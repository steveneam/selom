/**
 * The four AI Action Gateway endpoint wrappers (S5).
 *
 * Mirrors the live contract (app/backend/routers/ai.py) and the shape of
 * `lib/extract/api.ts`: thin typed fetch wrappers over the proxied `/api/ai/*`
 * routes. The gateway is OFF by default (NullActionGateway) — every wrapper here
 * degrades clean: `propose` returns an empty plan, `explain` returns deterministic
 * text, `gaps` returns the backlog (which works regardless of the gateway). Live
 * AI proposal text awaits `SELOM_AI_GATEWAY=live` + `ANTHROPIC_API_KEY`.
 */

import { parseSkillRunResponse, type SkillParams, type SkillRunResponse } from "@/lib/skills/api";
import type {
  AiActionDelta,
  ExplainRequest,
  ExplainResponse,
  GapBacklogEntry,
  HelperTurn,
} from "./types";

/** Context for an AI proposal — what the helper sees (mirrors backend ProposeRequest). */
export interface ProposeRequest {
  stage?: string;
  skill_id?: string | null;
  params?: SkillParams;
  goal: string;
  figure_spec?: Record<string, unknown> | null;
  capability_surface?: Record<string, unknown> | null;
  // Slice 2 — data context for data-aware routing (the route-stage select_skill gate). The server
  // derives the fit verdict from these via engine.compat.fit; the client never asserts compatibility.
  data_columns?: string[];
  data_kind?: string;
  data_n_numeric_cols?: number;
}

/**
 * Ask the gateway to propose an ActionPlan for a goal + figure context.
 *
 * With the gateway off this resolves to a HelperTurn with an empty plan (no
 * proposals) — the zero-regression baseline. The caller turns
 * `staged_params` + `provenance_actions` into the FE proposal queue.
 */
export async function proposeActions(req: ProposeRequest): Promise<HelperTurn> {
  const res = await fetch("/api/ai/propose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stage: "analyze", params: {}, ...req }),
  });
  if (!res.ok) {
    throw new Error(`Couldn't reach the AI helper (${res.status}). The deterministic editor is unaffected.`);
  }
  return (await res.json()) as HelperTurn;
}

/**
 * Execute the user-approved AI actions through the SAME gated run path as a human run.
 *
 * Multipart POST to /ai/apply (matrix + skill_id + goal + override + params JSON +
 * ai_actions JSON). The backend routes it through `_execute_skill_run` — the same QC /
 * data-contract / frame-schema gates and the same provenance builder — then stamps the
 * SERVER-derived attribution onto `provenance.actions[]` (the NEXT#1 chokepoint re-derives
 * actor/model/approved_by/approved_at; the posted delta carries none of them). The response is
 * byte-identical to a normal run, so it reuses {@link parseSkillRunResponse} (one error/parse path).
 *
 * `aiActions` is the approved DELTA — non-empty, each entry `{action_id, type, target, prompt}`;
 * the backend rejects an empty/malformed log with 400.
 */
export async function applyAiActions(
  skillId: string,
  file: File,
  params: SkillParams,
  aiActions: AiActionDelta[],
  opts: { goal?: string; override?: boolean; design?: File | null } = {},
): Promise<SkillRunResponse> {
  const fd = new FormData();
  fd.append("matrix", file);
  fd.append("skill_id", skillId);
  fd.append("goal", opts.goal ?? "");
  fd.append("override", opts.override ? "true" : "false");
  // params are sent as a JSON object (not a query string) — the FINAL approved params
  // (base merged with the accepted staged delta), stringified to match the backend Form field.
  fd.append("params", JSON.stringify(params));
  fd.append("ai_actions", JSON.stringify(aiActions));
  // The design sheet (sample→condition/time) MUST ride the re-run for design-consuming skills
  // (deg / heatmap) — same as the human /skills/run path; without it the backend silently falls
  // back to column-name inference → a different result. provenance.params can't carry it (the
  // reserved key is stripped), so it's re-attached as the multipart `design` file every re-run.
  if (opts.design) fd.append("design", opts.design);

  const res = await fetch("/api/ai/apply", { method: "POST", body: fd });
  return parseSkillRunResponse(res);
}

/**
 * Fetch the ranked, categorized capability-gap backlog (`GET /ai/gaps`).
 *
 * Review-only — never mutates the registry. Works regardless of the gateway state
 * (it reads the persisted gap store). Returns `[]` when the backlog is empty.
 */
export async function fetchGaps(): Promise<GapBacklogEntry[]> {
  const res = await fetch("/api/ai/gaps");
  if (!res.ok) {
    throw new Error(`Couldn't load the capability backlog (${res.status}).`);
  }
  return (await res.json()) as GapBacklogEntry[];
}

/**
 * Informational AI helper text grounded in deterministic artifacts (`POST /ai/explain`).
 *
 * Never a mutation. `source` is "deterministic" when the gateway is off (a short
 * summary of the passed scorecard / sweep-space) and "ai" when live — either way it
 * never raises or fabricates values outside the supplied data.
 */
export async function explain(req: ExplainRequest): Promise<ExplainResponse> {
  const res = await fetch("/api/ai/explain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    throw new Error(`Couldn't generate an explanation (${res.status}).`);
  }
  return (await res.json()) as ExplainResponse;
}
