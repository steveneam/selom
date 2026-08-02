"use client";

/**
 * Tracked skill runs — the launch-point wrappers.
 *
 * Two jobs, both invisible to the caller:
 *
 *  1. **Progress.** Every run registers an entry in the activity store the moment it starts, so a
 *     user who launches a 90-second UMAP sees that it is running (and sees it finish) instead of
 *     staring at a disabled button. The entry outlives navigation, because the dock that renders
 *     it is mounted in the app shell.
 *
 *  2. **The heavy lane.** The synchronous run path is killed at `SELOM_SKILL_TIMEOUT_S` — **120
 *     seconds by default** (`app/backend/config.py`) — and answers 504 `skill_timeout` with
 *     "try a smaller input or a lighter analysis". For a real scRNA integration or a pyDESeq2
 *     contrast that is a dead end, and it is the exact case the async job path was built for
 *     ("Heavy skills should use POST /skills/{id}/jobs" — `routers/skills.py`), which runs under
 *     no timeout at all. So a run that hits the ceiling is resubmitted to the job lane and
 *     followed to completion rather than lost.
 *
 * The hand-off is honest about what it costs: the job path stores a smaller bundle than
 * `_execute_skill_run` (no auto-legend, no is-my-data-clean verdict, no data-fit score — see
 * `fetchJobResult`). It is only ever reached AFTER the synchronous attempt has already passed
 * every pre-run gate — QC, the D1 data contract and D2 frame validation all ran and let the run
 * through, and only the clock stopped it — so the hand-off trades three read-only panels for a
 * figure the user would otherwise not get at all.
 *
 * The signatures deliberately mirror `runSkill` / `runSkillByDataset` / `applyAiActions` so a
 * launch point swaps one import and keeps its own control flow.
 */

import { getSkill } from "@/lib/catalog/seed";
import { applyAiActions } from "@/lib/ai/api";
import type { AiActionDelta } from "@/lib/ai/types";
import {
  runSkill,
  runSkillByDataset,
  type SkillParams,
  type SkillRunResponse,
} from "@/lib/skills/api";
import {
  beginActivity,
  finishActivity,
  updateActivity,
} from "./activity";
import {
  fetchJobResult,
  isJobTerminal,
  jobEventsUrl,
  jobStatusUrl,
  submitSkillJob,
  submitSkillJobFromDataset,
  type JobRecord,
} from "./api";
import { followRun, RunGoneError } from "./sse";

/** The backend's error taxonomy code for a run killed by the execution ceiling. */
const TIMEOUT_CODE = "skill_timeout";

/**
 * The taxonomy code carried on a run failure (`routers/_errors.py` → `detail.error`), or "".
 * `parseSkillRunResponse` stamps it on the thrown Error so callers branch on the CODE rather than
 * matching on the prose of a user-facing message.
 */
export function runFailureCode(e: unknown): string {
  const code = (e as { code?: unknown } | null)?.code;
  return typeof code === "string" ? code : "";
}

/**
 * The catalog name for a runtime skill id. The registry is keyed by the bare slug while the
 * catalog namespaces its ids (`selom.umap_scrna`), so try both before falling back to the slug.
 */
export function skillLabel(runtimeId: string): string {
  const entry = getSkill(runtimeId) ?? getSkill(`selom.${runtimeId}`);
  if (entry) return entry.name;
  return runtimeId.replace(/[_-]+/g, " ");
}

function message(e: unknown, fallback: string): string {
  return e instanceof Error && e.message ? e.message : fallback;
}

/**
 * Resubmit a timed-out run to the async job lane and follow it to completion, reporting each
 * transition onto the caller's activity entry.
 */
