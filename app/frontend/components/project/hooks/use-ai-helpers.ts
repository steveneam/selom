"use client";

import * as React from "react";
import { projectStore } from "@/lib/projects/store";
import {
  acceptProposal,
  approvedActions,
  dismissProposal,
  pendingCounter,
  unacceptProposal,
  type PendingCounter,
} from "@/lib/ai/proposals";
import type { AiProposal } from "@/lib/ai/types";
import type { ActivityTurn } from "@/components/ai/ai-activity-feed";
import type { SkillParams } from "@/lib/skills/api";
import type { Figure } from "@/lib/projects/types";

interface UseAiHelpersArgs {
  /** The open figure — owns the AI-proposal queue (`aiProposals`). */
  activeFigure: Figure | undefined;
  activeFigureId: string | null;
  /** All project figures — the Activity feed's committed History derives from their provenance. */
  figures: Figure[];
  /** The figure-data staged params + base (the run values) — the counter/author map diff these. */
  fdParams: SkillParams;
  fdBaseParams: SkillParams;
  setFdParams: React.Dispatch<React.SetStateAction<SkillParams>>;
  /** The a/b-label toggle, restored on Reset (it's staged separately from params). */
  setMarkLabelsShown: React.Dispatch<React.SetStateAction<boolean>>;
  /** The two re-run flavours from useFigureRun — rerunPending routes between them. */
  rerunFigureWithAi: (params: SkillParams, aiActions: ReturnType<typeof approvedActions>) => Promise<void> | void;
  rerunFigureWithParams: (params: SkillParams) => Promise<void> | void;
}

export interface AiHelpers {
  /** The open figure's proposal queue (proposed + accepted), or []. */
  aiProposals: AiProposal[];
  /** The derived author-partitioned pending counter (banner header). */
  aiCounter: PendingCounter;
  /** Committed AI-assisted runs for the Activity feed's History. */
  aiTurns: ActivityTurn[];
  acceptAiProposal: (id: string) => void;
  dismissAiProposal: (id: string) => void;
  revertAiProposal: (id: string) => void;
  addAiProposals: (fresh: AiProposal[]) => void;
  rerunPending: () => void;
  resetFdToBase: () => void;
}

/**
 * The AI-Helpers (S5) orchestration for ProjectWorkspace — extracted from the editor orchestrator
 * (§3C decomposition pattern: lift state + orchestration into a cohesive hook, leave rendering in
 * the component). Owns the proposal queue derivations (the derived author counter, the committed
 * Activity turns) and the accept / dismiss / revert / add / re-run / reset handlers. Contract-frozen:
 * the logic is the orchestrator's verbatim, with the figure-data staging state + the run flavours
 * injected. The single source of truth stays the staged-vs-base diff + the accepted-proposal author
 * map (lib/ai/proposals); no stored counter. The AI panel's open/close is UI state and stays in the
 * component.
 */
