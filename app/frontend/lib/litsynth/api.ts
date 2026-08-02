"use client";

/**
 * lit-synthesizer client — the paper-level write-up outputs (docs/paper-outputs/spec.md §2).
 *
 * Six backend routes, all read-only from the FE's side, reached through the shared `/api` transport:
 *
 *   POST /methods/compose            an ordered list of skill runs -> ONE Methods section
 *   GET  /papers/{slug}/methods      the same, composed from a published reproduction's ledger
 *   GET  /papers/{slug}/legends      one paste-ready caption per in-scope analysis panel
 *   GET  /papers/{slug}/scorecard    JUST the derived scorecard (no panels/validations/goldens)
 *   GET  /citations/search           topical PubMed lookup — advisory, degrade-safe
 *   GET  /citations/by-doi           a DOI -> one bibliographic record — degrade-safe
 *
 * Every one of these shipped working and had **zero FE call sites** until this module
 * (`R-01` + `R-03` of docs/reachability/backlog.md).
 *
 * The two `/citations/*` routes are *advisory tier-3*: the backend degrades to an empty result with
 * `degraded: true` rather than raising, so a lookup can never break the write-up. This client keeps
 * that contract — it never invents a citation to fill a gap
 * ([[mock-fallback-never-fabricates-data]]).
 */

import { api } from "@/lib/api/client";
import type { Scorecard } from "@/lib/reproduction/types";

// ------------------------------------------------------------------------------------ wire types

/** One skill run in an analysis story — mirrors `litsynth.models.SkillRunRef`. */
export interface SkillRunRef {
  skill_id: string;
  params: Record<string, unknown>;
  /** Pins the narrative sequence; omitted -> the run's position in the list. */
  order?: number;
}

/** A composed Methods section — mirrors `litsynth.models.MethodsSection`. */
export interface MethodsSection {
  intro: string;
  /** Per-skill prose in run order (no per-paragraph attribution). */
  paragraphs: string[];
  /** intro + paragraphs + one Selom attribution sentence, space-joined. The paste target. */
  text: string;
  /** Deduped tool citations, first-seen order across the whole story. */
  citations: string[];
  modality: string;
  skill_ids: string[];
  degraded?: boolean;
}

/** One paste-ready figure caption — mirrors `litsynth.models.FigureLegend`. */
export interface FigureLegend {
  figure: string;
  panel: string;
  /** Paste-ready label the ledger's own numbering knows, e.g. "Figure 4e." */
  label: string;
  skill_id: string;
  text: string;
}

/** A structured bibliographic record — mirrors `litsynth.models.Citation`. Bibliographic fields
 *  only; `metadata_license` carries bioRxiv/medRxiv's per-record license (None for PubMed). */
export interface Citation {
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
  pmid: string | null;
  url: string | null;
  source: string;
  metadata_license: string | null;
}

/** `degraded` is true only when a consulted source raised — a clean "no hit" is not degraded. */
export interface CitationSearchResponse {
  results: Citation[];
  degraded: boolean;
}

export interface CitationByDoiResponse {
  citation: Citation | null;
  degraded: boolean;
}

export interface PaperLegendsResponse {
  slug: string;
  legends: FigureLegend[];
}

// ---------------------------------------------------------------------------------------- routes

/**
 * Compose ONE Methods section from an ordered sequence of skill runs.
 *
 * The user's-own-reproduction path: `runsFromLedger` derives the sequence from a driven run's
 * ledger, so a paper the user reproduced themselves gets the same prose a published one does.
 * Rejects an empty sequence client-side — the backend answers 400 for it, and there is nothing to
 * ask about.
 */
export async function composeMethods(
  runs: SkillRunRef[],
  opts: { modality?: string; dataset?: string | null } = {},
): Promise<MethodsSection> {
  if (runs.length === 0) throw new Error("composeMethods: at least one skill run is required");
  return api.post<MethodsSection>("/methods/compose", {
    runs,
    modality: opts.modality ?? "",
    dataset: opts.dataset ?? null,
  });
}

/** A published reproduction's ledger -> its paper-level Methods section. `modality` overrides the
 *  ledger's own declared modality for the intro framing. */
export async function getPaperMethods(slug: string, modality?: string): Promise<MethodsSection> {
  const q = modality ? `?modality=${encodeURIComponent(modality)}` : "";
  return api.get<MethodsSection>(`/papers/${encodeURIComponent(slug)}/methods${q}`);
}

/** One paste-ready caption per in-scope analysis panel, in ledger (figure) order. */
export async function getPaperLegends(slug: string): Promise<FigureLegend[]> {
  const data = await api.get<PaperLegendsResponse>(`/papers/${encodeURIComponent(slug)}/legends`);
  return data?.legends ?? [];
}

