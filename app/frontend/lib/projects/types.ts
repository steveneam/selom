/**
 * Project-store domain types for the command center.
 *
 * These are intentionally shaped to match the planned Supabase schema
 * (docs/command-center/design.md §5) so the later swap from the localStorage mock
 * to a Supabase-backed `ProjectStore` is a backend-impl change, not a FE rewrite.
 * No component imports Supabase directly — everything goes through `ProjectStore`.
 */

import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { DataCheck, DataRouting, FigureLegend, SkillGuardrail, SkillMethods, SkillProvenance, StatsTable } from "@/lib/skills/api";
import type { DataFit } from "@/lib/reproduction/data-fit";
import type { DataFitSummary } from "@/lib/intake/inspect";
import type { DesignHints } from "@/lib/intake/design";
import type { AiProposal } from "@/lib/ai/types";

export type Modality = "scRNA-seq" | "bulk RNA-seq" | "proteomics" | "unknown";

export type GuardrailLevel = "info" | "warn" | "error";

export interface Guardrail {
  level: GuardrailLevel;
  /** One-line "what" + the implied fix; surfaced before any figure (PRODUCT.md). */
  msg: string;
}

/** One cleaning operation, with the effect it had on the matrix shape. */
export interface CleaningStep {
  id: string;
  label: string;
  detail?: string;
  /** filter = drops rows/cols; transform = rescales values; selection = flags features. */
  kind: "filter" | "transform" | "selection";
  /** Signed change to observation/feature counts (negative = removed). */
  obsDelta?: number;
  varDelta?: number;
}

/** Ingest + QC report produced on upload. Now sourced from the real engine `/data/inspect`
 *  (lib/intake/inspect.ts → qcFromInspect); the filename-only mock is the fail-soft fallback. */
export interface QcReport {
  detectedModality: Modality;
  /** Post-cleaning shape (analysis-ready baseline). */
  nObs: number;
  nVar: number;
  /** Raw shape as dropped, before any cleaning (for the before/after view). */
  nObsRaw?: number;
  nVarRaw?: number;
  /** The cleaning recipe applied to reach the baseline (display strings). */
  cleaning: string[];
  /** Structured, toggleable cleaning steps (before/after + edit-before-proceed). */
  cleaningSteps?: CleaningStep[];
  guardrails: Guardrail[];
  // --- engine data-type profile (lib/intake/inspect.ts), when classified live -------------
  /** Friendly data-type label from the layered detector ("ERG / electrophysiology",
   *  "Data table", "Bulk RNA-seq counts"…). Falls back to `detectedModality` when absent. */
  profileLabel?: string;
  /** Machine code for the profile (an engine Kind or "erg") — drives the override selector. */
  profileCode?: string;
  /** How sure the detector is: certain | likely | unsure. */
  confidence?: "certain" | "likely" | "unsure";
  /** The *why* (the layer that decided) — shown so the classification is transparent. */
  reason?: string;
  /** The full ranked guess list (engine candidates) — drives the "or maybe Y" alternatives. */
  candidates?: { code: string; label: string; confidence: "certain" | "likely" | "unsure"; source: string; reason: string }[];
  /** Soft nudge: the filename disagrees with a positive content signal (content still wins). */
  mismatch?: string;
  /** The user set the type explicitly — keep it sticky across a re-inspect, offer "reset to auto". */
  overridden?: boolean;
  /** Whether any matrix cleaning applies. False ⇒ the table is used as-is (no gene cleaning). */
  applies?: boolean;
  /** Axis labels for the detected type (cells/genes, samples/genes, rows/columns…). */
  obsLabel?: string;
  varLabel?: string;
}

/**
 * Where an imported dataset came from — the backend stamps this on `datasets.source` when a file is
 * streamed in from a cloud provider (`routers/cloud.py` → `repo.set_source`). Absent for a locally
 * dropped file, which is exactly the difference the UI has to show: without it a cloud-imported
 * dataset renders identically to a hand-dropped one, so its provenance is lost the moment it lands
 * (findings B14 · B16).
 *
 * SERVER-authoritative — mapped in `fromApiDataset`, refreshed on every reconcile, never invented by
 * the client.
 */
export interface DatasetSource {
  /** Backend registry provider id: "url" | "google" | "onedrive" | "dropbox". */
  provider: string;
  /** The reference the import ran against — a URL / s3:// URI, or a provider file id/path. */
  ref: string;
  /** ISO timestamp of the fetch, as stamped by the server. */
  fetchedAt?: string;
}

