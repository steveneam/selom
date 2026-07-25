"use client";

import { useState, type ReactNode } from "react";
import { ArtboardHost } from "./artboard-host";
import { CommandBar } from "./command-bar";
import { InspectorDock, type EditorSkill } from "./inspector-dock";
import { ToolContextStrip } from "./tool-context-strip";
import { ToolsRail } from "./tools-rail";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { MarkRole } from "@/lib/erg/marks";
import type { GeneLabelPoint } from "@/lib/volcano/labels";

/**
 * The figure-editor CANVAS SHELL — a four-region, Inkscape-style frame around the artboard:
 *   • top    — the command bar (figure-view's command cluster) + a tool-context strip
 *   • left   — the tools rail (Select live; the rest are placeholders)
 *   • centre — the artboard as the hero (ArtboardHost, min-w-0 so it never squeezes to nothing)
 *   • right  — the property inspector dock (InspectorDock, the existing tabbed inspector, as-is)
 *
 * There is deliberately NO bottom band. The inert palette strip that used to dock there was retired
 * (A25 · B13): it was aria-hidden, hardcoded Okabe–Ito regardless of `layout.colorway` — so it made
 * a confident WRONG claim about the figure the moment Style swapped the palette — and spent ~34px of
 * an already-clipped artboard to say "coming soon". The real colourway swap lives in the inspector's
 * Style tab. A LIVE palette board is welcome back; placeholder chrome that costs the hero its pixels
 * is not (docs/integration-robustness/proposal.md §3.3).
 *
 * Pure composition over ONE store (owned by project-workspace) — it instantiates nothing and adds
 * no write path. The command cluster is a `command` slot so figure-view keeps its view-local state
 * (export/staleness/style/bundle) rather than prop-drilling it into the shell. Desktop-only layout.
 */
export function CanvasShell({
  command,
  store,
  elevated = false,
  readOnly = false,
  skill,
  onEditCopy,
  onMarkMove,
  onToggleLabel,
}: {
  /** The command cluster built by figure-view (undo/redo · staleness · style · export · version bar). */
  command: ReactNode;
  store: FigureStore;
  /** Export is open — lift the artboard above the scrim (forwarded to ArtboardHost). */
  elevated?: boolean;
  /** Frozen "paper" version: no edit gestures; the inspector shows the fork notice (Decision D6). */
  readOnly?: boolean;
  /** Skill-identity card shown atop the inspector. */
  skill?: EditorSkill;
  onEditCopy?: () => void;
  /** Drag an ERG landmark dot → commit its new time (erg-manual-marks R5). */
  onMarkMove?: (segment: string, role: MarkRole, tMs: number) => void;
  /** Click a plotted point to toggle its gene label (generalization-spec §H, volcano). */
  onToggleLabel?: (point: GeneLabelPoint) => void;
}) {
  // Click-to-select (P3 §3.4): the artboard reports a clicked trace; the inspector focuses its
  // series. A monotonic nonce makes re-clicking the SAME trace re-fire the focus effect. This is
  // view-local UI state, not figure state — no second store is created.
  const [selection, setSelection] = useState<{ trace: number; nonce: number } | null>(null);

  return (
    <div className="flex min-h-[520px] min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-background">
      <CommandBar>{command}</CommandBar>
      <ToolContextStrip />
      <div className="flex min-h-0 flex-1">
        {/* Draw tools commit to the store; a frozen ("paper") figure gets no store → they disable. */}
        <ToolsRail store={readOnly ? undefined : store} />
        <ArtboardHost
          store={store}
          elevated={elevated}
          readOnly={readOnly}
          onSelectTrace={(trace) => setSelection((s) => ({ trace, nonce: (s?.nonce ?? 0) + 1 }))}
          onMarkMove={onMarkMove}
          onToggleLabel={onToggleLabel}
        />
        <InspectorDock
          store={store}
          selection={selection}
          readOnly={readOnly}
          onEditCopy={onEditCopy}
          skill={skill}
        />
      </div>
    </div>
  );
}
