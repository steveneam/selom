/**
 * MSW fixtures for the AI Action Gateway endpoints (S5) — mirror the live contract shape
 * (app/backend/routers/ai.py) so `npm run dev:mock` exercises the propose → accept → re-run →
 * attribution loop without a backend or an API key.
 *
 * Honesty note ([[mock-must-mirror-backend-contract]] / [[verify-on-real-data-not-mock]]): the
 * REAL backend default (gateway OFF) returns an EMPTY plan; the live gateway returns proposals.
 * These stubs return a representative NON-EMPTY HelperTurn so the UI path is demonstrable in
 * dev:mock — they prove the wire/UI, not the AI's content. Real proposal text is a live-key step.
 */

import type { GapBacklogEntry, HelperTurn } from "@/lib/ai/types";

/** A representative HelperTurn: one staged recompute proposal + its actor-tagged provenance entry.
 *  The proposal MUST target a param the open skill actually exposes — the real gateway validates
 *  every proposed param against the skill's param_spec, so a param the skill lacks is rejected /
 *  recorded as a gap, never staged. For the UMAP demo we bump `n_neighbors` (a real input, so the
 *  slider moves + the ✨ control marker lands on it); otherwise the first param present, else
 *  `resolution` as a last resort. */
// Unique per call so repeated Asks don't collide on one id (React duplicate-key + a concat'd queue
// merging two rows). Stays consistent WITHIN a turn (the plan/result/provenance all share it).
let _mockSeq = 0;

export function mockHelperTurn(skillId: string | null, goal: string, params: Record<string, unknown>): HelperTurn {
  const aid = `mock-a${++_mockSeq}`;
  const isUmap = (skillId ?? "").includes("umap");
  const target = isUmap || "n_neighbors" in params ? "n_neighbors" : Object.keys(params)[0] ?? "resolution";
  const isNeighbors = target === "n_neighbors";
  const current = Number(params[target] ?? (isNeighbors ? 15 : 1.0)) || (isNeighbors ? 15 : 1.0);
  const proposed = isNeighbors ? Math.round(current + 15) : Number((current + 0.2).toFixed(2));
  const rationale = isNeighbors
    ? "More neighbours → a smoother, more connected manifold."
    : "Higher resolution → tighter, more granular clusters.";
  return {
    goal,
    plan: {
      goal,
      notes: "Mock proposal (dev:mock). The live gateway needs SELOM_AI_GATEWAY=live + a key.",
      actions: [{ id: aid, type: "set_param", target, payload: { value: proposed }, rationale }],
    },
    results: [
      {
        action_id: aid,
        type: "set_param",
        target,
        tier: "recompute",
        status: "staged",
        effect: { value: proposed },
        errors: [],
        gap: null,
      },
    ],
    staged_params: { [target]: proposed },
    figure_spec: null,
    gaps: [],
    provenance_actions: [
      {
        action_id: aid,
        actor: "ai",
        type: "set_param",
        target,
        prompt: goal,
        model: "mock-model",
        approved_by: "",
        approved_at: "",
      },
    ],
  };
}

/** A representative ranked, categorized capability-gap backlog. */
export function mockGaps(): GapBacklogEntry[] {
  return [
    {
      context_hash: "mock-gap-1",
      stage: "ingest",
      unmet: "missing_column_op",
      category: "engine_capability_missing",
      skill_id: null,
      count: 4,
      sample_attempt: { op: "map_columns", from: "Gene", to: "gene_id" },
    },
    {
      context_hash: "mock-gap-2",
      stage: "analyze",
      unmet: "param_not_in_spec",
      category: "param_spec_gap",
      skill_id: "deg",
      count: 2,
      sample_attempt: { param: "min_lfc" },
    },
  ];
}

/** Deterministic explanatory text grounded in the supplied artifact (mirrors the Null gateway). */
export function mockExplain(req: string, data: { scorecard?: { score?: number }; sweep_space?: Record<string, unknown> }): string {
  if (req === "explain_score") {
    const score = data.scorecard?.score;
    return score != null
      ? `This figure scored ${score}/100 for reproducibility (mock summary).`
      : "Reproducibility scorecard (mock summary).";
  }
  const keys = Object.keys(data.sweep_space ?? {});
  return keys.length
    ? `Consider sweeping: ${keys.join(", ")} (mock suggestion).`
    : "No sweep space provided (mock suggestion).";
}
