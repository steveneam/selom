"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight, GitCompareArrows, Hourglass } from "lucide-react";

import { tierLabel } from "@/lib/reproduction/api";
import type { SavedPaper } from "@/lib/workspace/types";

/**
 * The Score stage body in the Paper shell — the graded *output* of reproduction, GHOSTED until the
 * live drive lands (a later backend contract). It is a faithful skeleton of the real per-paper score
 * region (components/reproduction/paper-detail.tsx): the same two-axis ScoreHeader, the "what the
 * engine found" findings row, and a heatmap grid using the real `ReproHeatmap` cell dimensions — so
 * when the live run fills it, the layout doesn't reflow. (D-c / U6: the ghost mirrors the real layout,
 * not loose placeholder boxes.)
 */
export function ScoreStage({ paper }: { paper: SavedPaper }) {
  return (
    <div className="space-y-8">
      <GhostScoreHeader />
      <GhostFindings />
      <GhostHeatmap figureCount={paper.figureCount} />
      <GoldenVsComputedHint />
    </div>
  );
}

/** Mirrors `ScoreHeader` — two axis cards + the interpretation card, dimmed. */
function GhostScoreHeader() {
  return (
    <div className="grid gap-4 sm:grid-cols-[auto_auto_1fr] sm:items-stretch">
      <GhostAxis label="Reproducibility" sub="the paper & its data" />
      <GhostAxis label="Selom confidence" sub="our reconstruction" />
      <div className="flex flex-col justify-center rounded-xl border border-dashed border-border bg-card/30 p-5">
        <p className="inline-flex items-center gap-1.5 text-sm font-medium text-foreground/80">
          <Hourglass className="size-4 text-muted-foreground" />
          Awaiting reproduction
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
          Add the paper&apos;s supplementary data on the Reproduce tab, then run reproduction — Selom
          grades every figure on two axes: how reproducible it is, and how confident Selom is in its
          own work.
        </p>
      </div>
    </div>
  );
}

/** Matches `Axis`'s dimensions (p-5, text-5xl number, label/sub) so the live score fills it cleanly. */
function GhostAxis({ label, sub }: { label: string; sub: string }) {
  return (
    <div className="flex flex-col rounded-xl border border-dashed border-border bg-card/30 p-5">
      <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="tabular mt-1 text-5xl font-bold leading-none text-muted-foreground/30">
        —<span className="ml-0.5 text-lg font-normal text-muted-foreground/40">/100</span>
      </span>
      <span className="mt-1.5 text-xs text-muted-foreground/70">{sub}</span>
    </div>
  );
}

/** Mirrors `FindingsBanner` — the "what the engine found" row, with the finding categories greyed. */
const FINDING_LABELS = [
  "reproduced",
  "paper-irreproducible",
  "structural-limit",
  "engine-delta",
  "Selom defects",
];

function GhostFindings() {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-dashed border-border bg-card/30 px-4 py-3">
      <span className="mr-1 inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        <GitCompareArrows className="size-3.5" />
        What the engine found
      </span>
      {FINDING_LABELS.map((label) => (
        <span
          key={label}
          className="inline-flex items-center gap-1 rounded-md border border-dashed border-border bg-muted/40 px-2 py-0.5 text-xs text-muted-foreground/55"
        >
          <span className="tabular font-semibold">—</span>
          {label}
        </span>
      ))}
    </div>
  );
}

// The tier legend (red→green), shown static so the ghost still teaches the scale (mirrors ReproHeatmap).
const LEGEND: { tier: string; color: string }[] = [
  { tier: "verified", color: "#15803d" },
  { tier: "reproduced", color: "#22c55e" },
  { tier: "recoverable", color: "#84cc16" },
  { tier: "deposit-faithful", color: "#f59e0b" },
  { tier: "irreproducible", color: "#f97316" },
  { tier: "discrepant", color: "#ef4444" },
  { tier: "out-of-scope", color: "#9ca3af" },
];

/** Mirrors `ReproHeatmap` — the same 96px-cell grid + legend, with empty cells awaiting the grade. */
function GhostHeatmap({ figureCount }: { figureCount: number }) {
  const cells = Math.max(8, figureCount);
  return (
    <section>
      <SectionHeading
        title="Reproducibility heatmap"
        sub="Once reproduced, every panel is graded here — color paired with the numeric score, the panel key, and the attribution glyph."
      />
      <div className="mt-4 grid grid-cols-[repeat(auto-fill,minmax(96px,1fr))] gap-2" aria-hidden>
        {Array.from({ length: cells }).map((_, i) => (
          <div
            key={i}
            className="flex flex-col gap-1 rounded-lg border border-dashed border-border bg-card/30 p-2.5"
          >
            <div className="flex items-center justify-between gap-1">
              <span className="h-3 w-5 rounded-sm bg-muted/60" />
              <span className="size-2 rounded-full bg-muted/60" />
            </div>
            <span className="tabular text-2xl font-bold leading-none text-muted-foreground/25">—</span>
            <span className="h-2.5 w-10 rounded-sm bg-muted/50" />
          </div>
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

/** A light expectation-setter for the golden-vs-computed evidence table (the real detail's last block). */
function GoldenVsComputedHint() {
  return (
    <section>
      <SectionHeading
        title="Golden vs computed"
        sub="After reproduction, the printed target from the PDF appears here against what Selom computed, with a verdict and blame per number."
      />
      <Link
        href="/reproduction/jev"
        className="mt-3 inline-flex items-center gap-1 text-xs text-primary/90 hover:text-primary hover:underline"
      >
        See a graded example
        <ArrowUpRight className="size-3" />
      </Link>
    </section>
  );
}

function SectionHeading({ title, sub }: { title: string; sub: string }) {
  return (
    <div>
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{sub}</p>
    </div>
  );
}
