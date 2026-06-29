"use client";

import * as React from "react";
import { Sparkles, CornerDownLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/ui/cn";
import { proposeActions } from "@/lib/ai/api";
import { proposalsFromTurn } from "@/lib/ai/proposals";
import type { AiProposal } from "@/lib/ai/types";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { SkillParams } from "@/lib/skills/api";

/**
 * The propose entry point (S5) — a single-shot goal box that asks the gateway to suggest
 * figure-data inputs for the open figure. Deliberately NOT a conversation (the Ask-Selom chat
 * dock is future Pillar-3): one goal → a set of typed, validated proposals that land in the
 * pending-changes banner for the user to accept/revert.
 *
 * Degrades clean: with the gateway off (the default) `/ai/propose` returns an empty plan, so
 * this shows a quiet "gateway off" note and changes nothing — the deterministic editor is
 * entirely unaffected. Live proposal text awaits `SELOM_AI_GATEWAY=live` + `ANTHROPIC_API_KEY`.
 */
export function AiProposeComposer({
  skillId,
  params,
  figureSpec,
  onProposals,
  disabled,
}: {
  skillId: string;
  params: SkillParams;
  figureSpec?: FigureSpec | null;
  onProposals: (proposals: AiProposal[]) => void;
  disabled?: boolean;
}) {
  const [goal, setGoal] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [note, setNote] = React.useState<string | null>(null);

  async function send() {
    const g = goal.trim();
    if (!g || busy) return;
    setBusy(true);
    setNote(null);
    try {
      const turn = await proposeActions({
        skill_id: skillId,
        params,
        goal: g,
        figure_spec: (figureSpec as Record<string, unknown> | null) ?? null,
      });
      const proposals = proposalsFromTurn(turn);
      if (proposals.length > 0) {
        onProposals(proposals);
        setGoal("");
      } else if (turn.plan.actions.length > 0) {
        // The gateway DID propose, but only cosmetic actions (restyle/relabel) — they don't enter the
        // recompute queue, and applying them live from turn.figure_spec isn't wired yet (deferred,
        // gateway-off). Say that honestly rather than "nothing to propose" (which would be a lie).
        setNote(
          `The AI suggested ${turn.plan.actions.length} cosmetic change${turn.plan.actions.length === 1 ? "" : "s"} (restyle/relabel); applying those live isn't wired into this flow yet, so there are no input changes to stage.`,
        );
      } else {
        setNote(
          turn.plan.notes ||
            "No suggestions — the AI gateway is off or had nothing to propose. Your editor is unaffected.",
        );
      }
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Couldn't reach the AI helper.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={cn(
        "rounded-xl border p-3",
        "border-stage-ai/30 bg-[color-mix(in_oklab,var(--stage-ai)_7%,var(--card))]",
      )}
    >
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-foreground">
        <Sparkles className="size-3.5 text-stage-ai" aria-hidden />
        Ask AI to tune these inputs
      </p>
      <div className="flex items-center gap-2">
        <Input
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="e.g. tighten the clusters"
          disabled={disabled || busy}
          aria-label="Describe what you want the AI to adjust"
          className="h-8 flex-1 text-xs"
        />
        <Button size="sm" disabled={disabled || busy || !goal.trim()} onClick={() => void send()}>
          {busy ? "Asking…" : <><CornerDownLeft /> Ask</>}
        </Button>
      </div>
      {note && <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{note}</p>}
    </div>
  );
}
