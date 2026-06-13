"use client";

import * as React from "react";
import { Boxes, Check, Database, ShieldCheck, Sparkles, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { Stagger, StaggerItem } from "@/components/ui/motion";

/**
 * The Selom loop, drawn as a connected, colour-coded stage flow:
 *
 *   Drop data  →  Apply a skill  →  Edit the figure  →  Publish with proof
 *   (blue)        (violet)          (cyan · centerpiece)  (green)
 *
 * Two registers from one component:
 *  - `variant="feature"` teaches the loop (Home hub) — every stage lit, the
 *    figure node glowing, connectors flowing.
 *  - `variant="progress"` tracks a real project — pass `states` and each node
 *    reads done / active / todo, with the active stage pulsing.
 *
 * The colour coding borrows the chart colourway so stage chrome and figure data
 * stay one family; cyan still owns "live/action" (the figure stage and the glow).
 */

export type StageKey = "data" | "skill" | "figure" | "publish";
export type StageState = "done" | "active" | "todo";

interface StageDef {
  key: StageKey;
  label: string;
  blurb: string;
  icon: LucideIcon;
  color: string; // css var reference
}

const STAGES: StageDef[] = [
  {
    key: "data",
    label: "Drop your data",
    blurb: "h5ad, CSV or mzML — cleaned and QC'd the moment it lands.",
    icon: Database,
    color: "var(--stage-data)",
  },
  {
    key: "skill",
    label: "Apply a skill",
    blurb: "UMAP, DEG, volcano, enrichment — Verified, parameterised, reproducible.",
    icon: Boxes,
    color: "var(--stage-skill)",
  },
  {
    key: "figure",
    label: "Edit the figure",
    blurb: "A live, publication-ready figure on a light artboard. No code.",
    icon: Sparkles,
    color: "var(--stage-figure)",
  },
  {
    key: "publish",
    label: "Publish with proof",
    blurb: "Auto methods text, full provenance and statistical guardrails.",
    icon: ShieldCheck,
    color: "var(--stage-publish)",
  },
];

export function Pipeline({
  variant = "feature",
  states,
  className,
}: {
  variant?: "feature" | "progress";
  states?: Partial<Record<StageKey, StageState>>;
  className?: string;
}) {
  return (
    <Stagger
      className={cn("grid grid-cols-1 gap-y-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-y-0", className)}
    >
      {STAGES.map((stage, i) => {
        const state: StageState =
          variant === "feature" ? (stage.key === "figure" ? "active" : "done") : states?.[stage.key] ?? "todo";
        return (
          <StaggerItem key={stage.key}>
            <Stage stage={stage} state={state} isLast={i === STAGES.length - 1} variant={variant} index={i} />
          </StaggerItem>
        );
      })}
    </Stagger>
  );
}

function Stage({
  stage,
  state,
  isLast,
  variant,
  index,
}: {
  stage: StageDef;
  state: StageState;
  isLast: boolean;
  variant: "feature" | "progress";
  index: number;
}) {
  const Icon = stage.icon;
  const lit = state !== "todo";
  const pulsing = state === "active";

  return (
    <div className="relative flex flex-col items-center px-3 text-center">
      {/* connector to the next node, drawn from this node's center rightward,
          sitting behind the node. Hidden on the stacked (sub-lg) layout. */}
      {!isLast && (
        <span
          aria-hidden
          className={cn(
            "absolute left-1/2 top-7 hidden h-px w-full lg:block",
            lit ? "flow-line" : "bg-border",
          )}
        />
      )}

      {/* node */}
      <div
        aria-hidden
        className={cn(
          "relative z-10 grid size-14 place-items-center rounded-2xl border bg-card transition-colors [&_svg]:size-6",
          pulsing && "node-pulse",
        )}
        style={
          lit
            ? {
                borderColor: `color-mix(in oklab, ${stage.color} 55%, transparent)`,
                background: `color-mix(in oklab, ${stage.color} 12%, var(--card))`,
                color: stage.color,
              }
            : { color: "var(--muted-foreground)" }
        }
      >
        <Icon />
        {state === "done" && variant === "progress" && (
          <span
            className="absolute -right-1.5 -top-1.5 grid size-5 place-items-center rounded-full border border-card bg-stage-publish text-[var(--background)]"
            style={{ background: "var(--stage-publish)" }}
          >
            <Check className="size-3" strokeWidth={3} />
          </span>
        )}
      </div>

      {/* step index — a small ordinal, since this genuinely IS an ordered flow */}
      <span className="tabular mt-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        Step {index + 1}
      </span>
      <h3 className="mt-1 text-base font-semibold tracking-tight text-foreground">{stage.label}</h3>
      <p className="mx-auto mt-1.5 max-w-[26ch] text-sm leading-relaxed text-muted-foreground">{stage.blurb}</p>
    </div>
  );
}
