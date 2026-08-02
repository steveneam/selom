"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowUpRight, Gauge } from "lucide-react";

import { reproducibilityStatement } from "@/lib/litsynth/api";
import { tierLabel } from "@/lib/reproduction/api";
import type { Scorecard } from "@/lib/reproduction/types";
import { cn } from "@/lib/ui/cn";
import { ProseBlock } from "./prose-block";

/**
 * The **Reproducibility statement** — the write-up's score section (docs/paper-outputs/spec.md §2).
 *
 * The paste-ready sentence is the point: a Methods section needs one line stating what was
 * computationally reproduced and how well. The two axis chips above it are context for that
 * sentence, not a second scoreboard — the full grading lives on the Score stage, which this links
 * to rather than restating (15Five's "How is the MEI calculated?" pattern).
 *
 * **What this deliberately does NOT do.** Contra and Lovable frame a score as a gap to close
 * ("strengthen your score", "Current 7.5 → Potential 9.5"). That idiom is wrong here and was
 * rejected outright: reproducibility is a property of **the paper and its data**, not of the user's
 * effort — a low score is frequently a discovery, not a failure, which is why the engine attributes
 * every residual. Uxcel's radar was rejected for the twin reason: the two axes are deliberately
 * separate and non-summable, and their *divergence* is the signal a radar would erase.
 */
export function ReproducibilityStatement({
  scorecard,
  scoreHref,
  loading = false,
  error,
}: {
  scorecard: Scorecard | null;
  /** Where "how this was graded" goes — the Score stage, or the published paper's graded page. */
  scoreHref: string;
  loading?: boolean;
  error?: string;
}) {
  const statement = React.useMemo(
    () => reproducibilityStatement(scorecard, { tierLabel }),
    [scorecard],
  );
  const score = scorecard?.score ?? null;

  return (
    <ProseBlock
      id="wu-repro"
      title="Reproducibility statement"
      icon={Gauge}
      text={statement}
      note="Report the score as measured — Selom never rounds it up for you."
      loading={loading}
      error={error}
      emptyNote="No panel in this paper has been graded yet, so there is nothing to state."
      action={
        <Link
          href={scoreHref}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-primary/90 transition-colors hover:text-primary hover:underline"
        >
          How this was graded
          <ArrowUpRight className="size-3" />
        </Link>
      }
    >
      {score && (
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          <AxisChip
            label="Reproducibility"
            value={score.reproducibility}
            sub="the paper & its data"
            color={score.color}
          />
          <AxisChip
            label="Selom confidence"
            value={score.selom_confidence}
            sub="our reconstruction"
          />
          <span className="text-[11px] text-muted-foreground">
            {tierLabel(score.tier)} · {score.n_scored}/{score.n_in_scope} in-scope panels graded
            {score.n_out_of_scope > 0 ? ` · ${score.n_out_of_scope} out of scope` : ""}
          </span>
        </div>
      )}
    </ProseBlock>
  );
}

/** One axis, shown beside the other and never combined with it. */
function AxisChip({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: number | null;
  sub: string;
  color?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-baseline gap-1.5 rounded-lg border px-2.5 py-1",
        color ? "" : "border-border bg-muted/30",
      )}
      style={
        color
          ? {
              borderColor: `color-mix(in oklab, ${color} 40%, transparent)`,
              backgroundColor: `color-mix(in oklab, ${color} 10%, transparent)`,
            }
          : undefined
      }
      title={`${label} — ${sub}`}
    >
      <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span className="tabular text-sm font-bold text-foreground">
        {value ?? "—"}
        <span className="ml-0.5 text-[10px] font-normal text-muted-foreground">/100</span>
      </span>
    </span>
  );
}
