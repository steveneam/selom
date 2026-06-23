import type { CleaningStep, Guardrail, Modality, QcReport } from "@/lib/projects/types";
import type { DataQcReport, DataRouting } from "@/lib/skills-api";

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

interface InspectResponse {
  filename: string;
  kind: string;
  profile: DataProfile;
  cleaning_plan: CleaningPlan;
  qc: DataQcReport | null;
  routing: DataRouting | null;
}

export interface InspectResult {
  kind: string;
  profile: DataProfile;
  plan: CleaningPlan;
  qc: DataQcReport | null;
  routing: DataRouting | null;
}

/** Override choices the user can force (the L3 layer). `erg` rides the `profile` param; the
 *  engine Kinds ride `hint`. */
export type DataTypeOverride = "erg" | "sc_counts" | "bulk_counts" | "de_results" | "proteomics" | "generic_table";

/** Inspect a dropped file against the live engine. `override` is the user's explicit data-type
 *  choice. Returns `null` on any failure (fail-soft). */
export async function inspectData(file: File, override?: DataTypeOverride): Promise<InspectResult | null> {
  try {
    const fd = new FormData();
    fd.append("matrix", file);
    const params = new URLSearchParams();
    if (override === "erg") params.set("profile", "erg");
    else if (override) params.set("hint", override);
    const qs = params.toString();
    const res = await fetch(`/api/data/inspect${qs ? `?${qs}` : ""}`, { method: "POST", body: fd });
    if (!res.ok) return null;
    const body = (await res.json()) as InspectResponse;
    if (!body?.profile || !body?.cleaning_plan) return null;
    return { kind: body.kind, profile: body.profile, plan: body.cleaning_plan, qc: body.qc, routing: body.routing };
  } catch {
    return null; // offline / dev:mock without a handler / uninspectable — caller falls back
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
