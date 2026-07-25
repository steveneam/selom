"use client";

import { useSyncExternalStore } from "react";
import { api } from "@/lib/api/client";
import { WriteQueue, type SyncStatus } from "@/lib/api/write-queue";
import type { Dataset, DatasetSource, Figure, GeneSet, Modality, Project, ProjectState, SkillInstall } from "./types";

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

/**
 * Cloud-import provenance off the wire (`datasets.source`, stamped by `routers/cloud.py`).
 *
 * The mapper used to drop this field entirely, so a dataset streamed in from Google Drive arrived in
 * the FE indistinguishable from one dragged off the desktop — the provenance existed in the database
 * and died at the boundary (findings B14 · B16). Defensive because `source` is a free-form JSON
 * column: anything without a `provider` is not provenance and is discarded rather than rendered as a
 * half-empty chip.
 */
function fromApiDatasetSource(v: unknown): DatasetSource | undefined {
  if (!v || typeof v !== "object" || Array.isArray(v)) return undefined;
  const r = v as Record<string, unknown>;
  const provider = typeof r.provider === "string" ? r.provider.trim() : "";
  if (!provider) return undefined;
  return {
    provider,
    ref: typeof r.ref === "string" ? r.ref : "",
    fetchedAt: typeof r.fetched_at === "string" ? r.fetched_at : undefined,
  };
}

/**
 * QC off the wire (`datasets.qc`) — a free-form JSON column holding TWO different shapes.
 *
 * `POST /datasets` (the metadata-only twin) stores the FE's own {@link QcReport}, so a round-trip
 * gives back exactly what was sent. But the real upload path stores something else entirely:
 * `uploads/service.py::materialize_dataset` stamps the ENGINE's QcReport
 * (`{ran, ok, flags, stats, blocked}`), which has no `nObs`/`nVar` at all. Two same-named types,
 * one column.
 *
 * The mapper used to `as`-cast the column straight into `Dataset["qc"]`, which told TypeScript the
 * engine's shape had the fields it does not. The result was a hard runtime crash on Selom's PRIMARY
 * flow — drop a file → `uploadDataset` → `addUploadedDataset` → the workrail renders `DatasetRow`
 * → `dataset.qc.nObs.toLocaleString()` → *Cannot read properties of undefined*, and the whole app
 * goes to the error overlay (same call in `data-panel.tsx`). It never showed up in testing because
 * `dev:mock` skips `uploadDataset` entirely (`if (!mockMode)`), so the mock only ever produced the
 * client shape [[verify-on-real-data-not-mock]] [[mock-must-mirror-backend-contract]].
 *
 * So: adopt the column only when it really is the FE's report. The engine's is not a lesser version
 * of it — it is a different record, and the FE's arrives moments later from `/data/inspect` via
 * `qcFromInspect` (`updateDatasetProfile`). Dropping it means the rail reads the plain modality for
 * a beat instead of dying.
 */
function fromApiDatasetQc(v: unknown): Dataset["qc"] {
  if (!v || typeof v !== "object" || Array.isArray(v)) return undefined;
  const r = v as Record<string, unknown>;
  // `nObs`/`nVar` are what every consumer formats, and they are required on the FE type — so they
  // are the honest discriminator between the two shapes.
  if (typeof r.nObs !== "number" || typeof r.nVar !== "number") return undefined;
  return v as Dataset["qc"];
}

export function fromApiDataset(r: Record<string, unknown>): Dataset {
  return {
    id: r.id as string, projectId: r.project_id as string, filename: (r.filename as string) || "data",
    label: (r.label as string) || undefined, modality: (r.modality as Modality) || "unknown",
    currentSha256: (r.current_sha256 as string) || undefined,
    // Server-derived "has stored bytes" (WS2.1): a `ready` row with an upload/parsed key came through
    // the real intake flow → runs use run-from-dataset_id. A metadata-only `addDataset` row is `ready`
    // with NO key → false. Recomputed on every reconcile, so it stays correct across reload.
    uploaded: r.status === "ready" && Boolean(r.upload_s3_key || r.parquet_s3_key),
    qc: fromApiDatasetQc(r.qc),
    source: fromApiDatasetSource(r.source),
    createdAt: ms(r.created_at),
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
