"use client";

/**
 * Stable-skeleton pane wrapper (architecture-consistency-gate, Task B3 · plan Spine 3).
 *
 * Renders a CONSISTENT outer shape for a pane regardless of what its data is doing, driven by a
 * single `PaneState` tag (lib/ui/pane-state). Every status renders inside the same wrapper, so a
 * pane never collapses to `null` while loading and the seven states are visually distinct:
 *   loading → a skeleton (not a vanished pane)   ·  empty → a quiet muted note
 *   error   → a message + Retry (not a spinner)  ·  partial/stale → the content + a note banner
 *
 * Pairs with `PaneBoundary` (Task B1): the boundary catches a render THROW; PaneShell renders the
 * pane's own typed STATE (loading/empty/error) so those never need to throw to be handled.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import type { PaneState } from "@/lib/ui/pane-state";
import { hasData, isDegraded } from "@/lib/ui/pane-state";

export function PaneShell<T>({
  state,
  children,
  title,
  className,
  /** Drop the default card chrome (border/padding) — for a pane that supplies its own wrapper. */
  bare = false,
}: {
  state: PaneState<T>;
  /** Rendered for the content states (ready/partial/stale). */
  children?: ReactNode;
  /** Optional small-caps section label, kept across every state so the header doesn't jump. */
  title?: ReactNode;
  className?: string;
  bare?: boolean;
}) {
  return (
    <div
      className={cn(
        !bare && "rounded-xl border border-border bg-card/60 p-4",
        className,
      )}
      data-pane-status={state.status}
    >
      {title != null && (
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </p>
      )}
      <PaneBody state={state}>{children}</PaneBody>
    </div>
  );
}

function PaneBody<T>({ state, children }: { state: PaneState<T>; children?: ReactNode }) {
  switch (state.status) {
    case "idle":
      return null;
    case "loading":
      return <LoadingSkeleton label={state.label} />;
    case "empty":
      return (
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {state.message ?? "Nothing to show here."}
        </p>
      );
    case "error":
      return (
        <div className="mt-2 rounded-lg border border-dashed border-destructive/40 bg-destructive/5 p-3" role="alert">
          <p className="text-xs font-medium text-foreground">
            {state.message ?? "This pane couldn’t load."}
          </p>
          {state.retry && (
            <button
              type="button"
              onClick={state.retry}
              className="mt-2 rounded-md border border-border bg-background px-2.5 py-1 text-[11px] font-medium text-foreground transition hover:bg-muted"
            >
              Retry
            </button>
          )}
        </div>
      );
    default:
      // A content state (ready/partial/stale): a note banner for the degraded ones, then the content.
      return (
        <>
          {isDegraded(state) && (state as { note?: string }).note && (
            <p
              className={cn(
                "mt-2 rounded-md border px-2.5 py-1.5 text-[11px] leading-relaxed",
                state.status === "stale"
                  ? "border-amber-500/40 bg-amber-500/5 text-amber-700 dark:text-amber-400"
                  : "border-border bg-muted/40 text-muted-foreground",
              )}
            >
              {(state as { note?: string }).note}
            </p>
          )}
          {hasData(state) ? children : null}
        </>
      );
  }
}

/** A few pulsing bars — unmistakably "loading", distinct from the muted "empty" note. */
function LoadingSkeleton({ label }: { label?: string }) {
  return (
    <div className="mt-3 space-y-2" aria-busy="true" aria-live="polite">
      {label && <p className="text-xs text-muted-foreground">{label}</p>}
      <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
      <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
      <div className="h-8 w-full animate-pulse rounded bg-muted/70" />
    </div>
  );
}
