"use client";

/**
 * Tiny cross-component intent bus for the project workspace.
 *
 * The command palette is global (mounted in the app shell), but the project
 * workspace owns its tab state internally and is NOT URL-driven. To let the
 * palette deep-link an action — "apply this skill", "open the figure tab" — into
 * a project whether that project is about to mount or is already on screen, the
 * palette dispatches an intent here and the workspace consumes it.
 *
 * Two delivery paths, both covered:
 *   - target not yet mounted (navigating in): the intent stays pending; the
 *     workspace consumes it in its mount effect via `takeIntent()`.
 *   - target already mounted (same project): subscribers fire synchronously, so
 *     the live workspace reacts without a remount (a same-route `router.push`
 *     would otherwise be a no-op).
 */

export type WorkspaceTab = "overview" | "data" | "workbench" | "figure";

export interface WorkspaceIntent {
  projectId: string;
  /** Tab to switch to on arrival. */
  tab?: WorkspaceTab;
  /** A skill to install into the project and pre-select in the Workbench. */
  skillId?: string;
}

let pending: WorkspaceIntent | null = null;
const listeners = new Set<() => void>();

/** Queue an intent and notify any mounted workspace. */
export function dispatchIntent(intent: WorkspaceIntent): void {
  pending = intent;
  for (const l of listeners) l();
}

/** Consume the pending intent for this project (one-shot). */
export function takeIntent(projectId: string): WorkspaceIntent | null {
  if (pending && pending.projectId === projectId) {
    const i = pending;
    pending = null;
    return i;
  }
  return null;
}

/** Subscribe to intent dispatches (a mounted workspace re-checks `takeIntent`). */
export function subscribeIntent(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}
