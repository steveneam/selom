import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { DataFit } from "@/lib/reproduction/data-fit";
import type { BackendParamSpec } from "@/lib/catalog/params";
import type { AiAction } from "@/lib/ai/types";

/** Per-figure reproducibility bundle (backend provenance.py — charter B4). */
export interface SkillProvenance {
  skill: {
    id: string;
    version: string;
    title: string;
    engine: string;
    /** C5: the immutable param_spec for this skill_version, stamped at run so the figure is
     *  self-describing — the Figure-data Inputs seed from it with no describe round-trip.
     *  Optional: a figure run before C5 (or a mock without it) simply falls back to fetching. */
    param_spec?: BackendParamSpec;
  };
  params: Record<string, string | number | boolean>;
  input: { filename: string | null; sha256: string; n_bytes: number };
  environment: {
    python: string;
    platform: string;
    engine_policy: string;
    packages: Record<string, string>;
  };
  /**
   * AI Helpers (S5): the actor-tagged log of AI actions an assisted run was approved
   * under (backend provenance.build `actions[]`). Present ONLY on figures produced via
   * `/ai/apply`; absent on every human run (additive, non-breaking — the bundle stays
   * byte-identical otherwise, preserving the "AI compiles away" invariant). The ✨ marker
   * reads its tooltip from here; the Activity feed renders these entries.
   */
  actions?: AiAction[];
}

/** Auto methods-text (backend methods.py — charter B4). */
export interface SkillMethods {
  text: string;
  citations: string[];
}

/** Statistical / data-quality guardrail (backend guardrails.py — charter B4). */
export interface SkillGuardrail {
  level: "info" | "warn";
  code: string;
  title: string;
  detail: string;
}

/**
 * A tabular result a skill computes — the DE / enrichment / marker / correlation
 * table that becomes the Statistics artifact (Pillar 1). The backend returns it
 * alongside the figure (wired into the contract in S2, Decision D7); the durable
 * `Figure` record stores it so the Statistics node survives reload.
 */
export interface StatsTable {
  columns: string[];
  rows: (string | number)[][];
  title?: string;
  /**
   * L3 table synthesis (docs/records/table-synthesis/spec.md, S3): true when Selom re-shaped
   * this table from the figure's OWN output because the skill emits no native table —
   * a real computed value, not a digitized guess, but labelled distinctly in the UI.
   */
  synthesized?: boolean;
  /** Provenance note for a synthesized table (e.g. "figure"). */
  source?: string;
}

/** One honest data-quality signal from the engine QC (backend engine/qc.py QCFlag). */
export interface QcFlag {
  severity: "info" | "warn" | "block";
  code: string;
  message: string;
  /** A concrete next step — always present for a `block`/`warn` (E3: never a silent filter). */
  fix: string;
}

/** "Is-my-data-clean?" verdict (backend engine/qc.py QCReport). */
export interface DataQcReport {
  ran: boolean;
  ok: boolean;
  /** Any `block`-severity flag present (D-e5: warn + require override, not hard-refuse). */
  blocked: boolean;
  flags: QcFlag[];
  stats: Record<string, number | string>;
}

/** One suggested analysis step for a modality (backend engine/route.py SuggestedStep). */
export interface SuggestedStep {
  skill_id: string;
  role: string;
  reason: string;
}

/** Suggested skill pipeline for a classified DataBundle (backend engine/route.py DataRouting). */
export interface DataRouting {
  kind: string;
  steps: SuggestedStep[];
  confident: boolean;
  note: string;
}

/**
 * The is-my-data-clean verdict surfaced with a run (P1c/P3a) — the modality the engine
 * detected, the QC report, and the suggested pipeline for that modality. `qc`/`routing` are
 * null when the upload couldn't be inspected (fail-soft; `kind` is then "unknown").
 */
export interface DataCheck {
  kind: string;
  qc: DataQcReport | null;
  routing: DataRouting | null;
}

