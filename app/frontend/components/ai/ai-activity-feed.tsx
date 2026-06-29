"use client";

import * as React from "react";
import { TintChip } from "@/components/ui/confidence-chip";
import { AiMarker } from "./ai-marker";
import { describeAction, formatApprovedAt } from "@/lib/ai/format";
import type { AiAction, AiProposal } from "@/lib/ai/types";

/** One committed AI-assisted run — a group of actor-tagged actions that produced one figure. */
export interface ActivityTurn {
  figureId: string;
  title: string;
  /** When the figure was produced (ms) — drives the reverse-chron order + the header time. */
  createdAt: number;
  /** The NL goal that drove the turn, if recorded (the group sub-header). */
  goal?: string;
  actions: AiAction[];
  /** The figure's resolved params — the action tag carries the target, the *value* it became lives
   *  here (provenance.params), so a `set_param` row can show "target → value". */
  params?: Record<string, string | number | boolean>;
}

/**
 * The AI Activity feed (S5, build piece c) — the AI panel's Activity tab.
 *
 * Two sections so the tab always reflects what the AI is doing AND what it did:
 *   PENDING — the open figure's live proposal queue (✨ hollow = proposed, filled = staged). This is
 *             read-only here; accept/revert live in the pending-changes banner. It's why the tab's ✨
 *             badge has content even before a re-run (the badge counts staged proposals).
 *   HISTORY — the committed, immutable audit trail derived from each figure's `provenance.actions[]`
 *             (the actor-tagged record an `/ai/apply` run stamped), reverse-chron, grouped by turn.
 * With the gateway off and nothing committed, both are empty → a clean empty state (degrade-clean).
 */
export function AiActivityFeed({ turns, proposals = [] }: { turns: ActivityTurn[]; proposals?: AiProposal[] }) {
  const ordered = React.useMemo(
    () => [...turns].filter((t) => t.actions.length > 0).sort((a, b) => b.createdAt - a.createdAt),
    [turns],
  );

  if (ordered.length === 0 && proposals.length === 0) {
    return (
      <p className="px-1 py-6 text-center text-xs leading-relaxed text-muted-foreground">
        No AI activity yet. Ask the AI to tune a figure’s inputs — its suggestions appear here as you
        review them, and each accepted change is recorded with its model and approval once you re-run.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      {proposals.length > 0 && (
        <section>
          <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-stage-ai">
            Pending · this figure
          </h4>
          <ul className="space-y-1.5">
            {proposals.map((p) => {
              const staged = p.status === "accepted";
              return (
                <li
                  key={p.id}
                  className="flex items-start gap-2 rounded-lg border border-stage-ai/30 bg-[color-mix(in_oklab,var(--stage-ai)_7%,transparent)] px-2.5 py-2"
                >
                  <AiMarker state={staged ? "staged" : "proposed"} model={p.model} className="mt-px" />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs leading-snug text-foreground">
                      {describeAction(p)}
                      {p.paramKey && (
                        <span className="ml-1 font-mono text-[11px] text-muted-foreground">{p.paramKey}</span>
                      )}
                      {p.value !== undefined && (
                        <>
                          {" → "}
                          <span className="font-mono text-[11px] text-foreground">{String(p.value)}</span>
                        </>
                      )}
                    </p>
                    {p.rationale && (
                      <p className="mt-0.5 truncate text-[11px] text-muted-foreground" title={p.rationale}>
                        {p.rationale}
                      </p>
                    )}
                  </div>
                  <TintChip color="var(--stage-ai)" label={staged ? "staged" : "proposed"} size="xs" className="mt-px" />
                </li>
              );
            })}
          </ul>
          <p className="mt-1.5 text-[10px] leading-relaxed text-muted-foreground">
            Accept or revert these in the pending-changes banner, then re-run to commit.
          </p>
        </section>
      )}

      {ordered.length > 0 && (
        <section>
          {proposals.length > 0 && (
            <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              History
            </h4>
          )}
          <ol className="space-y-4">
            {ordered.map((turn) => (
              <li key={turn.figureId}>
                <div className="mb-1.5 flex items-baseline justify-between gap-2">
                  <p className="truncate text-xs font-semibold text-foreground" title={turn.title}>
                    {turn.title}
                  </p>
                  <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
                    {formatApprovedAt(new Date(turn.createdAt).toISOString())}
                  </span>
                </div>
                {turn.goal && (
                  <p className="mb-1.5 text-[11px] italic leading-relaxed text-muted-foreground">“{turn.goal}”</p>
                )}
                <ul className="space-y-1.5">
                  {turn.actions.map((a) => (
                    <li
                      key={a.action_id}
                      className="flex items-start gap-2 rounded-lg border border-border/70 bg-card/40 px-2.5 py-2"
                    >
                      <AiMarker state="applied" action={a} className="mt-px" />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs leading-snug text-foreground">
                          {describeAction(a)}
                          {a.target && (
                            <span className="ml-1 font-mono text-[11px] text-muted-foreground">{a.target}</span>
                          )}
                          {turn.params && a.target && turn.params[a.target] !== undefined && (
                            <>
                              {" → "}
                              <span className="font-mono text-[11px] text-foreground">
                                {String(turn.params[a.target])}
                              </span>
                            </>
                          )}
                        </p>
                        {a.prompt && (
                          <p className="mt-0.5 truncate text-[11px] text-muted-foreground" title={a.prompt}>
                            {a.prompt}
                          </p>
                        )}
                      </div>
                      <TintChip color="var(--stage-ai)" label="applied" size="xs" className="mt-px" />
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
