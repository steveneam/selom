/**
 * Types for the Skill Keyword Index feasibility surface — mirrors the backend
 * `extract.routing.models.FeasibilityMap` (POST /papers/route). Only the fields the read-only
 * surface consumes are typed; the deterministic core ships every figure with a tier + confidence.
 */

export type Attribution = "legend" | "results" | "none";
export type RoutingTier = "structured" | "recovered";

export interface RoutingCandidate {
  /** "skill:<id>" (a live Selom skill) or "oos:<reason>" (an out-of-scope modality). */
  target: string;
  score: number;
}

export interface RouteVerdict {
  figure: string;
  verdict: string;
  target: string;
  confidence: number;
  note: string;
}

export interface FigureRoute {
  figure: string;
  candidates: RoutingCandidate[];
  top: string | null;
  in_scope: boolean;
  reason: string;
  confidence: number;
  attribution: Attribution;
  tier: RoutingTier;
  /** Optional L4 AI adjudication (fast-follow #2); null unless a gateway verified this figure. */
  ai: RouteVerdict | null;
}

/** Enriched bibliographic record from the backend (paper_metadata; any field may be absent). */
export interface PaperMetadata {
  title?: string | null;
  authors?: string[] | null;
  year?: number | null;
  venue?: string | null; // journal / source
  volume?: string | null;
  issue?: string | null;
  pages?: string | null;
  doi?: string | null;
  pmid?: string | null;
  url?: string | null;
  is_preprint?: boolean;
}

/** The POST /papers/extract response: the PDF's text layer (for routing) + its metadata. */
export interface ExtractResult {
  text: string;
  filename: string;
  metadata: PaperMetadata | null;
  provenance: { matched_by?: string | null; source?: string | null; degraded?: boolean };
}

export interface FeasibilityMap {
  paper_id: string;
  /** L3 paper-level inventory: every in-scope skill the paper needs (the core deliverable). */
  skills: string[];
  /** Out-of-scope modality reasons present (atac / spatial / grn / wet_lab / …). */
  out_of_scope: string[];
  figures: FigureRoute[];
  paper_targets: RoutingCandidate[];
  tier_summary: { structured: number; recovered: number };
  /** Method-nouns that routed to NO skill — the Skill Foundry backlog signal. */
  unmatched_terms: string[];
}
