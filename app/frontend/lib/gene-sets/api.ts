"use client";

/**
 * Gene-set catalog client (gene-set builder Phase A · DECISIONS #11).
 *
 * Mirrors the live backend contract (app/backend/main.py):
 *   GET /gene-sets?q=&source=&limit=  -> { sources, results }  (lightweight cards)
 *   GET /gene-sets/{id}               -> card + member symbols + provenance
 * Reached through the /api/* proxy; the MSW mock (mocks/handlers.ts) mirrors it so the
 * "Gene Sets" surface works with the backend down (`npm run dev:mock`).
 */

/** One source in the corpus (GO · WikiPathways · curated). */
export interface GeneSetSource {
  key: string;
  label: string;
  license: string;
  n_sets: number;
}

/** A search-result card — deliberately omits the full member list (fetched per set). */
export interface GeneSetCard {
  id: string;
  name: string;
  source: string;
  source_label: string;
  license: string;
  size: number;
  sample_genes: string[];
  /** Source citation for attributed reference panels (e.g. "CiliaCarta — van Dam 2013"). */
  attribution?: string;
}

export interface GeneSetSearchResponse {
  sources: GeneSetSource[];
  results: GeneSetCard[];
}

export interface GeneSetDetail extends GeneSetCard {
  genes: string[];
  provenance: {
    source: string;
    source_label: string;
    license: string;
    set_name: string;
    n_genes: number;
  };
}

export async function searchGeneSets(
  q: string,
  source: string | null,
  limit = 60,
  signal?: AbortSignal,
): Promise<GeneSetSearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  if (source && source !== "all") params.set("source", source);
  const res = await fetch(`/api/gene-sets?${params.toString()}`, {
    headers: { accept: "application/json" },
    signal,
  });
  if (!res.ok) throw new Error(`GET /gene-sets -> ${res.status}`);
  const data = (await res.json()) as Partial<GeneSetSearchResponse>;
  return { sources: data.sources ?? [], results: data.results ?? [] };
}

export async function getGeneSet(id: string, signal?: AbortSignal): Promise<GeneSetDetail> {
  const res = await fetch(`/api/gene-sets/${encodeURIComponent(id)}`, {
    headers: { accept: "application/json" },
    signal,
  });
  if (!res.ok) throw new Error(`GET /gene-sets/${id} -> ${res.status}`);
  return (await res.json()) as GeneSetDetail;
}

/** Result of compiling several sets into one (gene-set builder Phase B). */
export interface GeneSetCompileResult {
  genes: string[];
  op: string;
  sources: { id: string; name: string; source_label: string; license: string; size: number }[];
  missing: string[];
  provenance: {
    op: string;
    n_in: number;
    n_out: number;
    n_remapped: number;
    n_unrecognized: number;
    normalized: boolean;
    licenses: string[];
  };
  name?: string;
}

export async function compileGeneSets(
  setIds: string[],
  op: "union" | "intersect",
  name?: string,
): Promise<GeneSetCompileResult> {
  const res = await fetch("/api/gene-sets/compile", {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify({ set_ids: setIds, op, name }),
  });
  if (!res.ok) throw new Error(`POST /gene-sets/compile -> ${res.status}`);
  return (await res.json()) as GeneSetCompileResult;
}

/** Source identity — a clean, dark-legible colour per source (color-not-only: always paired with the label). */
export const SOURCE_META: Record<string, { color: string }> = {
  go: { color: "#34d399" }, // emerald — Gene Ontology
  wikipathways: { color: "#60a5fa" }, // blue — WikiPathways
  curated: { color: "#a78bfa" }, // violet — Selom curated (owned)
};

export function sourceColor(source: string): string {
  return SOURCE_META[source]?.color ?? "#8b98a9";
}
