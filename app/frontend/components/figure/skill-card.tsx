"use client";

import { FlaskConical, SlidersHorizontal } from "lucide-react";

/**
 * The figure editor's slim *skill-identity* strip — which skill produced this figure
 * (name + origin/version), shown atop the figure-AGNOSTIC cosmetic inspector.
 *
 * Separation of concerns (owner principle, 2026-06-23): the figure EDITOR is confined to
 * COSMETICS (colours, lines, labels, axes — JSON-Patch, instant, no re-run). Anything that
 * changes the data's shape / metric / output — the skill's `param_spec` inputs (smoothing,
 * low-pass, scale, Naka-Rushton slope, …) — lives in the FIGURE-DATA stage, because editing
 * one re-runs the analysis into a new version. So this strip carries skill metadata + a
 * hand-off to Figure data; it deliberately does NOT host the inputs (that was the duplication).
 */
export function SkillCard({
  skillName,
  badge,
  onOpenFigureData,
}: {
  skillName: string;
  /** Small origin/version line under the name, e.g. "proprietary · v0.1.0". */
  badge?: string;
  /** Open the Figure-data stage (where this skill's re-run inputs live). */
  onOpenFigureData?: () => void;
}) {
  return (
    <section className="shrink-0 border-b border-border bg-card/40 px-3 py-2.5">
      <div className="flex items-center gap-2">
        <span className="grid size-7 shrink-0 place-items-center rounded-md bg-stage-figure/10 text-stage-figure [&_svg]:size-4">
          <FlaskConical />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-foreground">{skillName}</span>
          {badge && (
            <span className="block truncate text-[10px] uppercase tracking-wider text-muted-foreground">
              {badge}
            </span>
          )}
        </span>
      </div>
      {onOpenFigureData && (
        <button
          type="button"
          onClick={onOpenFigureData}
          className="mt-2 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-border/70 bg-background/40 px-2 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground"
        >
          <SlidersHorizontal className="size-3" /> Edit inputs in Figure data
        </button>
      )}
      <p className="mt-1.5 text-[10px] leading-relaxed text-muted-foreground/70">
        Below edits cosmetics only. Smoothing, scale, fit &amp; other inputs that re-run the
        analysis live in Figure data.
      </p>
    </section>
  );
}