async function continueInBackground(
  activityId: string,
  submit: () => Promise<JobRecord>,
): Promise<SkillRunResponse> {
  updateActivity(activityId, {
    background: true,
    status: "queued",
    detail: "Took longer than the request limit — continuing in the background.",
  });
  let job: JobRecord;
  try {
    job = await submit();
  } catch (e) {
    const detail = message(e, "Couldn't start this run in the background.");
    finishActivity(activityId, { status: "failed", error: detail });
    throw new Error(detail);
  }
  updateActivity(activityId, { serverId: job.id, status: job.status });

  let outcome: JobRecord | null = job;
  if (!isJobTerminal(job)) {
    try {
      const followed = await followRun<JobRecord>({
        streamUrl: jobEventsUrl(job.id),
        pollUrl: jobStatusUrl(job.id),
        isTerminal: isJobTerminal,
        onState: (state) => updateActivity(activityId, { status: state.status }),
      });
      outcome = followed.terminal ? followed.state : null;
    } catch (e) {
      const detail =
        e instanceof RunGoneError
          ? "This background run is no longer available — the server may have restarted."
          : message(e, "Lost track of this background run.");
      finishActivity(activityId, { status: "failed", error: detail });
      throw new Error(detail);
    }
  }

  if (outcome === null) {
    const detail = "This run is still going after five minutes — Selom stopped watching it.";
    finishActivity(activityId, { status: "failed", error: detail });
    throw new Error(detail);
  }
  if (outcome.status === "failed") {
    const detail = outcome.error ?? "The background run failed.";
    finishActivity(activityId, { status: "failed", error: detail });
    throw new Error(detail);
  }

  try {
    const res = await fetchJobResult(job.id);
    finishActivity(activityId, { status: "succeeded", detail: "Finished in the background." });
    return res;
  } catch (e) {
    const detail = message(e, "The run finished but its result couldn't be fetched.");
    finishActivity(activityId, { status: "failed", error: detail });
    throw new Error(detail);
  }
}

/** `runSkill`, with progress reported and the heavy lane behind it. Same shape in and out. */
export async function runSkillTracked(
  skillId: string,
  file: File,
  params: SkillParams = {},
  design?: File | null,
  opts: { override?: boolean } = {},
): Promise<SkillRunResponse> {
  const activityId = beginActivity({ kind: "skill", label: skillLabel(skillId), context: file.name });
  try {
    const res = await runSkill(skillId, file, params, design, opts);
    finishActivity(activityId, { status: "succeeded" });
    return res;
  } catch (e) {
    if (runFailureCode(e) === TIMEOUT_CODE) {
      return continueInBackground(activityId, () => submitSkillJob(skillId, file, params, opts));
    }
    finishActivity(activityId, { status: "failed", error: message(e, "The run failed.") });
    throw e;
  }
}

/** `runSkillByDataset`, with progress reported and the heavy lane behind it. */
export async function runSkillByDatasetTracked(
  skillId: string,
  datasetId: string,
  params: SkillParams = {},
  opts: { override?: boolean } = {},
): Promise<SkillRunResponse> {
  const activityId = beginActivity({ kind: "skill", label: skillLabel(skillId) });
  try {
    const res = await runSkillByDataset(skillId, datasetId, params, opts);
    finishActivity(activityId, { status: "succeeded" });
    return res;
  } catch (e) {
    if (runFailureCode(e) === TIMEOUT_CODE) {
      return continueInBackground(activityId, () =>
        submitSkillJobFromDataset(skillId, datasetId, params, opts),
      );
    }
    finishActivity(activityId, { status: "failed", error: message(e, "The run failed.") });
    throw e;
  }
}

/**
 * `applyAiActions`, with progress reported. No heavy lane: the AI-assisted path must keep its
 * provenance chokepoint (`/ai/apply` stamps `provenance.actions[]`), and the job routes do not
 * carry AI actions — so a timeout here stays a timeout rather than silently producing a figure
 * with no AI attribution.
 */
export async function applyAiActionsTracked(
  skillId: string,
  file: File,
  params: SkillParams,
  aiActions: AiActionDelta[],
  opts: { goal?: string; override?: boolean; design?: File | null } = {},
): Promise<SkillRunResponse> {
  const activityId = beginActivity({ kind: "skill", label: skillLabel(skillId), context: file.name });
  try {
    const res = await applyAiActions(skillId, file, params, aiActions, opts);
    finishActivity(activityId, { status: "succeeded" });
    return res;
  } catch (e) {
    finishActivity(activityId, { status: "failed", error: message(e, "The run failed.") });
    throw e;
  }
}
