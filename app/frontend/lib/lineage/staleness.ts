/**
 * Staleness engine (Pillar 1 — liveness & lineage).
 *
 * A figure stores the provenance bundle it was computed from (input hash, params,
 * skill version, environment) — that bundle IS the staleness trigger-set. This pure
 * function diffs a figure's stored trigger-set against the CURRENT one ("live") and
 * reports whether the figure is stale and which factor diverged. It never blocks
 * anything — staleness is advisory (the badge + an explicit Re-run).
 *
 * Gating policy (spec Decision D1 — recommended default, reversible here):
 *   • data   (input sha256 ≠)        → gates. Any change counts; we can't cheaply
 *                                       tell append from replace, so honest
 *                                       over-flagging beats silent drift (D2).
 *   • params (≠)                     → gates.
 *   • skill  (major/minor bump)      → gates; a patch bump is ignored.
 *   • env    (≠)                     → info only, NEVER gates (too noisy on a dev box).
 *
 * Propagation is free (D2): each figure stores its own input hash, so a changed
 * dataset flags every figure built on it without any cascade engine.
 */
import type { Figure } from "@/lib/projects/types";
import type { SkillProvenance } from "@/lib/skills/api";

export type StaleFactor = "data" | "params" | "skill" | "env";

export interface StaleReason {
  factor: StaleFactor;
  /** Stable before/after for the badge — e.g. "params: {a:1} → {a:2}". */
  was: string;
  now: string;
}

export interface StalenessResult {
  stale: boolean;
  reasons: StaleReason[];
}

/**
 * The current trigger-set to diff a figure's stored provenance against. Each field
 * is optional: an absent field means "unknown / can't compare" → that factor is
 * skipped, never flagged. The caller assembles this from the dataset's current bytes,
 * the params a re-run would use, the skill's current registry version, and the env.
 */
export interface LiveTriggerSet {
  sha256?: string;
  params?: Record<string, string | number | boolean>;
  skillVersion?: string;
  /** Coarse env signature (python|platform|engine_policy); info-only, never gates. */
  env?: string;
}

/** Stable JSON for an order-independent params comparison + readable display. */
function stableParams(o: Record<string, string | number | boolean> | undefined): string {
  if (!o) return "{}";
  const out: Record<string, string | number | boolean> = {};
  for (const k of Object.keys(o).sort()) out[k] = o[k];
  return JSON.stringify(out);
}

/** Abbreviate a long hash for the badge. */
function shortHash(h: string): string {
  return h.length > 12 ? `${h.slice(0, 12)}…` : h;
}

/** A coarse env fingerprint — packages are intentionally excluded (too noisy). */
export function envSignature(env: SkillProvenance["environment"] | undefined): string {
  if (!env) return "";
  return [env.python, env.platform, env.engine_policy].filter(Boolean).join("|");
}

const SEMVER = /^(\d+)\.(\d+)\.(\d+)/;

/**
 * Does a skill version change gate? Major/minor bumps gate; a patch-only bump is
 * ignored (D1). Non-semver versions fall back to plain inequality (any change gates).
 */
export function skillVersionGates(was: string, now: string): boolean {
  if (was === now) return false;
  const a = SEMVER.exec(was.trim());
  const b = SEMVER.exec(now.trim());
  if (!a || !b) return true; // non-semver → honest over-flag on any difference
  return a[1] !== b[1] || a[2] !== b[2]; // major or minor differs → gate; patch-only → no
}

/**
 * Diff a figure's stored provenance bundle against the live trigger-set.
 * Returns `stale` (any *gating* factor diverged — env is advisory only) plus the
 * full list of diverged factors as `reasons`.
 */
export function figureStaleness(fig: Figure, live: LiveTriggerSet): StalenessResult {
  const reasons: StaleReason[] = [];
  const prov = fig.provenance;
  if (!prov) return { stale: false, reasons }; // no recorded trigger-set → can't assess

  // data — any input-hash change gates.
  if (live.sha256 != null && prov.input?.sha256 && live.sha256 !== prov.input.sha256) {
    reasons.push({ factor: "data", was: shortHash(prov.input.sha256), now: shortHash(live.sha256) });
  }

  // params — any change gates.
  if (live.params != null) {
    const was = stableParams(prov.params);
    const now = stableParams(live.params);
    if (was !== now) reasons.push({ factor: "params", was, now });
  }

  // skill — major/minor bump gates; patch ignored.
  if (live.skillVersion != null && prov.skill?.version && skillVersionGates(prov.skill.version, live.skillVersion)) {
    reasons.push({ factor: "skill", was: prov.skill.version, now: live.skillVersion });
  }

  // env — info only, never gates.
  if (live.env != null) {
    const was = envSignature(prov.environment);
    if (was && was !== live.env) reasons.push({ factor: "env", was, now: live.env });
  }

  const stale = reasons.some((r) => r.factor !== "env");
  return { stale, reasons };
}

/** A one-line human summary of why a figure is stale, for the badge tooltip. */
export function stalenessLabel(result: StalenessResult): string {
  const gating = result.reasons.filter((r) => r.factor !== "env").map((r) => r.factor);
  if (gating.length === 0) return "Up to date";
  const FACTOR_WORD: Record<StaleFactor, string> = {
    data: "data",
    params: "parameters",
    skill: "skill version",
    env: "environment",
  };
  const words = gating.map((f) => FACTOR_WORD[f]);
  return `Stale — ${words.join(" + ")} changed`;
}
