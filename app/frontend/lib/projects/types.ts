/**
 * Project-store domain types for the command center.
 *
 * These are intentionally shaped to match the planned Supabase schema
 * (docs/command-center/design.md §5) so the later swap from the localStorage mock
 * to a Supabase-backed `ProjectStore` is a backend-impl change, not a FE rewrite.
 * No component imports Supabase directly — everything goes through `ProjectStore`.
 */

import type { FigureSpec } from "@/lib/figure-spec";
import type { DataCheck, FigureLegend, SkillGuardrail, SkillMethods, SkillProvenance, StatsTable } from "@/lib/skills-api";
import type { DataFit } from "@/lib/reproduction/data-fit";

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

/** Ingest + QC report produced on upload (mock now → `POST /upload`, phase B2). */
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
  qc?: QcReport;
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
  table?: StatsTable;          // the Statistics result (wired in S2)
  dataCheck?: DataCheck;       // the is-my-data-clean verdict + routing for this run (P1c/P3a)
  dataFit?: DataFit;           // the data-fit verdict + confidence band for this run (Slice 2)
  // lineage / versioning
  parentFigureId?: string;     // set on a fork / variant / re-run
  variantLabel?: string;       // e.g. "resolution = 1.0"
  frozen?: boolean;            // the "paper" tag (S3)
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