/** One uploaded file. Maps to `datasets`. */
export interface Dataset {
  id: string;
  projectId: string;
  filename: string;
  /** Optional user-set display name (Pillar 1 family rename); falls back to `filename`.
   *  Renaming a dataset propagates to its figures'/stats' source chips automatically,
   *  since those read the live name rather than copying it. */
  label?: string;
  modality: Modality;
  /**
   * sha256 of the dataset's CURRENT bytes — the "live" data version a figure's
   * stored input hash is diffed against (Pillar 1 staleness). A figure goes stale
   * when its `provenance.input.sha256` no longer matches this. (In the dogfood mock,
   * with no real bytes, it's a stable real-looking stand-in the client maintains.)
   */
  currentSha256?: string;
  /** True when this dataset's BYTES live in the object store (uploaded via the real intake flow —
   *  WS2.1), so a run uses run-from-dataset_id (no multipart re-upload) and it — plus any figure it
   *  produces — is re-runnable after reload with no re-upload prompt. False/undefined for a
   *  metadata-only dataset (`addDataset`) or a demo seed. Server-derived (status=ready + a stored key,
   *  see `fromApiDataset`), so it self-heals across a reconcile — not a fragile client-only flag. */
  uploaded?: boolean;
  /** Present ONLY once a real qc verdict exists (seed demo data, or a completed `/data/inspect`
   *  success) — a real dataset added via `addDataset` starts `undefined`. Never a fabricated
   *  stand-in: an in-flight or failed inspect is tracked separately via `inspectState`, so the UI
   *  can render an honest "Inspecting…" / "Couldn't inspect this file" instead of guessed dims. */
  qc?: QcReport;
  /** Cloud-import provenance stamped by the server (`datasets.source`); absent for a dropped file.
   *  Rendered on the dataset so an imported file never looks hand-dropped. */
  source?: DatasetSource;
  /** Whether a live `/data/inspect` is in flight ("pending") or has definitively failed ("failed")
   *  for this dataset. Undefined once `qc` is set (a success clears it) or before any inspect has
   *  run. Client-only UI state — not synced to the backend, not preserved across a server reconcile
   *  (self-heals on the next focus/hydrate rather than getting stuck mid-flight). */
  inspectState?: "pending" | "failed";
  /**
   * The data-aware route the engine computed for this dataset at inspect time (Slice 2) — the
   * suggested skill pipeline (`routing`) + the per-skill data-fit ranking and table shape
   * (`dataFit`). Persisted with the dataset (from `/data/inspect`) so the data-driven
   * "Recommended for your data" chips survive reload, and so the route composer can send the
   * dataset's columns/kind as data context. Optional → legacy datasets load unchanged.
   */
  routing?: DataRouting | null;
  dataFit?: DataFitSummary | null;
  /**
   * The deterministic DESIGN prefill for the intake questionnaire (Layer A ingest), from
   * `/data/inspect` — candidate group/condition columns + levels + replicate counts + a control
   * guess. Client-only (like `routing`/`dataFit`): persisted in the FE store, no backend column, so
   * the layered confirm-card re-prefills after reload (preserved across reconcile by `mergeDatasets`).
   */
  design?: DesignHints | null;
  createdAt: number;
}

/** A skill added to a project from the Store. Maps to `skill_installs`. */
export interface SkillInstall {
  id: string;
  projectId: string;
  skillId: string;
  installedAt: number;
}

/**
 * A saved gene set — the durable, provenance-stamped unit of the gene-set builder
 * (DECISIONS #11). Compiled/picked from the license-clean corpus and reusable across
 * the enrichment / volcano / heatmap skills. Maps to a future `gene_sets` table.
 */
export interface GeneSet {
  id: string;
  projectId: string;
  name: string;
  genes: string[];
  /** Source key (go / wikipathways / curated) or "compiled" once Phase B unions sources. */
  source: string;
  sourceLabel: string;
  license: string;
  /** The catalog id this was saved from, for re-fetch + provenance. */
  createdFrom?: string;
  createdAt: number;
}

/**
 * A produced figure — the durable record. Maps to `figures` (design §5).
 *
 * Pillar 1 (liveness & lineage) makes this the source of truth for the editable
 * `spec` + its provenance `bundle` (both were transient before — lost on reload).
 * That stored bundle IS the staleness trigger-set (input hash / params / skill
 * version / env). Lineage/version metadata lives HERE, never inside the spec.
 * All new fields are optional → legacy persisted figures (spec-less) still load.
 */
export interface Figure {
  id: string;
  projectId: string;
  datasetId?: string;
  skillId?: string;            // catalog id
  title: string;
  spec?: FigureSpec;           // the editable Plotly spec (was transient)
  provenance?: SkillProvenance;// the staleness trigger-set (was transient)
  methods?: SkillMethods;
  legend?: FigureLegend;       // paste-ready figure caption (P4c — the Methods+legend layer)
  guardrails?: SkillGuardrail[];
  // The Statistics result (wired in S2) — one table, or several (stats-tables spec D1/D6).
  // A server field: reconcile stays authoritative for it; this widens its type, not its ownership.
  table?: StatsTable | StatsTable[];
  dataCheck?: DataCheck;       // the is-my-data-clean verdict + routing for this run (P1c/P3a)
  dataFit?: DataFit;           // the data-fit verdict + confidence band for this run (Slice 2)
  // lineage / versioning
  parentFigureId?: string;     // set on a fork / variant / re-run
  variantLabel?: string;       // e.g. "resolution = 1.0"
  frozen?: boolean;            // the "paper" tag (S3)
  // AI Helpers (S5): the AI-proposed param changes queued against this figure — surfaced
  // in the pending-changes banner (✨), accepted into the figure-data params, then applied
  // by ONE explicit re-run. Additive + optional → legacy figures load unchanged. The
  // *applied* proof is the produced figure's `provenance.actions[]`, not this queue.
  aiProposals?: AiProposal[];
  createdAt: number;
}

/** @deprecated Use {@link Figure}. Kept as an alias during the Pillar-1 migration. */
export type FigureRef = Figure;

/** A project folder (the sidebar entries). Maps to `projects`. */
export interface Project {
  id: string;
  name: string;
  /** One of the chart token hues, for the folder dot + accent. */
  color: string;
  createdAt: number;
}

/** The full denormalized snapshot the mock store exposes to the UI. */
export interface ProjectState {
  projects: Project[];
  datasets: Dataset[];
  installs: SkillInstall[];
  figures: Figure[];
  geneSets: GeneSet[];
}
