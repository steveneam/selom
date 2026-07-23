"use client";

import { Lock } from "lucide-react";
import { PropertyPanel } from "@/components/figure/property-panel";
import { SkillCard } from "@/components/figure/skill-card";
import { Button } from "@/components/ui/button";
import type { FigureStore } from "@/hooks/use-figure-store";

/** The editor's slim skill-identity pane (metadata + hand-off to Figure data for inputs). */
export interface EditorSkill {
  skillName: string;
  badge?: string;
  /** Open the Figure-data stage where this skill's re-run inputs live. */
  onOpenFigureData?: () => void;
}

/**
 * The right-dock property inspector — the existing tabbed inspector (Style · Axes · Legend · Data ·
 * Marks · Page) moved AS-IS, with the skill-identity card above it. Relocated (Pillar-2 s0) so the
 * CanvasShell and the classic EditorWorkspace share ONE inspector. Visible by default, defaulting to
 * Style (the e2e figure-gestures spec asserts the "Colour bar" heading WITHOUT any interaction) —
 * never behind a toggle. A frozen version shows the fork notice instead (Decision D6).
 */
export function InspectorDock({
  store,
  selection,
  readOnly = false,
  onEditCopy,
  skill,
}: {
  store: FigureStore;
  /** Click-to-select from the artboard (P3 §3.4): focus the clicked trace's series in Data. */
  selection: { trace: number; nonce: number } | null;
  readOnly?: boolean;
  onEditCopy?: () => void;
  /** Skill-specific pane shown atop the cosmetic inspector (owner layout 2026-06-23). */
  skill?: EditorSkill;
}) {
  return (
    <aside className="flex w-[330px] shrink-0 flex-col border-l border-border bg-card">
      {readOnly ? (
        <FrozenNotice onEditCopy={onEditCopy} />
      ) : (
        <>
          {skill && <SkillCard {...skill} />}
          <div className="flex min-h-0 flex-1 flex-col">
            <PropertyPanel store={store} selection={selection} />
          </div>
        </>
      )}
    </aside>
  );
}

/** The inspector slot for a frozen "paper" version — editing is off; fork to change it. */
function FrozenNotice({ onEditCopy }: { onEditCopy?: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <span className="grid size-10 place-items-center rounded-xl border border-stage-figure/40 bg-stage-figure/10 text-stage-figure [&_svg]:size-5">
        <Lock />
      </span>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">Frozen — the paper version</p>
        <p className="mx-auto max-w-[18rem] text-xs text-muted-foreground">
          This version is locked so it stays exactly as published. Edit a copy to make
          changes — the original is kept, untouched.
        </p>
      </div>
      {onEditCopy && (
        <Button size="sm" variant="outline" onClick={onEditCopy}>
          Edit a copy
        </Button>
      )}
    </div>
  );
}