/**
 * JUST the derived scorecard for a published reproduction.
 *
 * Deliberately not `GET /papers/{slug}` — the reproducibility statement needs `score`, `tier`,
 * `n_in_scope` and `findings` and none of the panels, validations or goldens the full ledger
 * carries (~67 KB to render one sentence). See spec §2.
 */
export async function getPaperScorecard(slug: string): Promise<Scorecard> {
  return api.get<Scorecard>(`/papers/${encodeURIComponent(slug)}/scorecard`);
}

/**
 * Topical PubMed lookup for supporting references. Advisory: a blank query is a clean empty result
 * with no request, and the backend degrades to `[] + degraded:true` on any network/parse failure.
 * bioRxiv has no free-text search API, so `source: "biorxiv"` is an honest empty.
 */
export async function searchCitations(
  q: string,
  opts: { source?: "both" | "pubmed" | "biorxiv"; maxResults?: number; minYear?: number } = {},
): Promise<CitationSearchResponse> {
  if (!q.trim()) return { results: [], degraded: false };
  const params = new URLSearchParams({ q: q.trim() });
  if (opts.source) params.set("source", opts.source);
  if (opts.maxResults) params.set("max_results", String(opts.maxResults));
  if (opts.minYear) params.set("min_year", String(opts.minYear));
  return api.get<CitationSearchResponse>(`/citations/search?${params.toString()}`);
}

/** Resolve a DOI to one bibliographic record. A blank DOI is a clean empty (the backend 400s). */
export async function citationByDoi(
  doi: string,
  source: "both" | "pubmed" | "biorxiv" = "both",
): Promise<CitationByDoiResponse> {
  if (!doi.trim()) return { citation: null, degraded: false };
  const params = new URLSearchParams({ doi: doi.trim(), source });
  return api.get<CitationByDoiResponse>(`/citations/by-doi?${params.toString()}`);
}

// ------------------------------------------------------------------------------------ formatting

/**
 * One reference-list line from a structured Citation — "Authors. Title. Venue Year. doi:…".
 *
 * Honest about absence: every field is optional on the wire and a missing one is simply dropped,
 * never filled with a placeholder. Three or more authors collapse to "First et al." the way the
 * canonical tool citations in `companions/methods.py` already read.
 */
export function formatCitation(c: Citation): string {
  const parts: string[] = [];
  const authors = c.authors ?? [];
  if (authors.length === 1) parts.push(`${authors[0]}.`);
  else if (authors.length === 2) parts.push(`${authors[0]} & ${authors[1]}.`);
  else if (authors.length > 2) parts.push(`${authors[0]} et al.`);
  if (c.title) parts.push(c.title.replace(/\.\s*$/, "") + ".");
  const venueYear = [c.venue, c.year != null ? String(c.year) : ""].filter(Boolean).join(" ");
  if (venueYear) parts.push(`${venueYear}.`);
  if (c.doi) parts.push(`doi:${c.doi}`);
  return parts.join(" ").trim();
}

/** The whole reference list as one paste-able block, one entry per line. */
export function referenceBlock(citations: string[]): string {
  return citations.join("\n");
}

/** All legends as one paste-able block — "Figure 4e. <caption>", blank-line separated. */
export function legendBlock(legends: FigureLegend[]): string {
  return legends.map((l) => `${l.label} ${l.text}`).join("\n\n");
}

/**
 * The paste-ready **reproducibility statement** — the sentence a methods section carries to state
 * what was computationally reproduced and how well.
 *
 * Deliberately phrased as a property of the paper and its data, never as a grade of the user: the
 * two axes stay separate and the score is reported, not editorialised
 * (`lib/reproduction/types.ts` — a low score is a discovery, not a failure).
 * Returns "" when the scorecard has no rollup score, rather than a sentence with a hole in it.
 */
export function reproducibilityStatement(
  scorecard: Scorecard | null,
  opts: { tierLabel?: (tier: string) => string } = {},
): string {
  const score = scorecard?.score;
  if (!scorecard || !score || score.reproducibility == null) return "";
  const tier = opts.tierLabel ? opts.tierLabel(score.tier) : score.tier;
  const scored = score.n_scored;
  const inScope = score.n_in_scope;
  const panels = `${scored} of ${inScope} in-scope panel${inScope === 1 ? "" : "s"}`;
  // The two axes stay separate in the sentence too: when only one was scored, the closing clause
  // must not imply the other was measured.
  const scored2 = score.selom_confidence != null;
  const confidence = scored2 ? `, at a Selom confidence of ${score.selom_confidence}/100` : "";
  const axes = scored2
    ? "Reproducibility reflects the paper and its data; Selom confidence reflects the reconstruction."
    : "Reproducibility reflects the paper and its data, not the reconstruction.";
  return (
    `Figures were computationally reproduced from the deposited data using Selom. ` +
    `Across ${panels}, the reproducibility score was ${score.reproducibility}/100 ` +
    `(${tier})${confidence}. ${axes}`
  );
}
