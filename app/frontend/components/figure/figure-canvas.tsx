"use client";

import dynamic from "next/dynamic";
import { useCallback, useMemo, useRef } from "react";
import type { Config, Data, Layout } from "plotly.js";
import type { FigureSpec } from "@/lib/figure-spec";
import type { FigureStore } from "@/hooks/use-figure-store";
import { projectOverlay } from "@/lib/figure-model";
import { relayoutToOps, restyleToOps } from "@/lib/plotly-edits";

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
}: {
  spec: FigureSpec;
  store?: FigureStore;
  /** Force the Plotly modebar on/off. Default (undefined) = Plotly's on-hover behaviour.
   *  Read-only previews (the compare panes) pass `false` for a clean, chrome-free figure. */
  displayModeBar?: boolean;
  /** Click-to-select (P3 §3.4): a click on a point/line reports its trace (curveNumber) so the
   *  inspector can focus that series. Independent of edits — works on a read-only figure too. */
  onSelectTrace?: (traceIndex: number) => void;
}) {
  // Trace-grid OVERLAY view (meta.selom.layoutMode): render a single-axis projection of the grid.
  // The canonical `spec` stays the grid — this is display-only, so every edit, undo, and export
  // still operates on the real spec. Gestures are gated below (the projected axes ≠ canonical).
  const overlay =
    (spec?.layout?.meta as { selom?: { layoutMode?: string } } | undefined)?.selom?.layoutMode ===
    "overlay";
  const display = useMemo(() => (overlay ? projectOverlay(spec) : spec), [spec, overlay]);
  const fixed = typeof display.layout.width === "number";

  const figure = useMemo(
    () => structuredClone({ data: display.data, layout: { ...display.layout, autosize: !fixed } }),
    [display, fixed],
  );

  // Handlers read the latest spec/store via a ref so the directly-bound Plotly
  // listeners stay stable while always seeing live values.
  const liveRef = useRef({ spec, store, onSelectTrace, overlay });
  liveRef.current = { spec, store, onSelectTrace, overlay };

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
      // Click-to-select (P3 §3.4): report the clicked curve's trace index so the inspector can
      // focus its series. Pure selection — no edit, so it's bound even on a read-only figure.
      click: (e: unknown) => {
        const points = (e as { points?: { curveNumber?: number }[] } | undefined)?.points;
        const ci = points?.[0]?.curveNumber;
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
  }, []);

  const config = useMemo(
    () => ({
      displaylogo: false,
      responsive: true,
      ...(displayModeBar === undefined ? {} : { displayModeBar }),
      // Direct manipulation: drag the legend / colour bar / annotations and
      // double-click titles in place. We DON'T enable blanket `editable` — that
      // also lets users drag data points (a data edit), which must stay server-side.
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
      modeBarButtonsToRemove: ["lasso2d", "select2d"] as const,
      toImageButtonOptions: { format: "png" as const, scale: 2, filename: "selom-figure" },
    }),
    [store, displayModeBar],
  );

  return (
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
  );
}
