"use client";

import { useState } from "react";
import { ArtboardHost } from "./shell/artboard-host";
import { InspectorDock, type EditorSkill } from "./shell/inspector-dock";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { MarkRole } from "@/lib/erg/marks";
import type { GeneLabelPoint } from "@/lib/volcano/labels";

export type { EditorSkill };

/**
 * The classic figure editor — the artboard hero (ArtboardHost) beside the property inspector
 * (InspectorDock), the SAME two regions the CanvasShell composes. Kept as its own component with a
 * `store`-only public contract because the chart-extractor renders `<EditorWorkspace store={store}/>`
 * and wants exactly artboard + inspector, no rails. Selection (click-to-select → focus a series in
 * Data) is wired locally here, mirroring the shell.
 */
export function EditorWorkspace({
  store,
  elevated = false,
  readOnly = false,
  onEditCopy,
  skill,
  onMarkMove,
  onToggleLabel,
}: {
  store: FigureStore;
  elevated?: boolean;
  /** Frozen "paper" version (Pillar 1, S3): render the figure but bind no edit gestures, and
   *  replace the inspector with an "Edit a copy" notice (Decision D6). */
  readOnly?: boolean;
  onEditCopy?: () => void;
  /** Skill-specific pane shown atop the cosmetic inspector (owner layout 2026-06-23). */
  skill?: EditorSkill;
  /** Drag an ERG landmark dot → commit its new time (erg-manual-marks R5). */
  onMarkMove?: (segment: string, role: MarkRole, tMs: number) => void;
  /** Click a plotted point to toggle its gene label (generalization-spec §H, volcano). */
  onToggleLabel?: (point: GeneLabelPoint) => void;
}) {
  // Click-to-select (P3 §3.4): the artboard reports a clicked trace; the inspector focuses its
  // series. A monotonic nonce makes re-clicking the SAME trace re-trigger the focus effect.
  const [selection, setSelection] = useState<{ trace: number; nonce: number } | null>(null);

  if (!store.spec) return null;

  return (
    <div className="flex min-h-0 flex-1">
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
  );
}
