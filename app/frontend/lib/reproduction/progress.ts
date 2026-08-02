"use client";

/**
 * The consumer for the reproduction run's progress stream (`GET /reproduction-runs/{id}/events`).
 *
 * That stream shipped with no reader at all, so a reproduction drive — the longest thing a user
 * can start in Selom, a whole paper's worth of panels — reported nothing while it ran (guard
 * waiver R-06). Its non-streaming sibling `GET /reproduction-runs/{id}` *was* read, which is why
 * this was a progress-visibility gap rather than a dead feature.
 *
 * The stream emits `reproduction_runs.public(rec, light=True)` every 0.5s until terminal, so
 * unlike the job wire shape it DOES carry a server-authored `progress` line. That line is shown
 * verbatim; nothing here invents one.
 *
 * v1 runs inline, so the POST that starts a run only returns once the run is already terminal and
 * the stream resolves in a single frame. The value today is that the activity entry exists from
 * the moment the user clicks Run; the value tomorrow is that the same code streams the per-panel
 * transitions the instant the drive moves off-request.
 */

import {
  beginActivity,
  finishActivity,
  updateActivity,
  type ActivityStatus,
} from "@/lib/jobs/activity";
import { followRun, RunGoneError } from "@/lib/jobs/sse";

/** The subset of the run payload this module needs — the light shape the stream emits. */
export interface ReproductionProgress {
  run_id: string;
  status: ActivityStatus;
  progress?: string;
  error?: string;
}

export function reproductionEventsUrl(runId: string): string {
  return `/api/reproduction-runs/${encodeURIComponent(runId)}/events`;
}

export function reproductionStatusUrl(runId: string): string {
  return `/api/reproduction-runs/${encodeURIComponent(runId)}`;
}

export function isReproductionTerminal(state: ReproductionProgress): boolean {
  return state.status === "succeeded" || state.status === "failed";
}

export interface ReproductionTracker {
  /**
   * Follow `payload`'s run to its terminal state, reporting progress as it goes. Returns the same
   * payload with the FINAL status and error folded in, so the caller's control flow is unchanged.
   */
  follow: <T extends ReproductionProgress>(payload: T) => Promise<T>;
  /** Mark the run failed before it ever got a run id (the POST itself failed). */
  fail: (detail: string) => void;
}

/**
 * Register a reproduction run in the activity store and return the handle that drives it.
 * Call this BEFORE the POST — the entry has to exist while the request is still in flight, which
 * is the whole window the user is waiting in.
 */
export function trackReproduction(label: string, context = ""): ReproductionTracker {
  const activityId = beginActivity({ kind: "reproduction", label, context });

  async function follow<T extends ReproductionProgress>(payload: T): Promise<T> {
    updateActivity(activityId, {
      serverId: payload.run_id,
      status: payload.status,
      detail: payload.progress ?? "",
    });
    if (isReproductionTerminal(payload)) return settle(payload);

    let last: ReproductionProgress | null = payload;
    try {
      const followed = await followRun<ReproductionProgress>({
        streamUrl: reproductionEventsUrl(payload.run_id),
        pollUrl: reproductionStatusUrl(payload.run_id),
        isTerminal: isReproductionTerminal,
        onState: (state) =>
          updateActivity(activityId, { status: state.status, detail: state.progress ?? "" }),
      });
      last = followed.terminal ? followed.state : null;
    } catch (e) {
      const detail =
        e instanceof RunGoneError
          ? "This reproduction run is no longer available — the server may have restarted."
          : "Lost track of this reproduction run.";
      finishActivity(activityId, { status: "failed", error: detail });
      return { ...payload, status: "failed" as const, error: detail };
    }

    if (last === null) {
      const detail = "This run is still going after five minutes — Selom stopped watching it.";
      finishActivity(activityId, { status: "failed", error: detail });
      return { ...payload, status: "failed" as const, error: detail };
    }
    // Fold the FINAL streamed state onto the POST payload — including its `progress` line, which
    // is the one the run ended on (the POST's own is whatever was true before it started).
    return settle({
      ...payload,
      status: last.status,
      error: last.error,
      progress: last.progress ?? payload.progress,
    });
  }

  function settle<T extends ReproductionProgress>(payload: T): T {
    if (payload.status === "failed") {
      finishActivity(activityId, {
        status: "failed",
        error: payload.error ?? "The reproduction run failed.",
      });
    } else {
      finishActivity(activityId, { status: "succeeded", detail: payload.progress ?? "" });
    }
    return payload;
  }

  return {
    follow,
    fail: (detail: string) => finishActivity(activityId, { status: "failed", error: detail }),
  };
}
