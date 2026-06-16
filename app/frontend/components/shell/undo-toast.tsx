"use client";

import * as React from "react";
import { RotateCcw, X } from "lucide-react";
import { clearUndo, getUndo, performUndo, subscribeUndo } from "@/lib/workspace/undo";

/**
 * Global "Undo" toast for destructive actions (delete a figure / a project). Mounted
 * once in the app shell so it survives the navigation a project-delete triggers. Auto-
 * dismisses after a few seconds; the action is the safety net for the localStorage
 * mock's irreversible deletes.
 */
const TIMEOUT_MS = 8000;

export function UndoToast() {
  const entry = React.useSyncExternalStore(subscribeUndo, getUndo, () => null);

  React.useEffect(() => {
    if (!entry) return;
    const id = setTimeout(() => clearUndo(entry.id), TIMEOUT_MS);
    return () => clearTimeout(id);
  }, [entry?.id]);

  if (!entry) return null;

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center px-4">
      <div
        role="status"
        className="pointer-events-auto flex items-center gap-3 rounded-xl border border-border bg-card/95 py-2 pl-4 pr-2 text-sm shadow-lg shadow-black/30 backdrop-blur-sm"
      >
        <span className="truncate text-foreground">{entry.label}</span>
        <button
          type="button"
          onClick={performUndo}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-accent/60 px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 [&_svg]:size-3.5"
        >
          <RotateCcw /> Undo
        </button>
        <button
          type="button"
          onClick={() => clearUndo(entry.id)}
          aria-label="Dismiss"
          className="grid size-7 shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 [&_svg]:size-4"
        >
          <X />
        </button>
      </div>
    </div>
  );
}
