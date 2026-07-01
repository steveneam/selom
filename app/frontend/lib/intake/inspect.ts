import type { CleaningStep, Guardrail, Modality, QcReport } from "@/lib/projects/types";
import type { DataQcReport, DataRouting } from "@/lib/skills/api";
import type { ConfidenceBand, DataFit } from "@/lib/reproduction/data-fit";
import type { DesignHints } from "@/lib/intake/design";

/**
 * The real engine front door for own-data intake — `POST /api/data/inspect`.
 *
 * Replaces the filename-only `detectModality` + hardcoded `mockQcReport` guess: the backend
 * classifies the *actual* payload the layered way (file format → high-precision column keywords
 * → modality) and returns the dynamic cleaning plan for that type, so the cleaning pane is
 * correct (an ERG table is never force-fed gene-subset cleaning). The call is **fail-soft**:
 * any error (offline, dev:mock without a handler, an uninspectable file) returns `null` and the
 * caller falls back to the filename heuristic — the proven flow is never broken.
 */

/** One ranked data-type guess (backend engine/cleaning.py Candidate). */
export interface DataTypeCandidate {
  code: string; // an engine Kind or "erg"
  label: string;
  confidence: "certain" | "likely" | "unsure";
  /** The signal that proposed it: user | format | content | filename. */
  source: string;
  reason: string;
}

/** The layered data-type verdict (backend engine/cleaning.py DataProfile). The flat fields are
 *  the chosen (top) candidate; `candidates` is the full ranked list (drives the "or maybe Y"
 *  alternatives); `mismatch` is the soft nudge when the filename disagrees with the content. */
export interface DataProfile {
  code: string; // an engine Kind or "erg"
  label: string;
  confidence: "certain" | "likely" | "unsure";
  reason: string;
  overridden: boolean;
  candidates?: DataTypeCandidate[];
  mismatch?: string;
}

/** One proposed cleaning step (backend engine/cleaning.py CleaningStep; snake → camel here). */
interface RawCleaningStep {
  id: string;
  label: string;
  detail?: string;
  kind: "filter" | "transform" | "selection";
  obs_delta?: number | null;
  var_delta?: number | null;
}

/** The dynamic cleaning plan (backend engine/cleaning.py CleaningPlan). */
export interface CleaningPlan {
  kind: string;
  profile: string;
  applies: boolean;
  obs_label: string;
  var_label: string;
  n_obs: number;
  n_var: number;
  steps: RawCleaningStep[];
  note: string;
}

/**
 * The data-fit summary the engine returns for the dropped file (backend /data/inspect `data_fit`,
 * Slice 2): each routed skill scored against the actual data, plus the table shape the FE forwards
 * to /ai/propose as the data context (`columns` / `n_numeric_cols`). `fits` reuses the per-skill
 * {@link DataFit} wire shape (one source with the reproduction surface).
 */
export interface DataFitSummary {
  quality: number;
  confidence: ConfidenceBand;
  columns: string[];
  n_numeric_cols: number;
  fits: DataFit[];
}

interface InspectResponse {
  filename: string;
  kind: string;
  profile: DataProfile;
  cleaning_plan: CleaningPlan;
  qc: DataQcReport | null;
  routing: DataRouting | null;
  data_fit: DataFitSummary | null;
  design: DesignHints | null;
}

export interface InspectResult {
  kind: string;
  profile: DataProfile;
  plan: CleaningPlan;
  qc: DataQcReport | null;
  routing: DataRouting | null;
  /** Per-skill data-fit + table shape (Slice 2) — persisted on the dataset, drives the data-aware
   *  "Recommended for your data" chips + the route composer's data context. */
  dataFit: DataFitSummary | null;
  /** The deterministic DESIGN prefill for the intake questionnaire (Layer A ingest): candidate
   *  group/condition columns, levels + replicate counts, a control guess. Persisted on the dataset
   *  (client-only, like routing/dataFit) so the confirm-card re-prefills after reload. */
  design: DesignHints | null;
}

/** Override choices the user can force (the L3 layer). `erg` rides the `profile` param; the
 *  engine Kinds ride `hint`. */
export type DataTypeOverride = "erg" | "sc_counts" | "bulk_counts" | "de_results" | "proteomics" | "generic_table";

/** Inspect a dropped file against the live engine. `override` is the user's explicit data-type
 *  choice; `design` is an optional attached sample sheet — when present it becomes the design source
 *  of truth for the questionnaire prefill (followups #5, the reproducible mis-grouping fix). Returns
 *  `null` on any failure (fail-soft). */
