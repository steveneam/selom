/**
 * Pure derivation helpers for the AI-proposal queue (S5).
 *
 * The banner's author-partitioned counter and the figure-data ✨ markers are DERIVED —
 * single source of truth = the staged-vs-base param diff + the accepted-proposal author
 * map. No stored counter to drift. These functions are pure (no React, no store) so the
 * counter/marker state machine is unit-testable in isolation.
 */

import type { SkillParams } from "@/lib/skills/api";
import type { AiAction, AiActionType, AiProposal, HelperTurn } from "./types";

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
 * The actor-tagged action log to POST to `/ai/apply` — built from the ACCEPTED proposals,
 * stamping the client-side approval (`approved_by` / `approved_at`). The backend requires a
 * non-empty list with each entry actor-tagged (`{actor:"ai", type, target}`), else 400.
 */
export function approvedActions(
  proposals: AiProposal[],
  base: SkillParams,
  staged: SkillParams,
  approvedBy: string,
  approvedAt: string,
): AiAction[] {
  return proposals
    .filter((p) => p.status === "accepted")
    // Only tag a param as AI-authored when the AI's value is STILL the staged one. If the user
    // hand-edited the control after accepting, authorOf() flips to "user" (the live ✨ marker drops
    // too) — emitting an AI action here would mis-attribute the human's value to the AI in the
    // immutable provenance.actions[] audit trail. Param-less (cosmetic) actions pass through.
    .filter((p) => p.paramKey === undefined || authorOf(p.paramKey, base, staged, proposals) === "ai")
    .map((p) => ({
      action_id: p.id,
      actor: p.actor || "ai",
      type: p.type,
      target: p.paramKey ?? "",
      prompt: p.prompt ?? "",
      model: p.model ?? "",
      approved_by: approvedBy,
      approved_at: approvedAt,
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
