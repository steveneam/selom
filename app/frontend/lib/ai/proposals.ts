/**
 * Pure derivation helpers for the AI-proposal queue (S5).
 *
 * The banner's author-partitioned counter and the figure-data ✨ markers are DERIVED —
 * single source of truth = the staged-vs-base param diff + the accepted-proposal author
 * map. No stored counter to drift. These functions are pure (no React, no store) so the
 * counter/marker state machine is unit-testable in isolation.
 */

import type { SkillParams } from "@/lib/skills/api";
import type { AiActionDelta, AiActionType, AiProposal, CapabilityGap, HelperTurn } from "./types";

/**
 * Result of extracting a proposed skill from a {@link HelperTurn} (route stage / SELECT mode).
 * `skillId` is non-null when the turn contains a successful `select_skill` result (status
 * `applied` or `staged`). `rationale` is the gateway's one-line reason for the pick (from
 * the matching `ProposedAction`). `gap` is set when the intent was coherent but no skill fitted.
 */
export interface SelectedSkillResult {
  skillId: string | null;
  rationale?: string;
  gap?: CapabilityGap;
}

/**
 * Extract the proposed skill id from a route-stage {@link HelperTurn} (SELECT mode).
 *
 * Priority:
 *   1. `turn.staged_params["_selected_skill"]` — the backend `_apply_select_skill` writes here.
 *   2. The `select_skill` result's `target`.
 * Both sources require the associated result to have status `applied` or `staged`.
 * Returns `{ skillId: null, gap }` when no valid selection was made; `gap` is populated
 * when a `no_fitting_skill` gap was recorded (the caller shows an honest note).
 */
export function selectedSkillFromTurn(turn: HelperTurn): SelectedSkillResult {
  const selectResult = turn.results.find((r) => r.type === "select_skill");

  if (selectResult && (selectResult.status === "applied" || selectResult.status === "staged")) {
    // Priority 1: staged_params["_selected_skill"]; fallback to result.target.
    const fromParams = turn.staged_params["_selected_skill"];
    const skillId = fromParams !== undefined ? String(fromParams) : selectResult.target;
    // Look up the gateway's rationale from the matching planned action.
    const rationale = turn.plan.actions.find((a) => a.id === selectResult.action_id)?.rationale;
    return { skillId, rationale };
  }

  // No successful selection — surface a no_fitting_skill gap if the gateway recorded one.
  const noFitGap = turn.gaps.find((g) => g.unmet === "no_fitting_skill");
  return { skillId: null, gap: noFitGap };
}

/** Figure-data controls stringify their values; the AI proposes typed. Compare as strings. */
function sameVal(a: unknown, b: unknown): boolean {
  return String(a) === String(b);
}

/** Author of a staged param key, or null when the key is NOT pending (staged === base).
 *  ai  — an accepted proposal targets it AND its staged value still equals the proposed value.
 *  user — pending but no matching accepted proposal (a manual edit, or an AI value you changed). */
export function authorOf(
  key: string,
  base: SkillParams,
  staged: SkillParams,
  proposals: AiProposal[],
): "ai" | "user" | null {
  if (staged[key] === base[key]) return null;
  const p = proposals.find(
    (p) => p.status === "accepted" && p.paramKey === key && p.value !== undefined,
  );
  return p && sameVal(p.value, staged[key]) ? "ai" : "user";
}

export interface PendingCounter {
  /** Total pending params (staged ≠ base) — equals the existing `fdDirty` count. */
  total: number;
  /** Pending params authored by the user (manual edits, or AI values since changed). */
  you: number;
  /** Pending params still carrying an accepted AI proposal's value. */
  ai: number;
}

/**
 * The derived, author-partitioned counter for the banner header (`N pending · X you · Y ✨`).
 * Reverting a key to base removes it from the diff → the count auto-decrements (the ✨ tally
 * drops if it was an AI row); reverting all → total 0 → the banner clears itself.
 */
export function pendingCounter(
  base: SkillParams,
  staged: SkillParams,
  proposals: AiProposal[],
): PendingCounter {
  const keys = new Set([...Object.keys(base), ...Object.keys(staged)]);
  let total = 0;
  let ai = 0;
  for (const k of keys) {
    if (staged[k] === base[k]) continue;
    total++;
    if (authorOf(k, base, staged, proposals) === "ai") ai++;
  }
  return { total, you: total - ai, ai };
}

