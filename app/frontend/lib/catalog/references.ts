/**
 * Skill-reference presentation helpers (docs/skill-references/spec.md).
 *
 * Pure logic for the Store "Skill Information" provenance card: resolve a reference to a
 * link (DOI → https://doi.org/<doi>, else the raw url, else none), label its type, and
 * decide whether a skill has any provenance worth showing. Kept in lib/ (node-env vitest)
 * so the rendering component (components/store/skill-detail.tsx) stays a thin consumer.
 */

import type { SkillCatalogEntry, SkillReference, SkillReferenceType } from "./types";

/** Human label per reference type — shown as a small tag beside each citation. */
const TYPE_LABELS: Record<SkillReferenceType, string> = {
  publication: "Publication",
  repo: "Repository",
  standard: "Standard",
  dataset: "Dataset",
  method: "Method",
  tool: "Tool",
};

export function referenceTypeLabel(type: string): string {
  return TYPE_LABELS[type as SkillReferenceType] ?? "Reference";
}

/**
 * Resolve a reference to its canonical link, or null when neither a DOI nor a URL is
 * present (the citation then renders as plain text — no dead link). A DOI wins so the
 * link is stable/citable; a bare DOI ("10.…") is expanded to the doi.org resolver.
 */
export function referenceHref(ref: Pick<SkillReference, "doi" | "url">): string | null {
  const doi = ref.doi?.trim();
  if (doi) {
    if (/^https?:\/\//i.test(doi)) return doi;
    return `https://doi.org/${doi.replace(/^doi:/i, "")}`;
  }
  const url = ref.url?.trim();
  if (url && /^https?:\/\//i.test(url)) return url;
  return null;
}

/** The "Authors · Year" trailing line for a citation, omitting absent parts. */
export function referenceMeta(ref: Pick<SkillReference, "authors" | "year">): string {
  return [ref.authors?.trim(), ref.year != null ? String(ref.year) : undefined]
    .filter(Boolean)
    .join(" · ");
}

/** True when a skill carries any provenance (background or ≥1 reference) → show the card. */
export function hasSkillInfo(
  skill: Pick<SkillCatalogEntry, "background" | "references">,
): boolean {
  return Boolean(skill.background?.trim()) || (skill.references?.length ?? 0) > 0;
}
