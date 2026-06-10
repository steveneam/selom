/**
 * Project-store domain types for the command center.
 *
 * These are intentionally shaped to match the planned Supabase schema
 * (docs/command-center/design.md §5) so the later swap from the localStorage mock
 * to a Supabase-backed `ProjectStore` is a backend-impl change, not a FE rewrite.
 * No component imports Supabase directly — everything goes through `ProjectStore`.
 */

export type Modality = "scRNA-seq" | "bulk RNA-seq" | "proteomics" | "unknown";

export type GuardrailLevel = "info" | "warn" | "error";

export interface Guardrail {
  level: GuardrailLevel;
  /** One-line "what" + the implied fix; surfaced before any figure (PRODUCT.md). */
  msg: string;
}

/** Ingest + QC report produced on upload (mock now → `POST /upload`, phase B2). */
export interface QcReport {
  detectedModality: Modality;
  nObs: number;
  nVar: number;
  /** The cleaning recipe applied to reach an analysis-ready baseline. */
  cleaning: string[];
  guardrails: Guardrail[];
}

/** One uploaded file. Maps to `datasets`. */
export interface Dataset {
  id: string;
  projectId: string;
  filename: string;
  modality: Modality;
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

/** A produced figure reference. Maps to `figures` (spec stored by the editor). */
export interface FigureRef {
  id: string;
  projectId: string;
  datasetId?: string;
  skillId?: string;
  title: string;
  createdAt: number;
}

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
  figures: FigureRef[];
}
