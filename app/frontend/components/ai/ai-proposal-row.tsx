"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/ui/cn";
import { AiMarker } from "./ai-marker";
import { describeAction } from "@/lib/ai/format";
import type { AiProposal } from "@/lib/ai/types";

/**
 * One AI-proposal row inside the pending-changes banner (S5, build piece b).
 *
 * Two states, set by the proposal's lifecycle:
 *   proposed — HOLLOW ✨, with Accept (stages the value) + Dismiss (drops the suggestion).
 *   accepted — FILLED ✨ + a "staged" tag, with Revert (drops the staged value back to base).
 * The single explicit "Re-run" in the banner header commits all accepted rows through /ai/apply.
 */
export function AiProposalRow({
  proposal,
  onAccept,
  onDismiss,
  onRevert,
  disabled,
}: {
  proposal: AiProposal;
  onAccept: (id: string) => void;
  onDismiss: (id: string) => void;
  onRevert: (id: string) => void;
  disabled?: boolean;
}) {
  const accepted = proposal.status === "accepted";
  return (
    <li
      className={cn(
        "flex items-center gap-2 rounded-md border px-2.5 py-1.5",
        accepted
          ? "border-stage-ai/35 bg-[color-mix(in_oklab,var(--stage-ai)_8%,transparent)]"
          : "border-border/70 bg-card/40",
      )}
    >
      <AiMarker
        state={accepted ? "staged" : "proposed"}
        model={proposal.model}
        onRevert={accepted ? () => onRevert(proposal.id) : undefined}
        className="mt-px"
      />
      <div className="min-w-0 flex-1">
        <p className="text-xs leading-snug text-foreground">
          {describeAction(proposal)}
          {proposal.paramKey && (
            <span className="ml-1 font-mono text-[11px] text-muted-foreground">{proposal.paramKey}</span>
          )}
          {proposal.value !== undefined && (
            <>
              {" → "}
              <span className="font-mono text-[11px] text-foreground">{String(proposal.value)}</span>
            </>
          )}
          {accepted && <span className="ml-1.5 text-[10px] font-medium uppercase tracking-wide text-stage-ai">staged</span>}
        </p>
        {proposal.rationale && (
          <p className="mt-0.5 truncate text-[11px] text-muted-foreground" title={proposal.rationale}>
            {proposal.rationale}
          </p>
        )}
      </div>
      {accepted ? (
        <Button size="sm" variant="ghost" className="shrink-0" disabled={disabled} onClick={() => onRevert(proposal.id)}>
          Revert
        </Button>
      ) : (
        <div className="flex shrink-0 items-center gap-0.5">
          <Button size="sm" variant="ghost" disabled={disabled} onClick={() => onAccept(proposal.id)}>
            Accept
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-muted-foreground hover:text-destructive"
            disabled={disabled}
            onClick={() => onDismiss(proposal.id)}
          >
            Dismiss
          </Button>
        </div>
      )}
    </li>
  );
}
