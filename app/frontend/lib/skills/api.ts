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
  // Statistics result (Pillar 1, Decision D7) — null for purely-visual skills, and a LIST when the
  // skill computes more than one (docs/stats-tables/spec.md D1: a ranked-values table AND the
  // pairwise p-values behind the stars drawn on the figure). Narrow it with
  // `lib/skills/stats-tables.ts` `asTables`, never inline.
  table?: StatsTable | StatsTable[] | null;
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

/** One recommended parameter from the deterministic Auto-tune recommender (backend
 *  engine/recommend.py ParamRec). `scaled` is true only when a curated rule moved `value` off the
 *  static `default`; `why` is the plain-language reason. */
export interface ParamRec {
  key: string;
  value: string | number | boolean;
  default: string | number | boolean;
  why: string;
  scaled: boolean;
}

/** The full recommended param set for one skill (backend ParamRecs). */
export interface ParamRecs {
  skill_id: string;
  recs: ParamRec[];
  note: string;
}

/** The data DESCRIPTION forwarded to the recommender — never a verdict (mirrors the route composer's
 *  data-aware context). All optional; the server degrades a missing field to the static default. */
export interface RecommendContext {
  data_columns?: string[] | null;
  data_kind?: string | null;
  data_n_numeric_cols?: number | null;
  design?: unknown | null;
}

/** One applied recommendation: the key + its OLD→NEW values + the plain-language reason — the
 *  reviewable, no-black-box diff the outcome note shows (spec §What / R9). */
export interface RecChange {
  key: string;
  from: string | number | boolean;
  to: string | number | boolean;
  why: string;
}

/**
 * Split the recommended params against the current staged + committed-base values (pure —
 * unit-testable, no fetch/React). A rec is APPLIED only when its key is UNTOUCHED by the user (its
 * staged value still equals `baseVal` — the committed base, else the skill default the run would use)
 * AND its recommended value differs from that base. So Auto-tune fills best practice into inputs the
 * user hasn't set, and:
 *   - it never silently overwrites a hand-edited staged value — a user-touched key that the rec would
 *     have changed is reported in `skipped` ("left your edits as-is"), never clobbered (fixes the
 *     silent-overwrite breach);
 *   - a **raw static default** (`scaled===false` ⇔ `value===default`, per `engine/recommend.py`) may
 *     only FILL an empty/unset input — it must NEVER overwrite a committed non-default value. This is
 *     the deg-clobber fix (`docs/auto-tune/followups.md` NEXT): on a correctly-set bulk `deg` contrast
 *     the `reference`/`treatment`/`method` static defaults (`""`, `""`, `wilcoxon`) diffed against the
 *     committed values and would have wiped the design + downgraded pyDESeq2→Wilcoxon. A **curated
 *     best-practice move** (`scaled===true`, e.g. `n_hvg→2000`) always applies, since it's a genuine
 *     recommendation, not a default leaking through;
 *   - every APPLIED change genuinely differs from the figure base, so it shows the amber pending cue
 *     and the count in the note matches what's visibly staged (fixes the note-vs-visible mismatch).
 * String-compared (controls stringify their values; the proposal path compares the same way).
 */
export function stageableRecommendations(
  recs: ParamRec[],
  staged: SkillParams,
  base: SkillParams,
): { changes: SkillParams; applied: RecChange[]; skipped: string[] } {
  const changes: SkillParams = {};
  const applied: RecChange[] = [];
  const skipped: string[] = [];
  for (const rec of recs) {
    const committed = base[rec.key];                // the figure's committed value (undefined = unset)
    const baseVal = committed ?? rec.default;       // what the run uses when this input is untouched
    const cur = staged[rec.key] ?? baseVal;         // the current effective (staged) value
    if (String(cur) !== String(baseVal)) {
      // The user has already staged a change to this key — don't overwrite it. Report it only if the
      // recommendation would actually have differed (so "left N as-is" is honest, not noise).
      if (String(rec.value) !== String(cur)) skipped.push(rec.key);
      continue;
    }
    if (String(rec.value) === String(baseVal)) continue; // rec already matches the run's value — no-op
    // A static default (scaled=false) must not overwrite a committed non-default value — it may only
    // fill an empty/unset input. A curated move (scaled=true) always applies. (deg-clobber fix.)
    const committedIsSet = committed !== undefined && committed !== null && String(committed) !== "";
    if (!rec.scaled && committedIsSet) continue;
    changes[rec.key] = rec.value;
    applied.push({ key: rec.key, from: baseVal, to: rec.value, why: rec.why });
  }
  return { changes, applied, skipped };
}

