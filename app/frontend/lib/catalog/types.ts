/**
 * Skill Store catalog types (docs/command-center/design.md §3.1).
 *
 * `SkillCatalogEntry` is the union of what bioSkills / ClawBio expose plus Selom's
 * runtime metadata. The mock seed (./seed.ts) stands in for the full ~600-skill
 * catalog; the live `GET /skills` / `GET /skills/{id}` (phase B1) returns the same
 * shape, so the Store UI is registry-driven and swaps without change.
 */

export type SkillSource = "selom" | "clawbio" | "bioskills";

/** Verified = a server-side runner exists and runs now. Community = browsable + */
/** installable-as-intent; runs later in a sandbox (design §6). */
export type SkillTier = "verified" | "community";

export type SkillStatus = "production" | "beta" | "community";

export type SkillEngine = "python" | "r" | "agent-sandbox";

export interface SkillCatalogEntry {
  /** Namespaced id: `<source>.<slug>`. */
  id: string;
  name: string;
  summary: string;
  source: SkillSource;
  /** Category from the source taxonomy (kebab-case). */
  category: string;
  /** Omics facets for filtering. */
  omics: string[];
  tier: SkillTier;
  status: SkillStatus;
  engine: SkillEngine;
  inputFormats: string[];
  /** Other catalog ids this chains well with ("works well with…"). */
  chainsWith: string[];
  outputs: string[];
  license: string;
  provenance: { repo: string; path: string };
  version: string;
  /** Curation signal for sort (mock). */
  popularity: number;
}
