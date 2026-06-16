"use client";

/**
 * A tiny global "undo last destructive action" bus.
 *
 * The project store is a localStorage mock with no server-side trash, so a confirmed
 * delete is otherwise irreversible. When something is deleted, the caller captures a
 * restore closure and pushes it here; a global <UndoToast> (mounted in the app shell,
 * so it survives the navigation a project-delete triggers) surfaces a brief "Undo".
 * One entry at a time — a newer delete replaces the older offer.
 */

export interface UndoEntry {
  id: number;
  label: string;
  /** Re-applies the deleted state. Called at most once. */
  restore: () => void;
}

let current: UndoEntry | null = null;
let seq = 0;
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

/** Offer an undo for a just-completed destructive action. */
export function pushUndo(label: string, restore: () => void): void {
  current = { id: ++seq, label, restore };
  emit();
}

/** The current offer (referentially stable until it changes) — for useSyncExternalStore. */
export function getUndo(): UndoEntry | null {
  return current;
}

/** Dismiss the current offer (optionally only if it still matches `id`). */
export function clearUndo(id?: number): void {
  if (current && (id == null || current.id === id)) {
    current = null;
    emit();
  }
}

/** Run the current restore closure and clear the offer. */
export function performUndo(): void {
  const entry = current;
  if (!entry) return;
  current = null;
  emit();
  entry.restore();
}

export function subscribeUndo(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}