export function useAiHelpers({
  activeFigure,
  activeFigureId,
  figures,
  fdParams,
  fdBaseParams,
  setFdParams,
  setMarkLabelsShown,
  rerunFigureWithAi,
  rerunFigureWithParams,
}: UseAiHelpersArgs): AiHelpers {
  // The open figure's AI-proposal queue + the DERIVED, author-partitioned banner counter. Single
  // source of truth = the staged-vs-base param diff + the accepted-proposal author map; no stored
  // counter to drift. Reverting a value to base drops it from the diff → the count auto-decrements.
  const aiProposals = activeFigure?.aiProposals ?? [];
  const aiCounter = pendingCounter(fdBaseParams, fdParams, aiProposals);
  // Committed AI-assisted runs (one per AI-touched figure) for the Activity feed.
  const aiTurns: ActivityTurn[] = React.useMemo(
    () =>
      figures
        .filter((f) => (f.provenance?.actions?.length ?? 0) > 0)
        .map((f) => ({
          figureId: f.id,
          title: f.title,
          createdAt: f.createdAt,
          actions: f.provenance!.actions!,
          params: f.provenance!.params,
        })),
    [figures],
  );

  // Accept a proposal → stage its value into fdParams (the ✨ author map then attributes the
  // staged key to "ai"); the single explicit re-run commits it through /ai/apply.
  function acceptAiProposal(id: string) {
    if (!activeFigureId) return;
    const p = aiProposals.find((x) => x.id === id);
    if (p?.paramKey !== undefined && p.value !== undefined) {
      setFdParams((prev) => ({ ...prev, [p.paramKey!]: p.value! }));
    }
    projectStore.setFigureProposals(activeFigureId, acceptProposal(aiProposals, id));
  }
  // Dismiss a still-proposed suggestion (it was never staged) — drop it from the queue.
  function dismissAiProposal(id: string) {
    if (!activeFigureId) return;
    projectStore.setFigureProposals(activeFigureId, dismissProposal(aiProposals, id));
  }
  // Revert an accepted proposal → restore its base value (leaves the diff, decrements the counter)
  // and return the suggestion to "proposed" so it can be re-accepted.
  function revertAiProposal(id: string) {
    if (!activeFigureId) return;
    const p = aiProposals.find((x) => x.id === id);
    if (p?.paramKey !== undefined) {
      const key = p.paramKey;
      setFdParams((prev) => {
        const next = { ...prev };
        if (key in fdBaseParams) next[key] = fdBaseParams[key];
        else delete next[key];
        return next;
      });
    }
    projectStore.setFigureProposals(activeFigureId, unacceptProposal(aiProposals, id));
  }
  // Append a fresh batch of AI proposals (from the propose composer) to the open figure's queue.
  function addAiProposals(fresh: AiProposal[]) {
    if (!activeFigureId) return;
    projectStore.setFigureProposals(activeFigureId, [...aiProposals, ...fresh]);
  }
  // The one explicit "Re-run" for the pending-changes banner: route through /ai/apply when any
  // AI proposal is accepted (so the figure gets actor-tagged provenance.actions[]), else the plain
  // edited-inputs re-run. "AI compiles away" — the deterministic run is identical either way.
  function rerunPending() {
    // Only emit AI actions for params whose value is STILL the AI's (authorOf gate inside) — a
    // user-overridden accepted proposal must not be stamped as AI-authored. The server derives the
    // attribution (actor/model/approved_by/approved_at) at /ai/apply; the FE posts only the delta.
    const actions = approvedActions(aiProposals, fdBaseParams, fdParams);
    if (actions.length > 0) void rerunFigureWithAi(fdParams, actions);
    else void rerunFigureWithParams(fdParams);
  }
  // Discard all staged input changes → back to this figure's current run values, and un-stage any
  // accepted AI proposals (return them to "proposed" so the suggestions stay offered, just not
  // applied). Pre-commit only: nothing is persisted — the figure's provenance is untouched until a
  // re-run actually produces a new version.
  function resetFdToBase() {
    setFdParams({ ...fdBaseParams });
    // Restore EVERY staged surface, not just params — the a/b-label toggle is staged separately, so
    // a params-only reset would leave the preview changed while the banner reports "no pending".
    setMarkLabelsShown(fdBaseParams.mark_labels === undefined ? true : String(fdBaseParams.mark_labels) === "true");
    if (activeFigureId && aiProposals.some((p) => p.status === "accepted")) {
      projectStore.setFigureProposals(
        activeFigureId,
        aiProposals.map((p) => (p.status === "accepted" ? { ...p, status: "proposed" as const } : p)),
      );
    }
  }

  return {
    aiProposals,
    aiCounter,
    aiTurns,
    acceptAiProposal,
    dismissAiProposal,
    revertAiProposal,
    addAiProposals,
    rerunPending,
    resetFdToBase,
  };
}
