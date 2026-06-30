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

/** A declared sweep knob (mirror of the FE `SweepKnob` / backend sweep_space entry). */
interface MockKnob {
  label?: string;
  type?: string;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
}

function isNum(x: unknown): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

/** `(breadth, reason, kind)` for one knob — mirrors `ai/gateway.py::_knob_metrics`. */
function knobMetrics(spec: MockKnob): { breadth: number; reason: string; kind: number } {
  const { min: mn, max: mx, step: st, type, options } = spec;
  const hasRange = isNum(mn) && isNum(mx) && mx > mn;
  if (type === "range" || type === "number" || (type == null && hasRange)) {
    if (hasRange) {
      const step = isNum(st) && st > 0 ? st : (mx - mn) / 10;
      const steps = Math.max(1, Math.round((mx - mn) / step));
      return { breadth: steps, reason: `widest declared range (${mn}–${mx}, ~${steps} steps)`, kind: 3 };
    }
    return { breadth: 1, reason: "numeric knob", kind: 3 };
  }
  const nOpts = Array.isArray(options) ? options.length : 0;
  if (type === "select" || (type == null && nOpts)) return { breadth: nOpts, reason: `${nOpts} options`, kind: 2 };
  if (type === "switch") return { breadth: 2, reason: "on / off", kind: 1 };
  return { breadth: 0, reason: "no declared range", kind: 0 };
}

/** Ranked sweep picks — mirrors `ai/gateway.py::rank_sweep_space` (the preselect source). */
export function mockSweepSuggestions(
  sweepSpace: Record<string, unknown> | undefined,
): { param: string; label: string; reason: string }[] {
  if (!sweepSpace || typeof sweepSpace !== "object") return [];
  return Object.entries(sweepSpace)
    .map(([param, raw]) => {
      const spec = (raw ?? {}) as MockKnob;
      const { breadth, reason, kind } = knobMetrics(spec);
      return { param, label: spec.label || param, reason, breadth, kind };
    })
    .sort((a, b) => b.kind - a.kind || b.breadth - a.breadth || a.label.toLowerCase().localeCompare(b.label.toLowerCase()))
    .slice(0, 3)
    .map(({ param, label, reason }) => ({ param, label, reason }));
}

/** Deterministic explanatory text grounded in the supplied artifact (mirrors the Null gateway). */
export function mockExplain(req: string, data: { scorecard?: Record<string, unknown>; sweep_space?: Record<string, unknown> }): string {
  if (req === "explain_score") {
    const sc = data.scorecard ?? {};
    const score = sc.score ?? "n/a";
    const tier = sc.tier ?? "unknown";
    const conf = sc.selom_confidence;
    let head = `Reproducibility ${score}/100 (tier: ${tier})`;
    if (conf != null) head += `, Selom confidence ${conf}/100`;
    return `${head}. Improve by supplying data that matches the paper's figures more closely. (mock summary)`;
  }
  const ranked = mockSweepSuggestions(data.sweep_space);
  if (!ranked.length) return "No sweep space provided — specify parameters and their ranges to sweep. (mock)";
  const parts = ranked.map((s) => `${s.label} (${s.reason})`).join(", ");
  return `Suggested sweeps: ${parts}. Numeric knobs with the widest declared range vary the result the most. (mock)`;
}
