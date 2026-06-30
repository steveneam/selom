/**
 * Wire + domain types for the AI Action Gateway (S5 frontend).
 *
 * These mirror the shipped backend contract (app/backend/ai/models.py +
 * routers/ai.py) one-for-one so the four endpoint wrappers in `./api.ts` cross the
 * HTTP boundary with no reshaping. The AI is a *translator* over the deterministic
 * spine: it proposes typed, schema-validated actions from a closed registry; our
 * validation (same as a human run) decides apply / stage / reject / gap. Nothing
 * here is trusted as authoritative — `tier` is always registry-derived server-side,
 * never read from a proposal.
 */

/** The closed, declared action vocabulary (mirror of backend ACTION_TYPES). */
export type AiActionType =
  | "set_param"
  | "add_filter"
  | "remove_filter"
  | "restyle_figure"
  | "relabel"
  // S3 — ingest-stage helpers (P1 surface)
  | "set_profile"
  | "set_design"
  | "map_columns"
  | "apply_cleaning_step"
  // S4 — P3 route action
  | "select_skill";

/** A run's tier — derived from the registry, never from a proposal. */
export type ActionTier = "cosmetic" | "recompute";

/** One atomic proposal from the gateway (backend `Action`). */
export interface ProposedAction {
  id: string;
  type: AiActionType;
  target: string;
  payload: Record<string, unknown>;
  rationale: string;
}

/** The gateway's response: the goal + the ordered proposed actions (backend `ActionPlan`). */
export interface ActionPlan {
  goal: string;
  actions: ProposedAction[];
  notes: string;
}

/** Per-action outcome after the spine validates + processes it (backend `ActionResult`). */
export interface ActionResult {
  action_id: string;
  type: string;
  target: string;
  tier: ActionTier;
  status: "applied" | "staged" | "rejected" | "gap";
  effect: Record<string, unknown>;
  errors: string[];
  gap: CapabilityGap | null;
}

/** A coherent-but-unfulfillable action — the self-improving loop's signal (backend `CapabilityGap`). */
export interface CapabilityGap {
  stage: string;
  intent: string;
  unmet:
    | "no_such_action"
    | "param_not_in_spec"
    | "unsupported_filter"
    | "no_fitting_skill"
    | "validation_blocked"
    | "missing_column_op";
  attempted: Record<string, unknown>;
  context_hash: string;
  skill_id: string | null;
}

/**
 * The actor-tagged provenance action recorded on an AI-assisted run
 * (backend provenance.build `actions[]` entry). This is what the ✨ marker reads
 * for its tooltip and the Activity feed renders. `actor` is "ai" for gateway
 * proposals (an "operator" dogfood action is also possible).
 */
export interface AiAction {
  action_id: string;
  actor: string;
  type: string;
  target: string;
  prompt: string;
  model: string;
  approved_by: string;
  approved_at: string;
}

/** Full outcome of one propose→validate→(stage|apply) pass (backend `HelperTurn`). */
export interface HelperTurn {
  goal: string;
  plan: ActionPlan;
  results: ActionResult[];
  staged_params: Record<string, string | number | boolean>;
  figure_spec: Record<string, unknown> | null;
  gaps: CapabilityGap[];
  provenance_actions: AiAction[];
}

/** One ranked, categorized backlog entry from `GET /ai/gaps`. */
export interface GapBacklogEntry {
  context_hash: string;
  stage: string;
  unmet: CapabilityGap["unmet"];
  /** The bucket the backlog ranks by (e.g. "engine_capability_missing", "param_spec_gap"). */
  category: string;
  skill_id: string | null;
  count: number;
  /** The last attempted payload that produced this gap. */
  sample_attempt: Record<string, unknown>;
}

/** `POST /ai/explain` request — informational, never a mutation. */
export interface ExplainRequest {
  request: "explain_score" | "propose_sweep";
  stage?: string;
  skill_id?: string | null;
  goal?: string;
  scorecard?: Record<string, unknown> | null;
  sweep_space?: Record<string, unknown> | null;
}

/**
 * One ranked sweep recommendation (`propose_sweep` only). Always the DETERMINISTIC
 * ranking — pure data grounded in the declared sweep space (knob value-space breadth),
 * computed server-side regardless of the gateway, so the picked param is reproducible
 * even when the prose is AI. The Sweep form preselects `suggestions[0].param`.
 */
export interface SweepSuggestion {
  /** The param key to sweep (a key present in the posted sweep_space). */
  param: string;
  /** The friendly label (falls back to `param`). */
  label: string;
  /** The grounded reason — e.g. "widest declared range (0.1–2.0, ~19 steps)". */
  reason: string;
}

/** `POST /ai/explain` response — `source` is "deterministic" when the gateway is off. */
export interface ExplainResponse {
  request: ExplainRequest["request"];
  text: string;
  source: "deterministic" | "ai";
  /** Ranked picks for `propose_sweep` (empty for `explain_score`). */
  suggestions?: SweepSuggestion[];
}

/**
 * The FE-persisted proposal queue item (`Figure.aiProposals[]`).
 *
 * Derived from a {@link HelperTurn}'s recompute actions + their staged param delta.
 * It is the durable record of "the AI suggested setting <target> to <value>", and
 * the source the banner rows + the figure-data ✨ markers render from (the marker is
 * "proposed" hollow / "staged" filled — a PRE-COMMIT state read from THIS queue). Lifecycle:
 *   proposed  — surfaced in the pending-changes banner (✨ hollow), NOT yet staged.
 *   accepted  — staged into the figure-data params (✨ "staged"; counted; the single
 *               explicit re-run posts it through /ai/apply).
 * "Applied" is not a stored status here — once a re-run lands, the durable proof is the
 * produced figure's `provenance.actions[]`, which the Activity-feed History renders as the
 * "applied" marker (the figure-data control markers, by contrast, read THIS pre-commit queue
 * and are emptied on re-run). The accepted proposal is consumed. Reverting drops the staged
 * value back to base and returns the proposal to `proposed`.
 */
export interface AiProposal {
  /** Stable id (the proposed action's id) — the revert/marker lookup key. */
  id: string;
  type: AiActionType;
  tier: ActionTier;
  status: "proposed" | "accepted";
  /** The param key this proposal stages (recompute actions); absent for pure-cosmetic. */
  paramKey?: string;
  /** The value the AI proposes for `paramKey` (stringly-typed to match SkillParams). */
  value?: string | number | boolean;
  /** The AI's one-line reason — shown in the banner row + the marker tooltip. */
  rationale?: string;
  // --- attribution (mirrors the AiAction tag this proposal will be applied under) ---
  actor: string;
  model?: string;
  prompt?: string;
}
