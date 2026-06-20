/**
 * Shared paper-metadata representation — the ONE bibliographic shape + formatters used across
 * Skill Match, Reproduction, and Recover data (the umbrella's Paper anchor; spec
 * docs/workspace-library/spec.md §10).
 *
 * Per the "unify on the superior framework" rule: Skill Match's structured metadata — sourced by
 * our dogfooded PDF extractor (`POST /papers/extract` → OpenAlex/CrossRef/PubMed) — is the
 * canonical engine. Every paper-bearing surface conforms to THIS shape and renders through THESE
 * formatters, rather than inventing its own (the Reproduction surface used to bake the citation
 * into the `title` string; it now carries structured fields and renders here).
 *
 * `PaperMetadata` (skill-match), `SavedPaper` (workspace), and the Reproduction `PaperSummary`
 * all conform to `PaperMeta` structurally, so one formatter serves them all.
 */

/** The canonical bibliographic fields a paper-bearing surface shares. Every field is optional —
 *  metadata is enriched best-effort, so any part may be absent. */
export interface PaperMeta {
  title?: string | null;
  authors?: string[] | null;
  venue?: string | null;
  year?: number | null;
  volume?: string | null;
  issue?: string | null;
  pages?: string | null;
  doi?: string | null;
  pmid?: string | null;
  isPreprint?: boolean;
}

/** A compact author display: "Cioanca, Wooff +4" (first two surnames, then the remainder count). */
export function authorSummary(authors: string[] | null | undefined): string {
  if (!authors || authors.length === 0) return "";
  const surname = (a: string) => a.trim().split(/\s+/).pop() ?? a;
  if (authors.length <= 2) return authors.map(surname).join(", ");
  return `${surname(authors[0])}, ${surname(authors[1])} +${authors.length - 2}`;
}

/** A compact citation line: "Journal of Extracellular Vesicles · 12(12):e12393 · 2023" (skips
 *  missing parts). Accepts any object carrying the citation fields (PaperMetadata / SavedPaper /
 *  PaperSummary all qualify). */
export function citationLine(
  m: Pick<PaperMeta, "venue" | "volume" | "issue" | "pages" | "year"> | null | undefined,
): string {
  if (!m) return "";
  const vi = [m.volume, m.issue ? `(${m.issue})` : ""].filter(Boolean).join("");
  const volPart = [vi, m.pages].filter(Boolean).join(":");
  return [m.venue, volPart, m.year].filter(Boolean).join(" · ");
}

/** The canonical header citation line — Year · Journal · Volume(Issue) · Pages (skips missing
 *  parts). This is the owner's preferred order for the paper-header's third line, distinct from the
 *  compact card `citationLine`. Used by the shared `PaperMetaHeader`. */
export function headerCitation(
  m: Pick<PaperMeta, "year" | "venue" | "volume" | "issue" | "pages"> | null | undefined,
): string {
  if (!m) return "";
  const volIssue = m.volume ? `${m.volume}${m.issue ? `(${m.issue})` : ""}` : "";
  return [m.year, m.venue, volIssue, m.pages].filter(Boolean).join(" · ");
}