/**
 * Map a {@link HelperTurn} into the FE proposal queue. Only RECOMPUTE actions that the spine
 * STAGED become queued proposals (status "proposed"): they need the user's accept + one explicit
 * re-run. Cosmetic actions that were APPLIED live are already reflected in `turn.figure_spec`, so
 * they don't enter the queue. Each proposal carries the AI's rationale + the actor tag (for the
 * marker tooltip), looked up by the stable per-turn action id.
 */
export function proposalsFromTurn(turn: HelperTurn): AiProposal[] {
  const rationaleById = new Map(turn.plan.actions.map((a) => [a.id, a.rationale]));
  const tagById = new Map(turn.provenance_actions.map((a) => [a.action_id, a]));
  const out: AiProposal[] = [];
  for (const r of turn.results) {
    if (r.status !== "staged") continue;
    const tag = tagById.get(r.action_id);
    out.push({
      id: r.action_id,
      type: r.type as AiActionType,
      tier: r.tier,
      status: "proposed",
      paramKey: r.target,
      value: turn.staged_params[r.target],
      rationale: rationaleById.get(r.action_id) ?? "",
      actor: tag?.actor ?? "ai",
      model: tag?.model,
      prompt: tag?.prompt,
    });
  }
  return out;
}

/**
 * The approved action **delta** to POST to `/ai/apply` — built from the ACCEPTED proposals. It carries
 * only "what to apply" (`{action_id, type, target, prompt}`); the backend re-derives the trusted
 * attribution (`actor` / `model` / `approved_by` / `approved_at`) itself at the NEXT#1 chokepoint, so
 * the FE deliberately does NOT stamp them (a client cannot forge a provenance tag). The backend requires
 * a non-empty list with each entry carrying `type` + `target`, else 400. See
 * docs/provenance-chokepoint/spec.md.
 */
export function approvedActions(
  proposals: AiProposal[],
  base: SkillParams,
  staged: SkillParams,
): AiActionDelta[] {
  return proposals
    .filter((p) => p.status === "accepted")
    // Only emit a param key whose staged value is STILL the AI's. If the user hand-edited the control
    // after accepting, authorOf() flips to "user" (the live ✨ marker drops too) — emitting it here
    // would have the server stamp the human's value as AI-authored in the immutable provenance.actions[]
    // audit trail. Param-less (cosmetic) actions pass through. (This author filter is part of selecting
    // the delta — it stays on the FE even though attribution is now stamped server-side.)
    .filter((p) => p.paramKey === undefined || authorOf(p.paramKey, base, staged, proposals) === "ai")
    .map((p) => ({
      action_id: p.id,
      type: p.type,
      target: p.paramKey ?? "",
      prompt: p.prompt ?? "",
    }));
}

/**
 * Overlay every ACCEPTED proposal's value onto a base param set. Re-hydrates the staged state from
 * the persisted queue so an accepted-but-not-yet-re-run proposal survives a reload coherently — the
 * banner's "staged" row, the derived counter, and the ✨ control marker all agree after a refresh
 * (without this, fdParams re-seeds from base on open and the accepted value is silently dropped).
 */
export function applyAcceptedProposals(base: SkillParams, proposals: AiProposal[]): SkillParams {
  const next = { ...base };
  for (const p of proposals) {
    if (p.status === "accepted" && p.paramKey !== undefined && p.value !== undefined) {
      next[p.paramKey] = p.value;
    }
  }
  return next;
}

// ── queue transitions (pure) ───────────────────────────────────────────────────
/** Mark a proposal accepted (the caller also stages its value into the figure-data params). */
export function acceptProposal(proposals: AiProposal[], id: string): AiProposal[] {
  return proposals.map((p) => (p.id === id ? { ...p, status: "accepted" } : p));
}
/** Return a proposal to "proposed" (on revert-to-base — keeps the suggestion offered). */
export function unacceptProposal(proposals: AiProposal[], id: string): AiProposal[] {
  return proposals.map((p) => (p.id === id ? { ...p, status: "proposed" } : p));
}
/** Drop a dismissed proposal entirely (it was never staged). */
export function dismissProposal(proposals: AiProposal[], id: string): AiProposal[] {
  return proposals.filter((p) => p.id !== id);
}
