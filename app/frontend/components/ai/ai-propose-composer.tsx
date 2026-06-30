"use client";

import { AskAi } from "@/components/ai/ask-ai";
import type { AiProposal } from "@/lib/ai/types";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { SkillParams } from "@/lib/skills/api";

/**
 * Thin compatibility wrapper — delegates to `<AskAi stage="analyze" mode="staged">`.
 *
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
  return (
    <AskAi
      stage="analyze"
      mode="staged"
      label="Ask AI to tune these inputs"
      placeholder="e.g. tighten the clusters"
      context={{ skillId, params, figureSpec }}
      onStaged={onProposals}
      disabled={disabled}
    />
  );
}
