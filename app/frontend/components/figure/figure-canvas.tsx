"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";
import type { Config, Data, Layout } from "plotly.js";
import type { FigureSpec } from "@/lib/figure-spec";

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
export function FigureCanvas({ spec }: { spec: FigureSpec }) {
  const fixed = typeof spec.layout.width === "number";

  const figure = useMemo(
    () => structuredClone({ data: spec.data, layout: { ...spec.layout, autosize: !fixed } }),
    [spec, fixed],
  );

  const config = useMemo(
    () => ({
      displaylogo: false,
      responsive: true,
      modeBarButtonsToRemove: ["lasso2d", "select2d"] as const,
      toImageButtonOptions: { format: "png" as const, scale: 2, filename: "selom-figure" },
    }),
    [],
  );

  return (
    <Plot
      data={figure.data as unknown as Data[]}
      layout={figure.layout as unknown as Partial<Layout>}
      config={config as unknown as Partial<Config>}
      useResizeHandler
      style={{
        width: fixed ? `${spec.layout.width}px` : "100%",
        height: fixed ? `${spec.layout.height}px` : "100%",
      }}
    />
  );
}