/** Auto figure-legend text (backend legends.py — the caption half of the Methods+legend layer). */
export interface FigureLegend {
  text: string;
}

export interface SkillRunResponse {
  figure: FigureSpec;
  // Publish-confidence bundle (B4). Optional so an older backend / a mock without it
  // still renders the figure; the panel just hides when absent.
  provenance?: SkillProvenance;
  methods?: SkillMethods;
  legend?: FigureLegend;
  guardrails?: SkillGuardrail[];
  // Statistics result (Pillar 1, Decision D7) — null for purely-visual skills.
  table?: StatsTable | null;
  // The is-my-data-clean verdict + suggested next steps for this run (P1c/P3a). Absent when
  // an older backend / mock omits it.
  dataCheck?: DataCheck;
  // The data-fit verdict for THIS run (Slice 2, product-agnostic engine/compat): is the uploaded
  // file the right + clean data for this skill — a 0-100 score + a confidence band. null when the
  // upload couldn't be inspected (fail-soft) or an older backend / mock omits it.
  dataFit?: DataFit | null;
}

/**
 * Thrown when the engine QC guardrail BLOCKS a run (HTTP 422, engine-spine spec §5 / E3 / D-e5):
 * the uploaded data has a `block`-severity problem (e.g. negative counts where raw integers are
 * required). The caller shows the flags + their fix hints and offers "review & run anyway" —
 * re-running with `override: true`. It is a warn-and-override, never a hard refuse (the user owns
 * their data).
 */
export class DataCheckError extends Error {
  readonly dataCheck: DataCheck;
  constructor(message: string, dataCheck: DataCheck) {
    super(message);
    this.name = "DataCheckError";
    this.dataCheck = dataCheck;
  }
}

export type SkillParams = Record<string, string | number | boolean>;

/**
 * Resolve a Skill Store catalog id to the backend's runnable skill id.
 *
 * Catalog ids are namespaced `<source>.<slug>` (lib/catalog/types.ts) for provenance,
 * but the backend registry is keyed by the bare slug — `skills/<slug>/skill.json`
 * (e.g. `selom.umap_scrna` → `umap_scrna`). Strip the known source prefix so the
 * `/api/skills/{id}/run` route resolves. Ids without a source prefix pass through.
 */
export function runtimeSkillId(catalogId: string): string {
  return catalogId.replace(/^(?:selom|clawbio|bioskills)\./, "");
}

/**
 * Run a skill on an uploaded file and return the figure + its publish-confidence bundle.
 *
 * Matches the live contract (app/backend/main.py): a one-shot multipart POST with
 * the file in field `matrix` and tuning params as query string, responding with
 * `{ figure, provenance, methods }`. The MSW mock (mocks/handlers.ts) mirrors it, so
 * this path works with the backend down (`npm run dev:mock`).
 */
export async function runSkill(
  skillId: string,
  file: File,
  params: SkillParams = {},
  /**
   * Optional design / sample sheet for bulk + time-course DE. The backend joins
   * it on sample id (overrides column-name inference) and keeps it out of
   * provenance (reserved `_design_path`). Sent as the multipart field `design`.
   */
  design?: File | null,
  /**
   * Run options. `override: true` re-runs past a `block`-severity QC verdict (the
   * "review & run anyway" affordance — engine-spine spec §5 / D-e5).
   */
  opts: { override?: boolean } = {},
): Promise<SkillRunResponse> {
  const fd = new FormData();
  fd.append("matrix", file);
  if (design) fd.append("design", design);

  const entries = Object.entries(params).map(([k, v]) => [k, String(v)] as [string, string]);
  if (opts.override) entries.push(["override", "true"]);
  const qs = new URLSearchParams(entries).toString();
  const url = `/api/skills/${encodeURIComponent(skillId)}/run${qs ? `?${qs}` : ""}`;

  const res = await fetch(url, { method: "POST", body: fd });
  return parseSkillRunResponse(res);
}

