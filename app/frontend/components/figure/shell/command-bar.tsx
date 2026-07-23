"use client";

import type { ReactNode } from "react";

/**
 * The shell's top command bar — the frame for the figure's command cluster (undo/redo, staleness
 * re-run, style, "Figure data", export, "New figure", version bar). figure-view BUILDS that cluster
 * (it owns the view-local state — export/staleness/style/bundle) and passes it in as `children`;
 * this component only frames it, so no view-local state is prop-drilled into the shell.
 */
export function CommandBar({ children }: { children: ReactNode }) {
  return <div className="shrink-0 border-b border-border bg-card/30 px-3 py-2.5">{children}</div>;
}
