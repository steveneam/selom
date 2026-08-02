"use client";

/**
 * The run-activity store — the one place the app records "something long is happening".
 *
 * WHY IT IS CLIENT-SIDE STATE AND NOT A SERVER QUERY. Selom's default queue mode is `inline`
 * (`SELOM_QUEUE=inline`, app/backend/config.py): a skill run and a reproduction run BLOCK their
 * own request until they finish, so the server has no job id to hand out until the work is
 * already over. There is therefore no server state to poll while the user is waiting — the only
 * thing that exists from t=0 is the fact that the client made the call. That fact is what this
 * store holds, and it is what makes progress visible today.
 *
 * As soon as a run does get a server-side handle — an async job id (`POST /skills/{id}/jobs`) or a
 * reproduction run id — the entry adopts it (`serverId`) and a follower streams the real
 * transitions onto it (`lib/jobs/sse.ts`). So the same surface that shows "running, 0:42" today
 * shows genuine server progress the moment the arq job store (OH-01) lands, with no FE change.
 *
 * Shaped after `lib/workspace/undo.ts`: a tiny external store read through `useSyncExternalStore`,
 * mounted once in the app shell so it survives the navigation a finished run triggers.
 */

export type ActivityStatus = "queued" | "running" | "succeeded" | "failed";

export type ActivityKind = "skill" | "reproduction";

export interface Activity {
  /** Client-side id — stable for the entry's whole life, unrelated to any server id. */
  id: string;
  kind: ActivityKind;
  /** What is running, in the user's words ("UMAP (scRNA)", "Reproduce RPGRIP1"). */
  label: string;
  /** The second line — the file or paper it is running on. Empty when there isn't one. */
  context: string;
  status: ActivityStatus;
  /**
   * A progress line the SERVER reported. Only ever set from a real payload field (the
   * reproduction stream's `progress`), never invented — the job wire shape carries no percentage
   * and no ETA, so this surface must not imply one.
   */
  detail: string;
  startedAt: number;
  endedAt: number | null;
  error: string | null;
  /** The server-side handle once one exists: an async job id, or a reproduction run id. */
  serverId: string | null;
  /** True once the run left its blocking request and continued as a background job. */
  background: boolean;
}

export interface ActivityInit {
  kind: ActivityKind;
  label: string;
  context?: string;
}

/** Finished entries kept for the dock's recent list before the oldest are pruned. */
const MAX_FINISHED = 8;

const EMPTY: readonly Activity[] = Object.freeze([]);

let entries: readonly Activity[] = EMPTY;
let seq = 0;
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

function isFinished(a: Activity): boolean {
  return a.status === "succeeded" || a.status === "failed";
}

/** Replace the snapshot, pruning the oldest finished entries past {@link MAX_FINISHED}. */
function commit(next: Activity[]): void {
  const finished = next.filter(isFinished);
  if (finished.length > MAX_FINISHED) {
    const drop = new Set(finished.slice(0, finished.length - MAX_FINISHED).map((a) => a.id));
    next = next.filter((a) => !drop.has(a.id));
  }
  entries = Object.freeze(next);
  emit();
}

/** Record that a long run has started. Returns the entry id the caller updates it by. */
export function beginActivity(init: ActivityInit, now: number = Date.now()): string {
  const id = `run-${++seq}`;
  commit([
    ...entries,
    {
      id,
      kind: init.kind,
      label: init.label,
      context: init.context ?? "",
      status: "running",
      detail: "",
      startedAt: now,
      endedAt: null,
      error: null,
      serverId: null,
      background: false,
    },
  ]);
  return id;
}

/** Patch a live entry. A no-op for an id that has already been dismissed. */
export function updateActivity(id: string, patch: Partial<Omit<Activity, "id">>): void {
  const idx = entries.findIndex((a) => a.id === id);
  if (idx === -1) return;
  const next = entries.slice();
  next[idx] = { ...next[idx], ...patch };
  commit(next);
}

/**
 * Move an entry to a terminal state. The entry STAYS in the list — reaching a terminal state has
 * to be visible, so a finished run is dismissed by the user (or auto-dismissed on success by the
 * dock), never silently dropped here.
 */
export function finishActivity(
  id: string,
  outcome: { status: "succeeded" | "failed"; error?: string | null; detail?: string },
  now: number = Date.now(),
): void {
  updateActivity(id, {
    status: outcome.status,
    error: outcome.error ?? null,
    endedAt: now,
    ...(outcome.detail === undefined ? {} : { detail: outcome.detail }),
  });
}

export function dismissActivity(id: string): void {
  const next = entries.filter((a) => a.id !== id);
  if (next.length !== entries.length) commit(next);
}

/** Clear every FINISHED entry, leaving anything still running in place. */
export function clearFinishedActivities(): void {
  const next = entries.filter((a) => !isFinished(a));
  if (next.length !== entries.length) commit(next);
}

/** The current snapshot — referentially stable until something changes (useSyncExternalStore). */
export function getActivities(): readonly Activity[] {
  return entries;
}

/** SSR snapshot: the server renders no activity, and this constant must not change identity. */
export function getActivitiesServerSnapshot(): readonly Activity[] {
  return EMPTY;
}

export function subscribeActivities(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

/** Test hygiene — drop every entry and reset the id counter. */
export function resetActivities(): void {
  entries = EMPTY;
  seq = 0;
  emit();
}