export async function inspectData(
  file: File,
  override?: DataTypeOverride,
  design?: File | null,
): Promise<InspectResult | null> {
  try {
    const fd = new FormData();
    fd.append("matrix", file);
    if (design) fd.append("design", design);
    const params = new URLSearchParams();
    if (override === "erg") params.set("profile", "erg");
    else if (override) params.set("hint", override);
    const qs = params.toString();
    const res = await fetch(`/api/data/inspect${qs ? `?${qs}` : ""}`, { method: "POST", body: fd });
    if (!res.ok) return null;
    const body = (await res.json()) as InspectResponse;
    if (!body?.profile || !body?.cleaning_plan) return null;
    return {
      kind: body.kind, profile: body.profile, plan: body.cleaning_plan,
      qc: body.qc, routing: body.routing, dataFit: body.data_fit ?? null,
      design: body.design ?? null,
    };
  } catch {
    return null; // offline / dev:mock without a handler / uninspectable — caller falls back
  }
}

/** Summary of a multi-file combine (backend X-Combine-Summary header). */
export interface CombineSummary {
  filename: string;
  n_files: number;
  conditions: string[];
  rows: number;
  columns: string[];
  per_condition_n: Record<string, number>;
}

export interface CombineResult {
  /** The merged CSV as one File — turned into a normal dataset by the caller. */
  file: File;
  summary: CombineSummary;
}

/** Combine several single-condition ERG files into ONE multi-condition table — `POST
 *  /api/data/combine` (C6). Each file = a condition (its own `condition` column, e.g. C57/Rd10,
 *  else its filename stem). Returns the merged CSV as a File + a summary, or `null` on failure
 *  (fail-soft — the caller can fall back to single-file ingest). */
export async function combineData(files: File[]): Promise<CombineResult | null> {
  if (files.length < 2) return null;
  try {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    const res = await fetch("/api/data/combine", { method: "POST", body: fd });
    if (!res.ok) return null;
    const raw = res.headers.get("X-Combine-Summary");
    const summary = (raw ? JSON.parse(raw) : {}) as CombineSummary;
    const blob = await res.blob();
    const name = summary.conditions?.length
      ? `Combined ERG — ${summary.conditions.join(" + ")} (${files.length} files).csv`
      : summary.filename || `combined_${files.length}_files.csv`;
    return { file: new File([blob], name, { type: "text/csv" }), summary };
  } catch {
    return null;
  }
}

/** Map an engine Kind to the coarse FE Modality (drives icon colour + the intake questions).
 *  The precise label lives in `QcReport.profileLabel`; ERG / results / generic land on "unknown"
 *  here (a neutral bucket) but carry their real label. */
export function modalityFromKind(kind: string): Modality {
  switch (kind) {
    case "sc_counts":
      return "scRNA-seq";
    case "bulk_counts":
      return "bulk RNA-seq";
    case "proteomics":
      return "proteomics";
    default:
      return "unknown";
  }
}

/** Build the FE `QcReport` (what CleaningReport + the dataset list render) from a live inspect
 *  result — the engine cleaning plan + profile + QC flags, mapped to the FE shape. */
export function qcFromInspect(r: InspectResult): QcReport {
  const plan = r.plan;
  const steps: CleaningStep[] = plan.steps.map((s) => ({
    id: s.id,
    label: s.label,
    detail: s.detail,
    kind: s.kind,
    obsDelta: s.obs_delta ?? undefined,
    varDelta: s.var_delta ?? undefined,
  }));
  const nObsRaw = plan.n_obs;
  const nVarRaw = plan.n_var;
  const nObs = nObsRaw + steps.reduce((a, s) => a + (s.obsDelta ?? 0), 0);
  const nVar = nVarRaw + steps.reduce((a, s) => a + (s.varDelta ?? 0), 0);
  // QC flags → guardrails. Drop the `unclassified` info flag (redundant with — and, for a
  // recognized profile like ERG, contradictory to — the profile reason).
  const guardrails: Guardrail[] = (r.qc?.flags ?? [])
    .filter((f) => f.code !== "unclassified")
    .map((f) => ({
      level: f.severity === "block" ? "error" : f.severity === "warn" ? "warn" : "info",
      msg: f.fix ? `${f.message} ${f.fix}` : f.message,
    }));
  return {
    detectedModality: modalityFromKind(r.kind),
    nObs,
    nVar,
    nObsRaw,
    nVarRaw,
    cleaning: steps.length ? steps.map((s) => s.label) : [plan.note],
    cleaningSteps: steps,
    guardrails,
    profileLabel: r.profile.label,
    profileCode: r.profile.code,
    confidence: r.profile.confidence,
    reason: r.profile.reason,
    overridden: r.profile.overridden,
    candidates: r.profile.candidates ?? [],
    mismatch: r.profile.mismatch ?? "",
    applies: plan.applies,
    obsLabel: plan.obs_label,
    varLabel: plan.var_label,
  };
}
