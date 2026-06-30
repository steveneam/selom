/**
 * The "Recommended for your data" chips — the skills the engine RECOMMENDED for the loaded dataset,
 * resolved + verified + de-duplicated against the real catalog.
 *
 * Two sources, preferred in order (Slice 2 — data-aware routing):
 *   1. the dataset's persisted `/data/inspect` route result (`routing` + `dataFit`) — the REAL,
 *      data-fit-ranked recommendation for an inspected file. This is the data-driven path and it
 *      survives reload (it's read off the dataset, not an in-session proposal).
 *   2. a modality-based MOCK proposal (`proposeForModality`) — the fallback for demo/sample datasets
 *      that have no inspected file, so they still show recommendations (owner steer).
 *
 * Kept pure (no React) so the selection + dedup logic is unit-testable in isolation. Returns an empty
 * list when neither source yields a runnable skill; the caller then renders nothing — the row only
 * ever shows genuine recommendations, never a popularity list wearing a recommendation's name.
 */

import { getSkill } from "@/lib/catalog/seed";
import { proposeForModality, type IntakeProposal } from "@/lib/intake/mock";
import type { DataFitSummary } from "@/lib/intake/inspect";
import type { Modality } from "@/lib/projects/types";
import type { DataRouting } from "@/lib/skills/api";

/** A resolved catalog skill (getSkill, narrowed to never-undefined). */
type CatalogSkill = NonNullable<ReturnType<typeof getSkill>>;

/**
 * Normalize a backend skill slug to the catalog id. Engine routing steps are BARE slugs (`volcano`);
 * the catalog is keyed `selom.<slug>`. Mirrors `pickSuggestedSkill` / the route composer's onSelect —
 * without this a bare slug silently resolves to nothing (the ad453fe regression). Already-prefixed
 * ids (the mock proposal's `selom.deg`) pass through unchanged.
 */
function toCatalogId(skillId: string): string {
  return skillId.startsWith("selom.") ? skillId : `selom.${skillId}`;
}

/**
 * De-duplicate by id, preserving first-seen order. A skill can recur across steps; without this the
 * chips would render two children with the same React key (`key={s.id}`) — unsupported, and visibly
 * duplicated/omitted.
 */
export function dedupById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((it) => (seen.has(it.id) ? false : (seen.add(it.id), true)));
}

/**
 * Resolve a list of catalog ids → verified catalog skills, de-duplicated, capped at four. Ids that
 * don't resolve (a typo, a not-yet-cataloged slug) are dropped rather than rendered as broken chips.
 */
function resolveVerified(catalogIds: string[]): CatalogSkill[] {
  return dedupById(
    catalogIds
      .map((id) => getSkill(id))
      .filter((s): s is CatalogSkill => !!s && s.tier === "verified"),
  ).slice(0, 4);
}

/**
 * The data-fit-ranked recommendation from the real inspect route result. Walks `routing.steps` (the
 * engine's recommended pipeline order), normalizes each bare slug, drops any skill the data is a
 * CERTAIN mismatch for (`dataFit.fits[].compatible === false`), then resolves to verified skills.
 */
function recommendedFromRoute(routing: DataRouting | null, dataFit: DataFitSummary | null): CatalogSkill[] {
  if (!routing) return [];
  const gated = new Set(
    (dataFit?.fits ?? []).filter((f) => f.compatible === false).map((f) => f.skill_id),
  );
  return resolveVerified(
    routing.steps.filter((s) => !gated.has(s.skill_id)).map((s) => toCatalogId(s.skill_id)),
  );
}

/** The modality mock fallback — the proposal's steps (already `selom.`-keyed), resolved + verified. */
function recommendedFromProposal(proposal: IntakeProposal | null): CatalogSkill[] {
  return resolveVerified((proposal?.steps ?? []).map((s) => toCatalogId(s.skillId)));
}

/**
 * The skills recommended for this dataset, verified-only, de-duplicated, capped at four, in the
 * engine's recommended order.
 *
 * A dataset that was INSPECTED carries a real `routing` → its honest data-fit result is returned
 * AS-IS, even when empty: an inspected file that fits none of the routed analyses hides the row
 * ("your data fits none of these"), it is NEVER masked by the generic modality mock. The mock is the
 * fallback ONLY for a NOT-inspected dataset (demo/sample, or bytes lost) — a data-type-appropriate
 * list so demo data still shows chips (owner D3), not a popularity fallback (the module's honesty
 * promise — fe-review gap, 2026-07-01).
 */
export function recommendedSkills(
  route: { routing: DataRouting | null; dataFit: DataFitSummary | null } | null,
  modality: Modality | null,
): CatalogSkill[] {
  if (route?.routing) return recommendedFromRoute(route.routing, route.dataFit);
  return modality ? recommendedFromProposal(proposeForModality(modality, {})) : [];
}
