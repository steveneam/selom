"use client";

import { AlertTriangle, Info, Play, Wand2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getSkill } from "@/lib/catalog/seed";
import type { IntakeProposal, ProposedStep } from "@/lib/intake/mock";

/**
 * Renders the LLM's pipeline proposal (design §4.3) as a reviewable plan. The
 * assistant proposes; the user runs. Each step is explainable (rationale +
 * confidence) and runnable. The mock returns this; phase B2 returns the real one.
 */
export function ProposalPlan({
  proposal,
  running,
  onRun,
}: {
  proposal: IntakeProposal;
  running: string | null;
  onRun: (step: ProposedStep) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2">
        <Wand2 className="mt-0.5 size-4 shrink-0 text-primary" />
        <div>
          <p className="text-sm font-medium text-foreground">Proposed analysis</p>
          <p className="text-xs text-muted-foreground">{proposal.summary}</p>
        </div>
      </div>

      {/* guardrails first — surfaced before figures */}
      {proposal.guardrails.length > 0 && (
        <div className="space-y-1.5">
          {proposal.guardrails.map((g, i) => (
            <div
              key={i}
              className="flex items-start gap-2 rounded-md border border-border bg-background/40 px-3 py-2"
            >
              {g.level === "info" ? (
                <Info className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
              ) : (
                <AlertTriangle
                  className={`mt-0.5 size-3.5 shrink-0 ${g.level === "error" ? "text-destructive" : "text-amber-400"}`}
                />
              )}
              <p className="text-xs text-foreground/85">{g.msg}</p>
            </div>
          ))}
        </div>
      )}

      {/* cleaning recipe */}
      {proposal.cleaning.length > 0 && (
        <div>
          <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
            Auto-clean
          </p>
          <div className="flex flex-wrap gap-1.5">
            {proposal.cleaning.map((c) => (
              <span key={c} className="rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* proposed steps */}
      <div className="space-y-2">
        <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
          Steps
        </p>
        {proposal.steps.length === 0 ? (
          <p className="text-xs text-muted-foreground">No steps — confirm the data type to get a proposal.</p>
        ) : (
          proposal.steps.map((step, i) => {
            const skill = getSkill(step.skillId);
            // `confidence` is only ever set by a genuine per-step measurement (none exist today) —
            // never fabricated for a step suggestion, so the bar is omitted rather than showing 0%.
            const pct = step.confidence != null ? Math.round(step.confidence * 100) : null;
            const busy = running === step.skillId;
            return (
              <div key={i} className="rounded-lg border border-border bg-card/60 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="tabular grid size-5 place-items-center rounded bg-secondary text-[11px] font-semibold text-secondary-foreground">
                      {i + 1}
                    </span>
                    <span className="truncate text-sm font-medium text-foreground">
                      {skill?.name ?? step.skillId}
                    </span>
                    {skill?.tier === "verified" && <Badge variant="verified">Verified</Badge>}
                  </div>
                  <Button size="sm" className="h-7 px-2.5 text-xs" disabled={busy} onClick={() => onRun(step)}>
                    <Play /> {busy ? "Running…" : "Run"}
                  </Button>
                </div>
                <p className="mt-1.5 pl-7 text-xs text-muted-foreground">{step.rationale}</p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5 pl-7">
                  {Object.entries(step.params).map(([k, v]) => (
                    <span key={k} className="tabular rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      {k}={String(v)}
                    </span>
                  ))}
                </div>
                {pct != null && (
                  <div className="mt-2 flex items-center gap-2 pl-7">
                    <div className="h-1 w-24 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary/70" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="tabular text-[10px] text-muted-foreground">{pct}% confidence</span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