/**
 * Parse a skill-run HTTP response into a {@link SkillRunResponse} (or throw a friendly,
 * typed error). Shared by {@link runSkill} (POST /skills/{id}/run) and the AI gateway's
 * apply path (POST /ai/apply) — both route through the SAME `_execute_skill_run` body,
 * so they return the SAME shape and must surface failures the SAME way. One home for the
 * one-shot-body-read discipline (read once, branch off the parsed body) so the two callers
 * can never drift [[fetch-body-read-once-browser-verify]].
 */
export async function parseSkillRunResponse(res: Response): Promise<SkillRunResponse> {
  if (!res.ok) {
    // The response body is a one-shot stream — read it ONCE and share it across every branch
    // below (reading it twice throws "body already used", which silently swallowed the real
    // message before — a non-data_check 422 fell back to the generic text). null = non-JSON body.
    let body: { detail?: unknown } | null = null;
    try {
      body = (await res.json()) as { detail?: unknown };
    } catch {
      /* non-JSON error body */
    }
    // The "is-my-data-clean?" guardrail (HTTP 422): a structured block verdict the caller turns
    // into a reviewable card + a "run anyway" override (D-e5), not a generic failure.
    if (res.status === 422) {
      const blocked = readDataCheckBlock(body);
      if (blocked) throw blocked;
    }
    // A typed gate's `detail.message` (D1 data_contract_failed, C3 param_out_of_range) is a full,
    // self-framed sentence with its own next step — surface it AS-IS. Wrapping it in "Couldn't run …
    // Please try again." reads wrong (a data mismatch isn't fixed by retrying) and doubles the period.
    const d = body?.detail;
    if (d && typeof d === "object" && typeof (d as { message?: unknown }).message === "string") {
      throw new Error((d as { message: string }).message);
    }
    // Otherwise speak plainly and point at a next step. A bare string detail (a runner's terse
    // ValueError) rides inside the friendly frame; an opaque failure gets the generic text.
    let detail =
      res.status >= 500
        ? "the analysis service is temporarily unavailable"
        : `the request was rejected (${res.status})`;
    if (typeof d === "string") detail = d;
    throw new Error(`Couldn't run this skill — ${detail}. Please try again.`);
  }

  const json = (await res.json()) as Record<string, unknown> & Partial<SkillRunResponse>;
  if (!json.figure || !Array.isArray(json.figure.data)) {
    throw new Error("Server returned a malformed figure spec.");
  }
  return {
    figure: json.figure,
    provenance: json.provenance,
    methods: json.methods,
    // The run response names it `figure_legend`; the FE carries it as `legend`.
    legend: (json.figure_legend as FigureLegend | undefined) ?? undefined,
    guardrails: json.guardrails,
    table: json.table ?? null,
    dataCheck: (json.data_check as DataCheck | undefined) ?? undefined,
    dataFit: (json.data_fit as DataFit | null | undefined) ?? null,
  };
}

/** Map an already-parsed 422 body into a {@link DataCheckError} when it carries the engine's QC
 *  block verdict (`data_check_failed`). Takes the parsed body — NOT the Response — so the caller
 *  reads the one-shot stream once and shares it (re-reading it threw, swallowing the real message).
 *  Returns null for any other error shape (e.g. D1 `data_contract_failed`), which the caller then
 *  surfaces via its `detail.message`. */
function readDataCheckBlock(body: { detail?: unknown } | null): DataCheckError | null {
  const d = body?.detail as
    | { error?: string; message?: unknown; kind?: unknown; qc?: unknown; routing?: unknown }
    | undefined;
  if (d && typeof d === "object" && d.error === "data_check_failed") {
    const message =
      typeof d.message === "string" ? d.message : "This data has a blocking problem for analysis.";
    return new DataCheckError(message, {
      kind: String(d.kind ?? "unknown"),
      qc: (d.qc as DataQcReport | null) ?? null,
      routing: (d.routing as DataRouting | null) ?? null,
    });
  }
  return null;
}
