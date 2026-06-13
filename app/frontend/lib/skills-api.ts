import type { FigureSpec } from "./figure-spec";

/** Per-figure reproducibility bundle (backend provenance.py — charter B4). */
export interface SkillProvenance {
  skill: { id: string; version: string; title: string; engine: string };
  params: Record<string, string | number | boolean>;
  input: { filename: string | null; sha256: string; n_bytes: number };
  environment: {
    python: string;
    platform: string;
    engine_policy: string;
    packages: Record<string, string>;
  };
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

export interface SkillRunResponse {
  figure: FigureSpec;
  // Publish-confidence bundle (B4). Optional so an older backend / a mock without it
  // still renders the figure; the panel just hides when absent.
  provenance?: SkillProvenance;
  methods?: SkillMethods;
  guardrails?: SkillGuardrail[];
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
): Promise<SkillRunResponse> {
  const fd = new FormData();
  fd.append("matrix", file);
  if (design) fd.append("design", design);

  const entries = Object.entries(params).map(([k, v]) => [k, String(v)] as [string, string]);
  const qs = new URLSearchParams(entries).toString();
  const url = `/api/skills/${encodeURIComponent(skillId)}/run${qs ? `?${qs}` : ""}`;

  const res = await fetch(url, { method: "POST", body: fd });
  if (!res.ok) {
    // Prefer the backend's own explanation; otherwise speak plainly (the user is
    // a bench scientist, not an ops engineer) and always point at a next step.
    let detail =
      res.status >= 500
        ? "the analysis service is temporarily unavailable"
        : `the request was rejected (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`Couldn't run this skill — ${detail}. Please try again.`);
  }

  const json = (await res.json()) as Partial<SkillRunResponse>;
  if (!json.figure || !Array.isArray(json.figure.data)) {
    throw new Error("Server returned a malformed figure spec.");
  }
  return {
    figure: json.figure,
    provenance: json.provenance,
    methods: json.methods,
    guardrails: json.guardrails,
  };
}
