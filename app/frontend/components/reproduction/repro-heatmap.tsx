"use client";

import * as React from "react";

import { tierLabel } from "@/lib/reproduction/api";
import type { PanelScore } from "@/lib/reproduction/types";
import { tint } from "./atoms";

// The tiers in red→green order, for the legend (a low score is never color-only).
const LEGEND: { tier: string; color: string }[] = [
  { tier: "verified", color: "#15803d" },
  { tier: "reproduced", color: "#22c55e" },
  { tier: "recoverable", color: "#84cc16" },
  { tier: "deposit-faithful", color: "#f59e0b" },
  { tier: "irreproducible", color: "#f97316" },
  { tier: "discrepant", color: "#ef4444" },
  { tier: "out-of-scope", color: "#9ca3af" },
];

/**
 * The per-panel Reproducibility heatmap. Each cell pairs its tier color with the numeric
 * score, the panel key, and the attribution glyph — color is never the only signal — and a
 * legend + the golden-vs-computed table below give the non-color reading.
 */
export function ReproHeatmap({ cells }: { cells: PanelScore[] }) {
  return (
    <section aria-label="Per-panel reproducibility heatmap">
      <div className="grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-2">
        {cells.map((c) => (
          <HeatCell key={c.panel_key} cell={c} />
        ))}
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5">
        {LEGEND.map((l) => (
          <li key={l.tier} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <span
              aria-hidden
              className="size-2.5 rounded-[3px] ring-1 ring-inset ring-black/20"
              style={{ backgroundColor: l.color }}
            />
            {tierLabel(l.tier)}
          </li>
        ))}
      </ul>
    </section>
  );
}

function HeatCell({ cell }: { cell: PanelScore }) {
  const repro = cell.reproducibility;
  const label =
    `Panel ${cell.panel_key}: ${tierLabel(cell.tier)}` +
    (repro != null ? `, reproducibility ${repro} of 100` : ", out of scope") +
    (cell.selom_confidence != null ? `, Selom confidence ${cell.selom_confidence}` : "") +
    (cell.provenance ? `, source ${cell.provenance}` : "") +
    (cell.note ? `. ${cell.note}` : "");

  return (
    <div
      role="img"
      aria-label={label}
      title={label}
      className="flex flex-col gap-1 rounded-lg border p-2.5"
      style={tint(cell.color)}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="tabular text-xs font-semibold text-foreground/90">{cell.panel_key}</span>
        <span aria-hidden className="text-xs leading-none opacity-80" title={cell.attribution}>
          {ATTR_ICON[cell.attribution] ?? "·"}
        </span>
      </div>
      <span className="tabular text-2xl font-bold leading-none" style={{ color: cell.color }}>
        {repro ?? "N/A"}
      </span>
      <span className="truncate text-[10px] uppercase tracking-wider opacity-80">
        {tierLabel(cell.tier)}
      </span>
    </div>
  );
}

const ATTR_ICON: Record<string, string> = {
  selom: "✓",
  engine: "⚙",
  paper: "📄",
  data: "🗄",
};
