"use client";

/**
 * The async job contract, client side (`app/backend/routers/jobs.py` + the two submit routes in
 * `routers/skills.py`). This is the READER half of the job pipeline; the arq + Redis producer
 * (OH-01) lands after it, deliberately, so the store ships with a consumer already in place.
 *
 * The wire shape is `Job.public()` (`app/backend/jobs/store.py`) — note what it does NOT carry:
 * no percentage, no step count, no ETA. Any surface built on this must therefore report elapsed
 * time and state transitions, never a fabricated completion estimate.
 */

import { parseSkillRunResponse, type SkillParams, type SkillRunResponse } from "@/lib/skills/api";

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

/** `GET /jobs/{id}` — the full wire shape the FE polls (`Job.public()`). */
export interface JobRecord {
  id: string;
  skill_id: string;
  status: JobStatus;
  result_url: string | null;
  error: string | null;
  created_at: number;
  updated_at: number;
}

/** Mirrors `jobs.store.TERMINAL` — the states that need no further watching. */
export function isJobTerminal(job: JobRecord): boolean {
  return job.status === "succeeded" || job.status === "failed";
}

export function jobStatusUrl(jobId: string): string {
  return `/api/jobs/${encodeURIComponent(jobId)}`;
}

export function jobEventsUrl(jobId: string): string {
  return `/api/jobs/${encodeURIComponent(jobId)}/events`;
}

export function jobResultUrl(jobId: string): string {
  return `/api/jobs/${encodeURIComponent(jobId)}/result`;
}

/** Surface a job-route failure with the backend's own `detail` when it sends one. */
async function jobError(res: Response, what: string): Promise<Error> {
  let detail = `${res.status}`;
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    /* non-JSON error body */
  }
  return new Error(`Couldn't ${what} — ${detail}.`);
}

/** Params ride the submit routes exactly as they ride `/run`: strings the runners coerce. */
function paramQuery(params: SkillParams, opts: { override?: boolean }): string {
  const entries = Object.entries(params).map(([k, v]) => [k, String(v)] as [string, string]);
  if (opts.override) entries.push(["override", "true"]);
  const qs = new URLSearchParams(entries).toString();
  return qs ? `?${qs}` : "";
}

/**
 * `POST /skills/{id}/jobs` — hand a run to the heavy lane. Multipart, same field name (`matrix`)
 * and same query-string params as the synchronous `/run`; the response is the job handle, not a
 * figure. In `inline` queue mode this request still blocks for the run's duration; in `arq` mode
 * it returns immediately and the worker takes over. Either way the caller follows the job id.
 */
export async function submitSkillJob(
  skillId: string,
  file: File,
  params: SkillParams = {},
  opts: { override?: boolean } = {},
): Promise<JobRecord> {
  const fd = new FormData();
  fd.append("matrix", file);
  const url = `/api/skills/${encodeURIComponent(skillId)}/jobs${paramQuery(params, opts)}`;
  const res = await fetch(url, { method: "POST", body: fd });
  if (!res.ok) throw await jobError(res, "start this run in the background");
  return (await res.json()) as JobRecord;
}

/**
 * `POST /skills/{id}/jobs-dataset` — the heavy-lane twin of `/run-dataset`: the bytes are already
 * in the object store, so this submits the `dataset_id` instead of re-uploading them.
 */
export async function submitSkillJobFromDataset(
  skillId: string,
  datasetId: string,
  params: SkillParams = {},
  opts: { override?: boolean } = {},
): Promise<JobRecord> {
  const res = await fetch(`/api/skills/${encodeURIComponent(skillId)}/jobs-dataset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, params, override: opts.override ?? false }),
  });
  if (!res.ok) throw await jobError(res, "start this run in the background");
  return (await res.json()) as JobRecord;
}

/** `GET /jobs/{id}` — one status read (the poll floor behind the event stream). */
export async function fetchJob(jobId: string): Promise<JobRecord> {
  const res = await fetch(jobStatusUrl(jobId), { headers: { accept: "application/json" } });
  if (!res.ok) throw await jobError(res, "check this run");
  return (await res.json()) as JobRecord;
}

/**
 * `GET /jobs/{id}/result` — the finished bundle.
 *
 * Parsed by the SAME reader as the synchronous run (`parseSkillRunResponse`) because the backend
 * stores the `/run` shape verbatim. It is a STRICT SUBSET of it, though: `jobs/queue.py` builds
 * `{figure, provenance, methods, guardrails, table}` and does not run the legend, is-my-data-clean
 * or data-fit steps that `_execute_skill_run` does. Every one of those fields is optional in
 * `SkillRunResponse`, so the figure renders correctly and the extra panels simply have nothing to
 * show. Closing that gap belongs to the producer (OH-01) — see `docs/jobs-surface/spec.md`.
 */
export async function fetchJobResult(jobId: string): Promise<SkillRunResponse> {
  const res = await fetch(jobResultUrl(jobId), { headers: { accept: "application/json" } });
  return parseSkillRunResponse(res);
}
