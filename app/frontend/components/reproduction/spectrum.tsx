"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { shortName, tierLabel, usePapers } from "@/lib/reproduction/api";
import type { PaperCell, PaperSummary } from "@/lib/reproduction/types";
import { cn } from "@/lib/cn";

/**
 * The index "reproducibility spectrum" — the three dogfood papers ordered ascending
 * (RPGRIP1 63 → JEV 86 → Hani 96, red → green). The headline of the Reproduction view:
 * a paper-irreproducible figure scores LOW reproducibility but HIGH Selom-confidence, so
 * the spectrum reads as discovery, not failure.
 */
export function Spectrum() {
  const { data: papers } = usePapers();
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      {papers.map((p) => (
        <SpectrumCard key={p.slug} paper={p} />
      ))}
    </div>
  );
}

function SpectrumCard({ paper }: { paper: PaperSummary }) {
  const s = paper.score;
  const repro = s?.reproducibility ?? null;
  const color = s?.color ?? "#9ca3af";
  const findings = findingHighlights(paper.findings);

  return (
    <Link
      href={`/reproduction/${paper.slug}`}
      className={cn(
        "group relative flex flex-col rounded-xl border border-border bg-card p-5 shadow-sm",
        "transition-colors hover:border-ring/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
      )}
      // a faint tier-colored top accent ties the card to its score without relying on color alone
      style={{ boxShadow: `inset 0 2px 0 0 color-mix(in oklab, ${color} 55%, transparent)` }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {shortName(paper.slug)}
          </p>
          <p className="mt-1 line-clamp-2 text-sm leading-snug text-foreground/85">{paper.title}</p>
        </div>
        <ArrowUpRight className="size-4 shrink-0 text-muted-foreground/60 transition-colors group-hover:text-foreground" />
      </div>

      <div className="mt-4 flex items-end gap-3">
        <span className="tabular text-5xl font-bold leading-none" style={{ color }}>
          {repro ?? "—"}
        </span>
        <div className="mb-0.5 flex flex-col gap-1">
          <span
            className="inline-flex w-fit items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider"
            style={{
              backgroundColor: `color-mix(in oklab, ${color} 14%, transparent)`,
              borderColor: `color-mix(in oklab, ${color} 42%, transparent)`,
              color: `color-mix(in oklab, ${color} 80%, white)`,
            }}
          >
            {s ? tierLabel(s.tier) : "—"}
          </span>
          <span className="tabular text-[11px] text-muted-foreground">
            {s?.selom_confidence ?? "—"} confidence
          </span>
        </div>
      </div>

      {/* bottom-anchored so the coverage + heatmap + findings align across cards of
          unequal title/findings length */}
      <div className="mt-auto pt-4">
        <p className="text-[11px] leading-snug text-muted-foreground">{s?.coverage}</p>

        <MiniHeatmap cells={paper.cells} className="mt-3" />

        {findings.length > 0 && (
          <p className="mt-3 text-[11px] leading-snug text-muted-foreground/90">
            <span className="text-muted-foreground/70">Found: </span>
            {findings.join(" · ")}
          </p>
        )}
      </div>
    </Link>
  );
}

/** A one-row strip of per-panel cells (the card's at-a-glance heatmap). */
function MiniHeatmap({ cells, className }: { cells: PaperCell[]; className?: string }) {
  return (
    <div className={cn("flex flex-wrap gap-1", className)} aria-hidden>
      {cells.map((c) => (
        <span
          key={c.panel_key}
          title={`${c.panel_key} · ${tierLabel(c.tier)}${c.reproducibility != null ? ` · ${c.reproducibility}` : ""}`}
          className="size-5 rounded-[4px] ring-1 ring-inset ring-black/20"
          style={{ backgroundColor: c.in_scope ? c.color : "color-mix(in oklab, #9ca3af 35%, transparent)" }}
        />
      ))}
    </div>
  );
}

/** Pull the findings-first discoveries into a compact human line (D10). */
function findingHighlights(findings: Record<string, number>): string[] {
  const order: [string, string][] = [
    ["paper_irreproducible", "paper-irreproducible"],
    ["structural_limit", "structural"],
    ["engine_delta", "engine-delta"],
    ["upstream_delta", "upstream-delta"],
  ];
  return order
    .filter(([k]) => (findings[k] ?? 0) > 0)
    .map(([k, label]) => `${findings[k]} ${label}`);
}
