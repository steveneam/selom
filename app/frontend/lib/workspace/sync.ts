"use client";

import { api } from "@/lib/api/client";
import { fromApiGeneSet, queue, toApiGeneSet } from "@/lib/projects/sync";
import type { GeneSet } from "@/lib/projects/types";
import type { SavedPaper, SavedSupplement, WorkspaceSkill, WorkspaceState } from "./types";

/**
 * API-sync layer behind `workspaceStore` (sub-spec §2/§3). Shares the one process-wide write `queue`
 * and the gene-set adapters with the project store; adds the saved-paper (+supplements) and
 * workspace-skill mappings. Wire shape is snake_case; this is the single camel↔snake boundary.
 */

export { queue };

const ms = (iso: unknown): number => {
  const t = typeof iso === "string" ? Date.parse(iso) : NaN;
  return Number.isFinite(t) ? t : Date.now();
};

// ── snake_case (wire) → camelCase (FE) ─────────────────────────────────────────────────────────
function fromApiSupplement(r: Record<string, unknown>): SavedSupplement {
  return { id: r.id as string, filename: (r.filename as string) || "supplement",
           kind: (r.kind as SavedSupplement["kind"]) || "csv",
           size: (r.size_bytes as number) ?? undefined, addedAt: ms(r.created_at) };
}

export function fromApiPaper(r: Record<string, unknown>): SavedPaper {
  const ts = (r.tier_summary as { structured?: number; recovered?: number } | null) || null;
  return {
    id: r.id as string, filename: (r.filename as string) || "paper.pdf",
    doi: (r.doi as string) ?? null, pmid: (r.pmid as string) ?? null,
    title: (r.title as string) ?? null, authors: (r.authors as string[]) ?? null,
    venue: (r.venue as string) ?? null, year: (r.year as number) ?? null,
    volume: (r.volume as string) ?? null, issue: (r.issue as string) ?? null,
    pages: (r.pages as string) ?? null, isPreprint: Boolean(r.is_preprint),
    url: (r.url as string) ?? null,
    skills: (r.skills as string[]) || [], outOfScope: (r.out_of_scope as string[]) || [],
    figureCount: (r.figure_count as number) || 0,
    tierSummary: { structured: ts?.structured ?? 0, recovered: ts?.recovered ?? 0 },
    savedAt: ms(r.created_at),
    reproductionRunId: (r.reproduction_run_id as string) || undefined,
    dataMap: (r.data_map as Record<string, string>) || undefined,
    supplements: ((r.supplements as Record<string, unknown>[]) || []).map(fromApiSupplement),
  };
}

function fromApiWsSkill(r: Record<string, unknown>): WorkspaceSkill {
  return { id: r.id as string, skillId: r.skill_id as string, installedAt: ms(r.installed_at) };
}

// ── camelCase (FE) → snake_case (wire) ─────────────────────────────────────────────────────────
export function toApiPaper(p: SavedPaper): Record<string, unknown> {
  return {
    id: p.id, filename: p.filename, doi: p.doi ?? null, pmid: p.pmid ?? null, title: p.title ?? null,
    authors: p.authors ?? [], venue: p.venue ?? null, year: p.year ?? null, volume: p.volume ?? null,
    issue: p.issue ?? null, pages: p.pages ?? null, is_preprint: Boolean(p.isPreprint), url: p.url ?? null,
    skills: p.skills ?? [], out_of_scope: p.outOfScope ?? [], figure_count: p.figureCount ?? 0,
    tier_summary: p.tierSummary ?? null, reproduction_run_id: p.reproductionRunId ?? null,
    data_map: p.dataMap ?? null,
    supplements: (p.supplements ?? []).map((s) => ({ id: s.id, filename: s.filename, kind: s.kind, size: s.size ?? 0 })),
  };
}

export { fromApiGeneSet, toApiGeneSet };
export type { GeneSet };

// ── reconcile: pull the account-level view ─────────────────────────────────────────────────────
/** GET papers + gene sets + workspace-wide installs (project_id null). The store merges these in. */
export async function reconcileFetchWorkspace(): Promise<WorkspaceState> {
  const [pp, gs, ins] = await Promise.all([
    api.get<{ papers: Record<string, unknown>[] }>("/workspace/papers"),
    api.get<{ gene_sets: Record<string, unknown>[] }>("/workspace/gene-sets"),
    api.get<{ installs: Record<string, unknown>[] }>("/skill-installs"),
  ]);
  return {
    papers: (pp.papers ?? []).map(fromApiPaper),
    geneSets: (gs.gene_sets ?? []).map(fromApiGeneSet),
    skills: (ins.installs ?? []).filter((i) => !i.project_id).map(fromApiWsSkill),
  };
}
