"use client";

import dynamic from "next/dynamic";
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useSyncExternalStore,
} from "react";
import type { Config, Data, Layout } from "plotly.js";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { FigureStore } from "@/hooks/use-figure-store";
import { deriveFigureModel, projectOverlay } from "@/lib/figure/figure-model";
import {
  dropGl,
  ensureGl,
  glLoad,
  holdsGl,
  MAX_GL_CONTEXTS,
  subscribeGl,
  toSvgTraces,
  usesWebgl,
} from "@/lib/figure/webgl-budget";
import { installPerfHook, recordRenderMs } from "@/lib/figure/perf";
import { payloadWarnings } from "@/lib/figure/payload";
import { relayoutToOps, restyleToOps } from "@/lib/figure/plotly-edits";
import { remove } from "@/lib/figure/patch";
import { isSelomAnnotation } from "@/lib/figure/annotations";
import { wireMarkDrag, type Crosshair } from "./mark-drag";
import { wireThresholdDrag } from "./threshold-drag";
import { wireColorbarDrag } from "./colorbar-drag";
import { wireDendrogramTipDrag } from "./dendrogram-drag";
import { applyDendrogramTips, hasDendrogram } from "@/lib/heatmap/dendrogram";
import type { MarkRole } from "@/lib/erg/marks";
import type { VolcanoThresholds } from "@/lib/volcano/thresholds";
import { pointFromClick, type GeneLabelPoint } from "@/lib/volcano/labels";

type GraphDiv = {
  on?: (ev: string, cb: (e: unknown) => void) => void;
  removeListener?: (ev: string, cb: (e: unknown) => void) => void;
};

const Plot = dynamic(() => import("react-plotly.js"), {
  ssr: false,
  loading: () => <CanvasSkeleton />,
});

function CanvasSkeleton() {
  return (
    <div className="grid size-full place-items-center">
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <div className="size-7 animate-spin rounded-full border-2 border-border border-t-primary" />
        <span className="text-xs">Rendering figure…</span>
      </div>
    </div>
  );
}

/**
 * Renders the figure from the spec — the entire view is a pure function of the
 * spec, so every JSON-Patch edit reflects instantly. We hand Plotly a structural
 * clone because react-plotly.js mutates the data/layout it receives; cloning keeps
 * the store's immutable history snapshots pristine.
 */
