/**
 * The "Recommended for your data" chips — the skills the engine RECOMMENDED for the loaded dataset
 * (its proposed pipeline, in order), resolved + verified + de-duplicated against the real catalog.
 *
 * This is the deterministic substrate the route-stage AI composer (`<AskAi stage="route">`) sits on:
 * the chips are the system's recommendation of what to run, the composer is the say-it-in-words path.
 * Kept pure (no React) so the selection + dedup logic is unit-testable in isolation.
 *
 * Returns an empty list when there is no proposal (or none of its steps resolve to a runnable skill);
 * the caller then renders nothing — so the row only ever shows genuine, data-driven recommendations,
 * never a popularity list wearing a recommendation's name.
 */

import { getSkill } from "@/lib/catalog/seed";
import type { IntakeProposal } from "@/lib/intake/mock";

/** A resolved catalog skill (getSkill, narrowed to never-undefined). */
type CatalogSkill = NonNullable<ReturnType<typeof getSkill>>;

/**
 * De-duplicate by id, preserving first-seen order. A skill can recur across proposal steps; without
 * this the chips would render two children with the same React key (`key={s.id}`) — unsupported, and
 * visibly duplicated/omitted.
 */
export function dedupById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((it) => (seen.has(it.id) ? false : (seen.add(it.id), true)));
}

/**
 * The skills recommended for this dataset, from the proposal. Verified-only (only Verified skills run
 * today), de-duplicated by id, capped at four, in the engine's proposed order. Ids resolve against the
 * real catalog, so a bare backend slug or a typo is dropped rather than rendered as a broken chip.
 * Empty when there is no proposal — the caller hides the row entirely.
 */
export function recommendedSkills(proposal: IntakeProposal | null): CatalogSkill[] {
  return dedupById(
    (proposal?.steps ?? [])
      .map((s) => getSkill(s.skillId))
      .filter((s): s is CatalogSkill => !!s && s.tier === "verified"),
  ).slice(0, 4);
}
