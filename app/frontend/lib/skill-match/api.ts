"use client";

/**
 * Skill-Match data access + pure helpers (read-only dogfood — spec D12).
 *
 * Two backend calls via the /api proxy: POST /papers/extract (drop a PDF → its text layer + an
 * enriched bibliographic record) and POST /papers/route (the deterministic router → the feasibility
 * map). Plus the small pure helpers the UI and its vitest need: target parsing, the per-figure
 * in-scope skill set, the "needs Pro-AI review" predicate (the open-core upsell signal), and the
 * tier/attribution/oos display metadata. No LLM on this path — the map is deterministic and offline.
 */

import type { SavedPaper } from "@/lib/workspace/types";
import type { ExtractResult, FeasibilityMap, FigureRoute, PaperMetadata, RoutingTier } from "./types";

const ROUTE_URL = "/api/papers/route";
const EXTRACT_URL = "/api/papers/extract";

export function isSkill(target: string | null | undefined): boolean {
  return !!target && target.startsWith("skill:");
}

export function skillId(target: string | null | undefined): string {
  return isSkill(target) ? (target as string).slice("skill:".length) : "";
}

export function oosReason(target: string | null | undefined): string {
  return target && target.startsWith("oos:") ? target.slice("oos:".length) : "";
}

/** The figure's in-scope skill ids, ranked by evidence (candidates are pre-aggregated, unique). */
export function figureSkills(fr: FigureRoute): string[] {
  return fr.candidates.filter((c) => isSkill(c.target)).map((c) => skillId(c.target));
}

/** The threshold the backend uses to flag a figure for the (paid) L4 verifier. */
export const REVIEW_CONFIDENCE = 0.5;

/**
 * A figure the paid Pro-AI tier would verify: it needed the recovery sweep OR routed with a thin
 * top-two margin. This is the deterministic upsell signal — computed with zero AI.
 */
export function needsReview(fr: FigureRoute): boolean {
  return fr.tier === "recovered" || fr.confidence < REVIEW_CONFIDENCE;
}

/** How many of a map's in-scope figures the Pro tier would verify (the upsell count). */
export function reviewCount(map: FeasibilityMap): number {
  return map.figures.filter(needsReview).length;
}

export const TIER_META: Record<RoutingTier, { label: string; color: string; hint: string }> = {
  structured: {
    label: "Structured",
    color: "#34d399",
    hint: "Routed from a clean numbered figure caption (L1) — high precision.",
  },
  recovered: {
    label: "Recovered",
    color: "#f59e0b",
    hint: "Routed via the recovery sweep (L2) — a candidate for Pro AI verification.",
  },
};

export function tierMeta(tier: string) {
  return TIER_META[(tier as RoutingTier)] ?? TIER_META.recovered;
}

/**
 * A 5-step temperature scale for a 0–1 confidence — red → orange → amber → lime → green. Discrete
 * bands read more legibly than a continuous gradient (no muddy mid-range) and map to clear
 * very-low … very-high meaning, matching the app's discrete tier-colour convention.
 */
export function confidenceColor(conf: number): string {
  if (conf >= 0.85) return "#22c55e"; // green — very high
  if (conf >= 0.65) return "#84cc16"; // lime — high
  if (conf >= 0.45) return "#f59e0b"; // amber — medium
  if (conf >= 0.25) return "#f97316"; // orange — low
  return "#ef4444"; // red — very low
}

export const ATTRIBUTION_LABEL: Record<string, string> = {
  legend: "from the figure legend",
  results: "from a Results in-text reference",
  none: "no figure-level evidence",
};

/** Human labels for the out-of-scope modality reasons (the backend ships the bare slug). */
export const OOS_LABEL: Record<string, string> = {
  atac: "scATAC-seq",
  spatial: "spatial transcriptomics",
  grn: "gene-regulatory network",
  wet_lab: "wet-lab assay",
  not_deposited: "data not deposited",
};