/**
 * Fetch the DETERMINISTIC best-practice params for a skill given the data context (the Layer A
 * "Auto-tune" button — docs/auto-tune/spec.md). No AI gateway, no key: works with the gateway off.
 * `skillId` is the bare runtime slug (call {@link runtimeSkillId} first). Throws on a non-2xx
 * response (incl. 404 for an unknown skill).
 */
export async function recommendParams(
  skillId: string,
  ctx: RecommendContext = {},
): Promise<ParamRecs> {
  const res = await fetch(`/api/skills/${encodeURIComponent(skillId)}/recommend-params`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(ctx),
  });
  if (!res.ok) {
    throw new Error(`Couldn't fetch recommendations (${res.status}).`);
  }
  return (await res.json()) as ParamRecs;
}

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
 * Run a skill from an ALREADY-UPLOADED dataset (WS2.1 / 7c §5): the bytes live in the object store, so
 * this POSTs the `dataset_id` (no multipart re-upload) and gets back the SAME `{ figure, provenance,
 * methods, … }` bundle as {@link runSkill} — both route through the backend's one `_execute_skill_run`,
 * so the response shape AND the typed-error surface (422 QC block, 400 data-contract) are identical
 * (shared {@link parseSkillRunResponse}). `skillId` is the bare runtime slug (call {@link runtimeSkillId}
 * first). NOTE: run-from-dataset_id carries NO design sheet — a run that needs one stays on the
 * multipart {@link runSkill} path.
 */
export async function runSkillByDataset(
  skillId: string,
  datasetId: string,
  params: SkillParams = {},
  opts: { override?: boolean } = {},
): Promise<SkillRunResponse> {
  const res = await fetch(`/api/skills/${encodeURIComponent(skillId)}/run-dataset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, params, override: opts.override ?? false }),
  });
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
    // Every run-path failure now arrives in ONE taxonomy envelope (backend routers/_errors.py
    // RunError → detail `{error, category, message, fix}`, mirroring the QC-flag shape) — a typed
    // gate (data_contract_failed, param_out_of_range), a runner data error (skill_run_failed, once a
    // bare-string 400 that fell through to the generic frame), an unknown skill/dataset, a timeout.
    // `message` is a full, self-framed sentence; surface it AS-IS (wrapping it in "Couldn't run …
    // Please try again." reads wrong for a data mismatch). `fix` is the actionable next step (the
    // QCFlag `fix` peer) — append it when present and not already folded into the message, so the
    // user reads what to do, not just what broke.
    const d = body?.detail;
    if (d && typeof d === "object" && typeof (d as { message?: unknown }).message === "string") {
      const { message, fix } = d as { message: string; fix?: unknown };
      const hint = typeof fix === "string" ? fix.trim() : "";
      const err = new Error(hint && !message.includes(hint) ? `${message} ${hint}` : message);
      // Carry the taxonomy CODE (`detail.error`) on the thrown Error, not just its prose. A caller
      // that needs to branch on the failure kind — `skill_timeout` hands the run to the async job
      // lane (lib/jobs/run-skill.ts) — must not have to pattern-match a user-facing sentence.
      const code = (d as { error?: unknown }).error;
      if (typeof code === "string") (err as Error & { code?: string }).code = code;
      throw err;
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
