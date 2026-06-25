"use client";

/**
 * Granular error isolation for the figure editor (architecture-consistency-gate, Task B1).
 *
 * Selom's panes are bespoke per data/skill — a pane built for skill A can receive skill B's spec
 * on a switch and throw while reading a capability-specific shape (e.g. a colour-scale panel reading
 * `tone.zmin` on a heatmap-less spec). Without isolation, that one throw unmounts the WHOLE editor.
 *
 * `ErrorBoundary` catches a render/lifecycle throw in its subtree and renders a fallback instead, so
 * the failure stays local. `resetKeys` clears a stuck boundary when the identity it watches changes
 * (e.g. the active figure / dataset / skill) — switching data/skill auto-recovers without a manual
 * retry. React requires a CLASS component for error boundaries; this is the one class in the FE.
 *
 * Dependency-free on purpose (no `react-error-boundary`): a ~60-line in-house boundary avoids a new
 * dependency for a well-understood primitive. NOTE: boundaries catch render/lifecycle errors only —
 * async / event-handler errors must be routed into a pane's own error STATE (Task B2/B3), not here.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { keysChanged } from "@/lib/ui/reset-keys";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Render the fallback from the caught error + a reset() the fallback can call (a Retry button). */
  fallback: (error: Error, reset: () => void) => ReactNode;
  /** When any entry changes (shallow compare), a stuck boundary auto-resets — pass the switch
   *  identity (figure id, dataset id, skill id) so dataset/skill switches clear a prior crash. */
  resetKeys?: ReadonlyArray<unknown>;
  /** Side-channel for logging/telemetry (console now; Sentry later — gate Task F). */
  onError?: (error: Error, info: ErrorInfo) => void;
  label?: string;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Keep the crash visible to developers even though the UI degrades gracefully.
    console.error(`[error-boundary${this.props.label ? `:${this.props.label}` : ""}]`, error, info);
    this.props.onError?.(error, info);
  }

  componentDidUpdate(prev: ErrorBoundaryProps): void {
    // A switch (figure/dataset/skill changed) clears a stuck boundary so it re-attempts the subtree.
    if (this.state.error && keysChanged(prev.resetKeys, this.props.resetKeys)) {
      this.setState({ error: null });
    }
  }

  reset = (): void => this.setState({ error: null });

  render(): ReactNode {
    if (this.state.error) return this.props.fallback(this.state.error, this.reset);
    return this.props.children;
  }
}

/**
 * The editor's standard pane wrapper: isolates one pane and renders a quiet, on-brand fallback
 * (a small card + Retry) when it throws, so a bespoke pane meeting an unexpected figure shape can
 * never take the editor down. Pass `resetKeys` so a dataset/skill/figure switch auto-clears it.
 */
export function PaneBoundary({
  children,
  resetKeys,
  label,
  title = "This panel hit an unexpected figure",
  className,
}: {
  children: ReactNode;
  resetKeys?: ReadonlyArray<unknown>;
  label?: string;
  title?: string;
  className?: string;
}) {
  return (
    <ErrorBoundary
      label={label}
      resetKeys={resetKeys}
      fallback={(_error, reset) => (
        <div
          className={cn(
            "m-3 rounded-lg border border-dashed border-destructive/40 bg-destructive/5 p-4 text-center",
            className,
          )}
          role="alert"
        >
          <p className="text-xs font-medium text-foreground">{title}</p>
          <p className="mx-auto mt-1 max-w-[20rem] text-[11px] leading-relaxed text-muted-foreground">
            The rest of the editor is fine. Switch figure or skill, or retry this panel.
          </p>
          <button
            type="button"
            onClick={reset}
            className="mt-2.5 rounded-md border border-border bg-background px-2.5 py-1 text-[11px] font-medium text-foreground transition hover:bg-muted"
          >
            Retry
          </button>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  );
}