export function oosLabel(reason: string): string {
  return OOS_LABEL[reason] ?? reason.replace(/_/g, " ");
}

export async function routePaper(text: string, paperId = ""): Promise<FeasibilityMap> {
  const res = await fetch(ROUTE_URL, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify({ text, paper_id: paperId }),
  });
  if (!res.ok) throw new Error(`POST ${ROUTE_URL} -> ${res.status}`);
  return (await res.json()) as FeasibilityMap;
}

/** Drop a PDF → its text layer (for routing) + an enriched bibliographic record (degrade-safe). */
export async function extractPaper(file: File): Promise<ExtractResult> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(EXTRACT_URL, { method: "POST", body });
  if (!res.ok) throw new Error(`POST ${EXTRACT_URL} -> ${res.status}`);
  return (await res.json()) as ExtractResult;
}

// Bibliographic formatters live in the shared paper-metadata module (the one representation used by
// Skill Match, Reproduction, and Recover data — spec §10). Re-exported here so existing imports keep
// working while the canonical home is `@/lib/paper/metadata`.
export { authorSummary, citationLine } from "@/lib/paper/metadata";

/**
 * A compact, realistic sample (a developing-retina multi-omic paper, Dorgau-shaped): an in-scope
 * scRNA figure plus spatial / scATAC / GRN / wet-lab figures — so the surface demonstrates the full
 * range (skill inventory, out-of-scope modalities, recovered-tier figures, and the upsell) offline.
 */
/**
 * Build the compact `SavedPaper` summary from the on-client routing result + metadata — what the
 * Workspace Library keeps so a paper is revisitable without re-dropping the PDF. Stores the L3 skill
 * inventory + per-figure tier rollup (NOT the full FeasibilityMap, spec D3) and NO PDF bytes/object
 * URL (spec I5). The store dedups idempotently on `doi || filename` (spec I3).
 */
export function toSavedPaper(
  map: FeasibilityMap,
  meta: PaperMetadata | null | undefined,
  filename: string,
): Omit<SavedPaper, "id" | "savedAt"> {
  return {
    filename,
    doi: meta?.doi ?? null,
    pmid: meta?.pmid ?? null,
    title: meta?.title ?? null,
    authors: meta?.authors ?? null,
    venue: meta?.venue ?? null,
    year: meta?.year ?? null,
    volume: meta?.volume ?? null,
    issue: meta?.issue ?? null,
    pages: meta?.pages ?? null,
    isPreprint: meta?.is_preprint ?? false,
    url: meta?.url ?? null,
    skills: map.skills,
    outOfScope: map.out_of_scope,
    figureCount: map.figures.length,
    tierSummary: map.tier_summary ?? { structured: 0, recovered: 0 },
  };
}

export const SAMPLE_TEXT = `Methods
Single-cell RNA-seq libraries were processed with CellRanger and analysed in Seurat. After
FindVariableFeatures (2000 HVG) we performed Harmony batch correction, computed a UMAP, applied
graph-based clustering, identified cluster markers with FindMarkers, and ordered cells along
pseudotime with Monocle 3. Spatial transcriptomics used 10x Visium. Chromatin accessibility was
profiled by scATAC-seq and analysed with Signac and chromVAR. Gene regulatory networks were inferred
with SCENIC+. Findings were validated by immunofluorescence and confocal microscopy.
Figure legends
Figure 1. Integrated UMAP of the developing human retina; dotplot of marker genes from FindMarkers;
pseudotime trajectory of the progenitors; heatmap of genes along pseudotime.
Figure 2. Spatial transcriptomics (Visium) of the retina with H&E staining section.
Figure 3. scATAC-seq differential accessibility; motif footprinting with chromVAR.
Figure 4. Gene regulatory networks inferred with SCENIC+; regulon activity.
Figure 5. Immunofluorescence validation; confocal microscopy of the ciliary margin.`;
