/**
 * The one-click "quick apply" chips — resolved, ranked, and de-duplicated against the real catalog.
 *
 * This is the deterministic substrate the route-stage AI composer (`<AskAi stage="route">`) sits on:
 * the chips are the system's *recommendation* of what to run, the composer is the say-it-in-words path.
 * Kept pure (no React) so the recommend-vs-favourites + dedup logic is unit-testable in isolation.
 */

import { getSkill } from "@/lib/catalog/seed";
import type { IntakeProposal } from "@/lib/intake/mock";

/** A resolved catalog skill (getSkill, narrowed to never-undefined). */
type CatalogSkill = NonNullable<ReturnType<typeof getSkill>>;

/**
 * De-duplicate by id, preserving first-seen order. A skill can be installed more than once, or recur
 * across proposal steps; without this the chips would render two children with the same React key
 * (`key={s.id}`) — unsupported, and visibly duplicated/omitted.
 */
export function dedupById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((it) => (seen.has(it.id) ? false : (seen.add(it.id), true)));
}

export interface QuickApply {
  /**
   * True when the picks are RECOMMENDED for the loaded dataset (derived from the proposal), false when
   * they are the popularity-ranked installed favourites (no proposal yet). Drives the row label so it
   * never overclaims — "Recommended for your data" only when it genuinely is.
   */
  dataAware: boolean;
  skills: CatalogSkill[];
}

/**
 * Pick the quick-apply chips.
 *
 * With a data proposal, these are the skills the engine RECOMMENDED for this dataset (its proposed
 * pipeline, in order) — a genuine, data-driven pick. With no proposal yet (or none of its steps
 * resolve to a runnable skill), fall back to the most-used installed favourites. Verified-only (only
 * Verified skills run today), de-duplicated by id, capped at four. Ids are resolved against the real
 * catalog, so a bare backend slug or a typo is dropped rather than rendered as a broken chip.
 */
export function pickQuickApply(
  proposal: IntakeProposal | null,
  installs: { id: string; skillId: string }[],
): QuickApply {
  const verified = (ids: string[]): CatalogSkill[] =>
    dedupById(
      ids
        .map((id) => getSkill(id))
        .filter((s): s is CatalogSkill => !!s && s.tier === "verified"),
    );

  const recommended = verified((proposal?.steps ?? []).map((s) => s.skillId));
  if (recommended.length > 0) return { dataAware: true, skills: recommended.slice(0, 4) };

  const favourites = verified(installs.map((i) => i.skillId)).sort(
    (a, b) => b.popularity - a.popularity,
  );
  return { dataAware: false, skills: favourites.slice(0, 4) };
}