export function FigureCanvas({
  spec,
  store,
  displayModeBar,
  onSelectTrace,
  onMarkMove,
  onThresholdChange,
  onToggleLabel,
}: {
  spec: FigureSpec;
  store?: FigureStore;
  /** Force the Plotly modebar on/off. Default (undefined) = Plotly's on-hover behaviour.
   *  Read-only previews (the compare panes) pass `false` for a clean, chrome-free figure. */
  displayModeBar?: boolean;
  /** Click-to-select (P3 §3.4): a click on a point/line reports its trace (curveNumber) so the
   *  inspector can focus that series. Independent of edits — works on a read-only figure too. */
  onSelectTrace?: (traceIndex: number) => void;
  /** Drag an ERG landmark dot → commit its new time (erg-manual-marks R5). Absent → dots aren't
   *  draggable (the numeric Marks panel is the fallback). Disabled in the overlay projection. */
  onMarkMove?: (segment: string, role: MarkRole, tMs: number) => void;
  /** Drag a volcano FC/p-value threshold line → stage the new cut (generalization-spec §E). Absent →
   *  the lines aren't draggable (the numeric Threshold editor is the fallback). Gated on the
   *  thresholds capability; disabled in the overlay projection. */
  onThresholdChange?: (t: VolcanoThresholds) => void;
  /** Click a plotted point to toggle its gene label (generalization-spec §H). Absent → clicks just
   *  select the series. Gated on the geneLabels capability; the click toggles a label instead of
   *  selecting when the point carries a gene. */
  onToggleLabel?: (point: GeneLabelPoint) => void;
}) {
  // Trace-grid OVERLAY view (meta.selom.layoutMode): render a single-axis projection of the grid.
  // The canonical `spec` stays the grid — this is display-only, so every edit, undo, and export
  // still operates on the real spec. Gestures are gated below (the projected axes ≠ canonical).
  const overlay =
    (spec?.layout?.meta as { selom?: { layoutMode?: string } } | undefined)?.selom?.layoutMode ===
    "overlay";
  // Compose the render spec: the ERG grid→overlay projection (trace-grids only) OR the dendrogram
  // leaf-tip projection (clustermaps only). Both are pure + identity when their pref is absent, so the
  // canonical `spec` (the store's source of truth, what undo/redo/export operate on) is never mutated.
  const display = useMemo(
    () => (overlay ? projectOverlay(spec) : applyDendrogramTips(spec)),
    [spec, overlay],
  );
  const fixed = typeof display.layout.width === "number";

  // Capability-driven gesture model (generalization-spec §A). Derived from the canonical spec so it's
  // consistent across grid/overlay. The GLOBAL default is a no-op drag (dragmode:false) so a stray
  // drag never box-zooms anywhere; zoom/pan are deliberate modebar buttons. A figure may opt into a
  // drag mode via meta.selom.capabilities.gesture. Dot-drag is gated on landmarkMarks below.
  const model = useMemo(() => deriveFigureModel(spec), [spec]);
  const gesture = model.gesture;
  // A clustermap carries furniture axes (tree gutters x2/y2·x3/y3, annotation strips + quant bar
  // x4/y4…) that have no titles. With inline axis-title editing on, Plotly paints a "Click to enter
  // … axis title" placeholder over EVERY title-less axis — 8+ of them litter a full clustermap in the
  // editor. So drop inline axis-title editing when secondary axes are present (the main sample/gene
  // titles are auto-set and meaningful); single-axis figures keep click-to-edit titles.
  const hasSecondaryAxes = useMemo(
    () =>
      Object.keys((spec?.layout ?? {}) as Record<string, unknown>).some((k) =>
        /^[xy]axis([2-9]|\d\d)$/.test(k),
      ),
    [spec],
  );
  const landmarkMarks = model.capabilities.landmarkMarks;
  const thresholds = model.capabilities.thresholds;
  const geneLabels = model.capabilities.geneLabels;
  const heatmapTones = model.capabilities.heatmapTones;

  // The render spec, memoized so Plotly is handed STABLE data/layout references across
  // renders (E1) — a fresh object every render makes react-plotly re-run `Plotly.react`
  // needlessly, churning the WebGL context. structuredClone keeps the store's immutable
  // history snapshots pristine (react-plotly mutates what it receives).
  const figure = useMemo(
    () =>
      structuredClone({
        data: display.data,
        layout: {
          ...display.layout,
          autosize: !fixed,
          dragmode: gesture.dragmode,
        },
      }),
    [display, fixed, gesture.dragmode],
  );

  // WebGL context budget (E1). A `scattergl`/`*gl` figure takes a scarce WebGL context;
  // past the browser's ceiling the oldest context is silently LOST (blank figure). Each GL
  // canvas claims a budget slot (keyed by a stable per-instance token) on mount and frees
  // it on unmount; the registry is read via useSyncExternalStore so a denied overflow canvas
  // re-upgrades the instant a slot frees. Under budget (≤ MAX_GL_CONTEXTS — the only case
  // the current UI reaches) the claim always succeeds and nothing changes; an over-budget
  // overflow canvas renders its GL traces as SVG instead of losing a context.
  const glToken = useId();
  const usesGl = useMemo(() => usesWebgl(figure.data), [figure.data]);
  useEffect(() => {
    if (!usesGl) return;
    ensureGl(glToken);
    return () => dropGl(glToken);
  }, [usesGl, glToken]);
  // Allowed unless this canvas uses GL and the budget can't seat it. Pre-commit (before the
  // effect claims) a would-be holder is admitted optimistically while a slot is free; an
  // overflow canvas (budget full, not yet a holder) is held to SVG from the first paint.
  const glAllowed = useSyncExternalStore(
    subscribeGl,
    () => !usesGl || holdsGl(glToken) || glLoad() < MAX_GL_CONTEXTS,
    () => true,
  );

  // The traces actually handed to Plotly: the GL figure as-is when allowed, else the SVG
  // projection (overflow path only). Pure + memoized — the canonical spec is untouched.
  const renderData = useMemo(
    () => (usesGl && !glAllowed ? toSvgTraces(figure.data as Data[]) : figure.data),
    [figure.data, usesGl, glAllowed],
  );

  // Render-timing telemetry (E2). Stamp the commit time when a new figure is about to draw
  // (useLayoutEffect runs synchronously after DOM commit); bindGestures — react-plotly's
  // onInitialized/onUpdate, fired once Plotly.react resolves — records the commit→draw delta.
  // A relative regression signal, read by the perf audit via window.__selomPerf.
  const renderStartRef = useRef(0);
  useEffect(() => installPerfHook(), []);
  useLayoutEffect(() => {
    renderStartRef.current = performance.now();
  }, [renderData, figure.layout]);

  // Payload ceiling (E2): a once-per-figure dev warning when a figure ships more bytes/points
  // than the advisory ceiling — non-blocking telemetry, the warnDeadKnob discipline.
  useEffect(() => {
    if (process.env.NODE_ENV === "production") return;
    const warnings = payloadWarnings(figure as unknown as FigureSpec);
    if (warnings.length) console.warn(`[figure] payload over ceiling — ${warnings.join("; ")}`);
  }, [figure]);

  // Handlers read the latest spec/store via a ref so the directly-bound Plotly
  // listeners stay stable while always seeing live values.
  const liveRef = useRef({ spec, store, onSelectTrace, overlay, onMarkMove, landmarkMarks, onThresholdChange, thresholds, onToggleLabel, geneLabels, heatmapTones });
  liveRef.current = { spec, store, onSelectTrace, overlay, onMarkMove, landmarkMarks, onThresholdChange, thresholds, onToggleLabel, geneLabels, heatmapTones };

  // Mark-drag plumbing (erg-manual-marks R5). The crosshair + live dot are positioned IMPERATIVELY
  // via refs (never React state) so a drag never re-renders the Plot. The dot moves as an HTML
  // overlay (no Plotly API → plotly.js stays out of the SSR graph). The real dot re-draws on re-run.
  const containerRef = useRef<HTMLDivElement | null>(null);
  const lineRef = useRef<HTMLDivElement | null>(null);
  const labelRef = useRef<HTMLDivElement | null>(null);
  const dotRef = useRef<HTMLDivElement | null>(null);
  // The live Plotly graph div, captured each bind so the unmount teardown (E1) can
  // explicitly remove the listeners WE bound directly onto it.
  const gdRef = useRef<GraphDiv | null>(null);
  const dragDisposeRef = useRef<(() => void) | null>(null);
  const thresholdDisposeRef = useRef<(() => void) | null>(null);
  const colorbarDisposeRef = useRef<(() => void) | null>(null);
  const dendroTipDisposeRef = useRef<(() => void) | null>(null);

  const setCrosshair = useCallback((c: Crosshair | null) => {
    const line = lineRef.current;
    const label = labelRef.current;
    const dot = dotRef.current;
    if (!line || !label || !dot) return;
    if (!c) {
      line.style.display = "none";
      label.style.display = "none";
      dot.style.display = "none";
      return;
    }
    line.style.display = "block";
    line.style.left = `${c.xPx}px`;
    line.style.top = `${c.yTopPx}px`;
    line.style.height = `${Math.max(0, c.yBotPx - c.yTopPx)}px`;
    label.style.display = "block";
    label.style.left = `${c.xPx}px`;
    label.style.top = `${c.yTopPx}px`;
    label.textContent = c.label;
    dot.style.display = "block";
    dot.style.left = `${c.dotXPx}px`;
    dot.style.top = `${c.dotYPx}px`;
  }, []);

  // Stable gesture handlers, created once. Each Plotly canvas gesture becomes ONE
  // undoable JSON-Patch edit (Plotly fires once on drag-release → one history entry).
  const handlersRef = useRef<
    {
      relayout: (e: unknown) => void;
      restyle: (e: unknown) => void;
      click: (e: unknown) => void;
      clickAnnotation: (e: unknown) => void;
    }
    | undefined
  >(undefined);
  if (!handlersRef.current) {
    handlersRef.current = {
      relayout: (e: unknown) => {
        const { spec: s, store: st, overlay: ov } = liveRef.current;
        // In the overlay projection the on-screen axes/shapes don't match the canonical grid spec,
        // so a layout gesture can't be mapped back safely — drop it (edits happen in Grid view).
        if (!st || !e || ov) return;
        const ops = relayoutToOps(s, e as Record<string, unknown>);
        if (ops.length) st.commit(ops);
      },
      // Trace-level gestures (colour-bar move/retext, legend-label rename) arrive
      // as a `plotly_restyle` event = [update, traceIndices].
      restyle: (e: unknown) => {
        const { spec: s, store: st, overlay: ov } = liveRef.current;
        if (!st || !Array.isArray(e) || ov) return;
        const [update, indices] = e as [Record<string, unknown>, number[]];
        const ops = restyleToOps(s, update ?? {}, indices ?? []);
        if (ops.length) st.commit(ops);
      },
      // A click is either a gene-label toggle (generalization-spec §H, volcano) or click-to-select
      // (P3 §3.4). On a geneLabels figure, a click on a point that carries a gene toggles its label
      // (an instant, undoable annotation) and stops there; otherwise it reports the clicked curve's
      // trace index so the inspector can focus its series. Pure selection is bound even read-only.
      click: (e: unknown) => {
        const point = (e as { points?: unknown[] } | undefined)?.points?.[0];
        const { onToggleLabel: otl, geneLabels: gl } = liveRef.current;
        if (gl && otl) {
          const lp = pointFromClick(point);
          if (lp) {
            otl(lp);
            return;
          }
        }
        const ci = (point as { curveNumber?: number } | undefined)?.curveNumber;
        if (typeof ci === "number") liveRef.current.onSelectTrace?.(ci);
      },
      // Click a gene label to DELETE it cleanly — the whole annotation (text + its smart connector)
      // goes in one undoable op, so nothing is left dangling. Fires only because the label sets
      // captureevents:true. Gated to a geneLabels figure with a store (the styler/editor), non-overlay.
      clickAnnotation: (e: unknown) => {
        const { store: st, overlay: ov, geneLabels: gl } = liveRef.current;
        if (!st || ov || !gl) return;
        const idx = (e as { index?: number } | undefined)?.index;
        if (typeof idx === "number" && idx >= 0) {
          // Click-to-delete applies to GENE LABELS only. A `selom`-tagged item (a hand-placed text
          // label, an arrow, a significance bracket) shares this annotations array but is owned by the
          // Annotate panel — deleting it here destroyed the user's annotation on first click, with the
          // bracket's other half left behind (milestone review 2026-07-25, blocker A3).
          const annos = (st.spec?.layout as { annotations?: unknown[] } | undefined)?.annotations;
          const target = Array.isArray(annos) ? annos[idx] : undefined;
          if (isSelomAnnotation(target)) return;
          st.commit([remove(`/layout/annotations/${idx}`)]);
        }
      },
    };
  }

  // Bind our gesture listeners straight onto the Plotly graph div, re-asserting
  // after EVERY render. We do NOT use react-plotly's onRelayout/onRestyle props:
  // those are synced inside a post-`Plotly.react` promise and don't attach until
  // the first *update*, so a drag on a brand-new figure would silently fail to
  // persist. react-plotly calls `onInitialized` (mount) and `onUpdate` (every
  // subsequent render) right after `Plotly.react` resolves — binding here, removing
  // first so it's idempotent, survives any internal listener reset. One commit/gesture.
  const bindGestures = useCallback((_figure: unknown, gd: unknown) => {
    // Render-timing (E2): this fires once Plotly has drawn — close the commit→draw window.
    if (renderStartRef.current) {
      recordRenderMs(performance.now() - renderStartRef.current);
      renderStartRef.current = 0; // one sample per commit
    }
    const el = gd as GraphDiv;
    const h = handlersRef.current;
    if (!el || typeof el.on !== "function" || !h) return;
    gdRef.current = el;
    el.removeListener?.("plotly_relayout", h.relayout);
    el.removeListener?.("plotly_restyle", h.restyle);
    el.removeListener?.("plotly_click", h.click);
    el.removeListener?.("plotly_clickannotation", h.clickAnnotation);
    el.on("plotly_relayout", h.relayout);
    el.on("plotly_restyle", h.restyle);
    el.on("plotly_click", h.click);
    el.on("plotly_clickannotation", h.clickAnnotation);

    // (Re)wire dot-dragging — capability-gated (spec §3): only on a figure that DECLARES editable
    // landmark marks (ERG trace / flicker-waveform), never on a UMAP scatter or any figure without
    // them. Also requires an editable (store), non-overlay figure with a mark-move handler. Bound
    // regardless of whether Plotly has finished loading. Dispose any prior binding first (idempotent).
    dragDisposeRef.current?.();
    dragDisposeRef.current = null;
    // Mark-drag needs only a mark-move handler (it sets manual_marks + re-runs) — NOT the cosmetic
    // `store`. So it works in the read-only Figure-data preview too, not just the styler, as long as
    // the figure declares landmark marks and isn't in the overlay projection.
    const { overlay: ov, onMarkMove: omm, landmarkMarks: lm } = liveRef.current;
    if (!ov && omm && lm) {
      dragDisposeRef.current = wireMarkDrag(gd as never, {
        getSpec: () => liveRef.current.spec,
        onMarkMove: omm,
        setCrosshair,
        container: containerRef.current,
      });
    }

    // (Re)wire threshold-line dragging — capability-gated (generalization-spec §E): only on a figure
    // that DECLARES the volcano thresholds capability and has a stage handler, never elsewhere. Like
    // mark-drag it needs no `store` (it stages params), so it works in the read-only Figure-data preview.
    thresholdDisposeRef.current?.();
    thresholdDisposeRef.current = null;
    const { onThresholdChange: otc, thresholds: th } = liveRef.current;
    if (!ov && otc && th) {
      thresholdDisposeRef.current = wireThresholdDrag(gd as never, {
        getSpec: () => liveRef.current.spec,
        onThresholdChange: otc,
      });
    }

    // (Re)wire colour-bar dragging — capability-gated (heatmap-spec §E): only on a heatmap that DECLARES
    // heatmapTones AND has an editable `store` (the styling artboard, not the read-only Figure-data
    // preview — re-toning is a cosmetic, undoable store edit). Disposes any prior binding first.
    colorbarDisposeRef.current?.();
    colorbarDisposeRef.current = null;
    const { heatmapTones: ht, store: stCb } = liveRef.current;
    if (!ov && ht && stCb) {
      colorbarDisposeRef.current = wireColorbarDrag(gd as never, {
        getSpec: () => liveRef.current.spec,
        store: stCb,
      });
    }

    // (Re)wire dendrogram leaf-tip dragging (dendrogram-tips-spec.md) — only on a clustermap that
    // HAS a tree AND an editable `store` (the styling artboard; lengthening a stub is a cosmetic,
    // undoable store edit, like the colour-bar). Gated on a present tree, not a declared capability.
    dendroTipDisposeRef.current?.();
    dendroTipDisposeRef.current = null;
    const { store: stDt } = liveRef.current;
    if (!ov && stDt && hasDendrogram(liveRef.current.spec)) {
      dendroTipDisposeRef.current = wireDendrogramTipDrag(gd as never, {
        getSpec: () => liveRef.current.spec,
        store: stDt,
        container: containerRef.current,
      });
    }
  }, [setCrosshair]);

  // Explicit teardown on unmount (E1). react-plotly.js calls `Plotly.purge(gd)` in its own
  // unmount, which tears down the WebGL context and Plotly's internal listeners (proven by
  // the Task B exit: canvas count → 0 at home). We additionally, and explicitly, remove the
  // gesture listeners WE bound directly onto the graph div and dispose every imperative drag
  // wiring, then drop the refs — so nothing we attached can outlive the component (the leak
  // surface in our control). Idempotent with react-plotly's purge; safe if it ran first.
  useEffect(() => () => {
    const el = gdRef.current;
    const h = handlersRef.current;
    if (el && h) {
      el.removeListener?.("plotly_relayout", h.relayout);
      el.removeListener?.("plotly_restyle", h.restyle);
      el.removeListener?.("plotly_click", h.click);
      el.removeListener?.("plotly_clickannotation", h.clickAnnotation);
    }
    dragDisposeRef.current?.();
    thresholdDisposeRef.current?.();
    colorbarDisposeRef.current?.();
    dendroTipDisposeRef.current?.();
    dragDisposeRef.current = null;
    thresholdDisposeRef.current = null;
    colorbarDisposeRef.current = null;
    dendroTipDisposeRef.current = null;
    gdRef.current = null;
  }, []);

  const config = useMemo(() => {
    // Zoom + pan stay as modebar buttons by default (a mode the user presses); a figure may drop
    // them with capabilities.gesture.zoomTools:false. lasso/select are always off (no point-select).
    const modeBarButtonsToRemove = [
      "lasso2d",
      "select2d",
      ...(gesture.zoomTools ? [] : ["zoom2d", "pan2d", "zoomIn2d", "zoomOut2d"]),
    ];
    return {
      displaylogo: false,
      responsive: true,
      // Wheel-zoom is OFF app-wide by default (resolved gesture.scrollZoom): a stray scroll zooms and
      // is fiddly to undo. Zoom stays a DELIBERATE action — the modebar Zoom button (drag a box) or
      // Zoom in/out — and Reset axes (or a double-click) restores the default view. A figure may opt
      // back into wheel-zoom via capabilities.gesture.scrollZoom:true.
      scrollZoom: gesture.scrollZoom,
      ...(displayModeBar === undefined ? {} : { displayModeBar }),
      // Direct manipulation: drag the legend / colour bar / annotations and
      // double-click titles in place. We DON'T enable blanket `editable` — that
      // also lets users drag data points (a data edit), which must stay server-side.
      // These element drags are independent of `dragmode`, so they survive dragmode:false.
      edits: store
        ? {
            legendPosition: true,
            legendText: true,
            annotationPosition: true,
            annotationTail: true,
            // Gene labels are identified by their `text` (= the gene symbol) — the toggle/carry model
            // and click-to-delete all key off it. Editing the text in place would break that identity
            // AND an empty-cleared text left a dangling arrow (the "line trace"). Reposition/drag yes,
            // rename no; delete is a clean click-to-remove (plotly_clickannotation).
            annotationText: false,
            titleText: true,
            axisTitleText: !hasSecondaryAxes,
            colorbarPosition: true,
            colorbarTitleText: true,
            shapePosition: true,
          }
        : undefined,
      modeBarButtonsToRemove,
      toImageButtonOptions: { format: "png" as const, scale: 2, filename: "selom-figure" },
    };
  }, [store, displayModeBar, gesture.zoomTools, gesture.scrollZoom, hasSecondaryAxes]);

  return (
    <div ref={containerRef} className="relative size-full">
      <Plot
        data={renderData as unknown as Data[]}
        layout={figure.layout as unknown as Partial<Layout>}
        config={config as unknown as Partial<Config>}
        onInitialized={bindGestures as never}
        onUpdate={bindGestures as never}
        useResizeHandler
        style={{
          width: fixed ? `${display.layout.width}px` : "100%",
          height: fixed ? `${display.layout.height}px` : "100%",
        }}
      />
      {/* Drag crosshair + live dot (erg-manual-marks) — positioned imperatively during a dot drag. */}
      <div
        ref={lineRef}
        aria-hidden
        className="pointer-events-none absolute z-10 hidden w-px -translate-x-1/2 bg-primary/70"
        style={{ display: "none" }}
      />
      <div
        ref={dotRef}
        aria-hidden
        className="pointer-events-none absolute z-10 hidden size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white bg-primary shadow"
        style={{ display: "none" }}
      />
      <div
        ref={labelRef}
        aria-hidden
        className="tabular pointer-events-none absolute z-10 hidden -translate-x-1/2 -translate-y-full rounded bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground shadow"
        style={{ display: "none" }}
      />
    </div>
  );
}
