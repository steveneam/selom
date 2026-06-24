"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef } from "react";
import type { Config, Data, Layout } from "plotly.js";
import type { FigureSpec } from "@/lib/figure-spec";
import type { FigureStore } from "@/hooks/use-figure-store";
import { deriveFigureModel, projectOverlay } from "@/lib/figure-model";
import { relayoutToOps, restyleToOps } from "@/lib/plotly-edits";
import { wireMarkDrag, type Crosshair } from "./mark-drag";
import { wireThresholdDrag } from "./threshold-drag";
import { wireColorbarDrag } from "./colorbar-drag";
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
  const display = useMemo(() => (overlay ? projectOverlay(spec) : spec), [spec, overlay]);
  const fixed = typeof display.layout.width === "number";

  // Capability-driven gesture model (generalization-spec §A). Derived from the canonical spec so it's
  // consistent across grid/overlay. The GLOBAL default is a no-op drag (dragmode:false) so a stray
  // drag never box-zooms anywhere; zoom/pan are deliberate modebar buttons. A figure may opt into a
  // drag mode via meta.selom.capabilities.gesture. Dot-drag is gated on landmarkMarks below.
  const model = useMemo(() => deriveFigureModel(spec), [spec]);
  const gesture = model.gesture;
  const landmarkMarks = model.capabilities.landmarkMarks;
  const thresholds = model.capabilities.thresholds;
  const geneLabels = model.capabilities.geneLabels;
  const heatmapTones = model.capabilities.heatmapTones;

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
  const dragDisposeRef = useRef<(() => void) | null>(null);
  const thresholdDisposeRef = useRef<(() => void) | null>(null);
  const colorbarDisposeRef = useRef<(() => void) | null>(null);

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
    { relayout: (e: unknown) => void; restyle: (e: unknown) => void; click: (e: unknown) => void }
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
    const el = gd as GraphDiv;
    const h = handlersRef.current;
    if (!el || typeof el.on !== "function" || !h) return;
    el.removeListener?.("plotly_relayout", h.relayout);
    el.removeListener?.("plotly_restyle", h.restyle);
    el.removeListener?.("plotly_click", h.click);
    el.on("plotly_relayout", h.relayout);
    el.on("plotly_restyle", h.restyle);
    el.on("plotly_click", h.click);

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
  }, [setCrosshair]);

  useEffect(() => () => {
    dragDisposeRef.current?.();
    thresholdDisposeRef.current?.();
    colorbarDisposeRef.current?.();
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
            annotationText: true,
            titleText: true,
            axisTitleText: true,
            colorbarPosition: true,
            colorbarTitleText: true,
            shapePosition: true,
          }
        : undefined,
      modeBarButtonsToRemove,
      toImageButtonOptions: { format: "png" as const, scale: 2, filename: "selom-figure" },
    };
  }, [store, displayModeBar, gesture.zoomTools, gesture.scrollZoom]);

  return (
    <div ref={containerRef} className="relative size-full">
      <Plot
        data={figure.data as unknown as Data[]}
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
