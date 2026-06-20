"use client";

import * as React from "react";
import Link from "next/link";
import { type LucideIcon, ArrowRight, Check, FlaskConical, Gauge, ScanSearch } from "lucide-react";

import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";

/**
 * The Paper-workflow pipeline header — the umbrella's three stages shown as a stepper above the paper
 * metadata, so the flow reads as one pipeline (workspace-library spec §10): a paper you drop flows
 * Skill Match → Reproduce → Score. Shared across surfaces (Skill Match results + the per-paper
 * Reproduction workspace, and later Recover data) so the workflow looks identical everywhere — the
 * same "one shared framework" discipline as the paper-metadata layer.
 *
 * The stage the user is ON is highlighted; earlier stages read as done (✓); later ones are muted.
 * The optional `forward` action is the prominent next-step button (e.g. "Reproduce →" on Skill Match,
 * which carries the paper into the Reproduction workspace).
 */
export type PipelineStage = "skill-match" | "reproduce" | "score";

const STAGES: { key: PipelineStage; label: string; icon: LucideIcon }[] = [
  { key: "skill-match", label: "Skill Match", icon: ScanSearch },
  { key: "reproduce", label: "Reproduce", icon: FlaskConical },
  { key: "score", label: "Score", icon: Gauge },
];

export interface PipelineForward {
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  title?: string;
  icon?: LucideIcon;
}

export function PaperPipeline({
  current,
  forward,
  links,
  className,
}: {
  current: PipelineStage;
  forward?: PipelineForward;
  /** Per-stage hrefs — a stage with a link (and not the current one) becomes a clickable pill that
   *  navigates to that stage for the same paper, so the pills are the cross-stage nav. */
  links?: Partial<Record<PipelineStage, string>>;
  className?: string;
}) {
  const curIdx = STAGES.findIndex((s) => s.key === current);
  const ForwardIcon = forward?.icon;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-x-2 gap-y-3 rounded-xl border border-border bg-card/40 px-3 py-2.5",
        className,
      )}
    >
      <ol className="flex items-center gap-1.5">
        {STAGES.map((s, i) => {
          const state = i < curIdx ? "done" : i === curIdx ? "current" : "upcoming";
          const Icon = s.icon;
          const href = state === "current" ? undefined : links?.[s.key];
          const pill = (
            <span
              aria-current={state === "current" ? "step" : undefined}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                state === "done" && "border-primary/25 bg-primary/5 text-primary/80",
                state === "current" && "border-primary/50 bg-primary/10 text-primary",
                state === "upcoming" && "border-border bg-muted/40 text-muted-foreground/55",
                href && "cursor-pointer hover:border-primary/50 hover:bg-primary/10 hover:text-primary",
              )}
            >
              <span
                className={cn(
                  "grid size-4 place-items-center rounded-full text-[10px] font-semibold [&_svg]:size-3",
                  state === "done" && "bg-primary/15 text-primary",
                  state === "current" && "bg-primary text-primary-foreground",
                  state === "upcoming" && "bg-muted text-muted-foreground/60",
                )}
              >
                {state === "done" ? <Check /> : <Icon />}
              </span>
              {s.label}
            </span>
          );
          return (
            <React.Fragment key={s.key}>
              {i > 0 && (
                <ArrowRight
                  aria-hidden
                  className={cn("size-3.5", i <= curIdx ? "text-primary/45" : "text-muted-foreground/25")}
                />
              )}
              <li className="contents">
                {href ? (
                  <Link
                    href={href}
                    title={`Go to ${s.label}`}
                    className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
                  >
                    {pill}
                  </Link>
                ) : (
                  pill
                )}
              </li>
            </React.Fragment>
          );
        })}
      </ol>

      {forward && (
        <Button
          size="sm"
          className="ml-auto"
          onClick={forward.onClick}
          disabled={forward.disabled}
          title={forward.title}
        >
          {ForwardIcon ? <ForwardIcon /> : null}
          {forward.label}
          <ArrowRight />
        </Button>
      )}
    </div>
  );
}
