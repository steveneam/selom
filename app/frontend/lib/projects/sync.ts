"use client";

import { useSyncExternalStore } from "react";
import { api } from "@/lib/api/client";
import { WriteQueue, type SyncStatus } from "@/lib/api/write-queue";
import type { Dataset, Figure, GeneSet, Modality, Project, ProjectState, SkillInstall } from "./types";

/**
 * The API-sync layer behind `projectStore` (sub-spec §2/§3): the shared write queue, the snake↔camel
 * adapters, and the reconcile GET. The store applies changes to its in-memory cache synchronously
 * (unchanged interface) and routes the durable write through `queue` here.
 */

/** One process-wide write queue (shared with the workspace store at FE-2). */
export const queue = new WriteQueue();

const ms = (iso: unknown): number => {
  const t = typeof iso === "string" ? Date.parse(iso) : NaN;
  return Number.isFinite(t) ? t : Date.now();
};

// ── snake_case (wire) → camelCase (FE) ─────────────────────────────────────────────────────────
export function fromApiProject(r: Record<string, unknown>): Project {
  return { id: r.id as string, name: r.name as string, color: (r.color as string) || "#22d3ee",
           createdAt: ms(r.created_at) };
}

export function fromApiDataset(r: Record<string, unknown>): Dataset {
  return {
    id: r.id as string, projectId: r.project_id as string, filename: (r.filename as string) || "data",
    label: (r.label as string) || undefined, modality: (r.modality as Modality) || "unknown",
    currentSha256: (r.current_sha256 as string) || undefined,
    qc: (r.qc as Dataset["qc"]) || undefined, createdAt: ms(r.created_at),
  };
}

export function fromApiFigure(r: Record<string, unknown>): Figure {
  return {
    id: r.id as string, projectId: r.project_id as string,
    datasetId: (r.dataset_id as string) || undefined, skillId: (r.skill_id as string) || undefined,
    title: (r.title as string) || "Untitled figure",
    spec: (r.spec as Figure["spec"]) || undefined,
    provenance: (r.provenance as Figure["provenance"]) || undefined,
    methods: (r.methods as Figure["methods"]) || undefined,
    legend: (r.legend as Figure["legend"]) || undefined,
    guardrails: (r.guardrails as Figure["guardrails"]) || undefined,
    table: (r.table_stats as Figure["table"]) || undefined,
    dataCheck: (r.data_check as Figure["dataCheck"]) || undefined,
    dataFit: (r.data_fit as Figure["dataFit"]) || undefined,
    parentFigureId: (r.parent_figure_id as string) || undefined,
    variantLabel: (r.variant_label as string) || undefined,
    frozen: Boolean(r.frozen), createdAt: ms(r.created_at),
  };
}

export function fromApiInstall(r: Record<string, unknown>): SkillInstall {
  return { id: r.id as string, projectId: r.project_id as string, skillId: r.skill_id as string,
           installedAt: ms(r.installed_at) };
}

export function fromApiGeneSet(r: Record<string, unknown>): GeneSet {
  return {
    id: r.id as string, projectId: "", name: (r.name as string) || "Gene set",
    genes: (r.genes as string[]) || [], source: (r.source as string) || "",
    sourceLabel: (r.source_label as string) || "", license: (r.license as string) || "",
    createdFrom: (r.created_from as string) || undefined, createdAt: ms(r.created_at),
  };
}

// ── camelCase (FE) → snake_case (wire) ─────────────────────────────────────────────────────────
export function toApiFigure(f: Figure): Record<string, unknown> {
  return {
    id: f.id, project_id: f.projectId, dataset_id: f.datasetId ?? null, skill_id: f.skillId ?? null,
    title: f.title, spec: f.spec ?? null, provenance: f.provenance ?? null, methods: f.methods ?? null,
    legend: f.legend ?? null, guardrails: f.guardrails ?? null, table_stats: f.table ?? null,
    data_check: f.dataCheck ?? null, data_fit: f.dataFit ?? null,
    parent_figure_id: f.parentFigureId ?? null, variant_label: f.variantLabel ?? null,
    frozen: Boolean(f.frozen),
  };
}

export function toApiGeneSet(g: GeneSet): Record<string, unknown> {
  return { id: g.id, name: g.name, genes: g.genes, source: g.source, source_label: g.sourceLabel,
           license: g.license, created_from: g.createdFrom ?? null };
}

// ── reconcile: pull the server view (the authority) ────────────────────────────────────────────
/** GET every project-scoped collection in parallel and assemble a server `ProjectState`. The store
 *  merges this in (server wins by id, local-only rows kept). Only project-scoped installs belong to
 *  this store — workspace-wide installs (null project_id) are the workspace store's (FE-2). */
export async function reconcileFetch(): Promise<ProjectState> {
  const [pj, ds, fg, ins, gs] = await Promise.all([
    api.get<{ projects: Record<string, unknown>[] }>("/projects"),
    api.get<{ datasets: Record<string, unknown>[] }>("/datasets"),
    api.get<{ figures: Record<string, unknown>[] }>("/figures"),
    api.get<{ installs: Record<string, unknown>[] }>("/skill-installs"),
    api.get<{ gene_sets: Record<string, unknown>[] }>("/workspace/gene-sets"),
  ]);
  return {
    projects: (pj.projects ?? []).map(fromApiProject),
    datasets: (ds.datasets ?? []).map(fromApiDataset),
    figures: (fg.figures ?? []).map(fromApiFigure),
    installs: (ins.installs ?? []).filter((i) => i.project_id).map(fromApiInstall),
    geneSets: (gs.gene_sets ?? []).map(fromApiGeneSet),
  };
}

/** Reactive sync status (idle | saving | offline | error) for a non-blocking chip. */
export function useSyncStatus(): SyncStatus {
  return useSyncExternalStore(queue.subscribe, queue.getStatus, () => "idle" as SyncStatus);
}
