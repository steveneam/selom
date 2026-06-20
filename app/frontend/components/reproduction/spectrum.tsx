"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { shortName, tierLabel, usePapers } from "@/lib/reproduction/api";
import { authorSummary, citationLine } from "@/lib/paper/metadata";
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

/**
 * A fixed card skeleton: every section has a reserved height so the metadata row, score, coverage,
 * heatmap, and findings all align ROW-FOR-ROW across cards of unequal title / author / findings
 * length. The heatmap in particular sits at a consistent vertical position on every card because
 * everything above it (eyebrow → 2-line title → metadata → score → coverage) is fixed-height.
 */
function SpectrumCard({ paper }: { paper: PaperSummary }) {
  const s = paper.score;
  const repro = s?.reproducibility ?? null;
  const color = s?.color ?? "#9ca3af";
  const findings = findingHighlights(paper.findings);
  // The SAME formatters Skill Match uses — one shared metadata representation (spec §10).
  const meta = [authorSummary(paper.authors), citationLine(paper)].filter(Boolean).join(" · ");

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
      {/* 1 · eyebrow */}
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          {shortName(paper.slug)}
        </p>
        <ArrowUpRight className="size-4 shrink-0 text-muted-foreground/60 transition-colors group-hover:text-foreground" />
      </div>

      {/* 2 · title — fixed 2-line slot */}
      <h3 className="mt-2 line-clamp-2 min-h-[2.5rem] text-balance text-sm font-semibold leading-snug text-foreground/90">
        {paper.title}
      </h3>

      {/* 3 · metadata — shared authorSummary · citationLine, one reserved line */}
      <p className="mt-1 min-h-[1.25rem] truncate text-xs text-muted-foreground" title={meta}>
        {meta}
      </p>

      {/* 4 · two-axis score (reproducibility + Selom confidence) */}
      <div className="mt-4 flex items-end justify-between gap-3">
        <div className="flex flex-col">
          <div className="flex items-baseline gap-1">
            <span className="tabular text-5xl font-bold leading-none" style={{ color }}>
              {repro ?? "—"}
            </span>
            <span className="text-sm font-medium text-muted-foreground/50">/100</span>
          </div>
          <span className="mt-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/70">
            Reproducibility
          </span>
        </div>
        <div className="flex flex-col items-end gap-1.5">
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
            <span className="font-semibold text-foreground/80">{s?.selom_confidence ?? "—"}</span>{" "}
            confidence
          </span>
        </div>
      </div>

      {/* 5 · divider + coverage (one reserved line) */}
      <div className="mt-4 border-t border-border/60 pt-3">
        <p className="min-h-[1.25rem] truncate text-[11px] text-muted-foreground" title={s?.coverage}>
          {s?.coverage}
        </p>

        {/* 6 · heatmap — consistent vertical position across all cards */}
        <MiniHeatmap cells={paper.cells} className="mt-2.5" />

        {/* 7 · findings — reserved 2-line slot so the heatmap above never shifts */}
        <p className="mt-2.5 line-clamp-2 min-h-[2rem] text-[11px] leading-snug">
          {findings.length > 0 ? (
            <span className="text-muted-foreground/90">
              <span className="text-muted-foreground/70">Found: </span>
              {findings.join(" · ")}
            </span>
          ) : (
            <span className="text-muted-foreground/40">No residual findings flagged.</span>
          )}
        </p>
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
