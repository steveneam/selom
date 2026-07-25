"use client";

import { useMemo } from "react";
import { ChevronLeft, ChevronRight, Lock } from "lucide-react";
import { PropertyPanel } from "@/components/figure/property-panel";
import { SkillCard } from "@/components/figure/skill-card";
import { inspectorTabs } from "@/components/figure/inspector-tabs";
import { cn } from "@/lib/ui/cn";
import type { FigureStore } from "@/hooks/use-figure-store";

/** The editor's slim skill-identity pane (metadata + hand-off to Figure data for inputs). */
export interface EditorSkill {
  skillName: string;
  badge?: string;
  /** Open the Figure-data stage where this skill's re-run inputs live. */
  onOpenFigureData?: () => void;
}

/**
 * The right-dock property inspector — the tabbed inspector (Style · Axes · Legend · Data · Marks ·
 * Page) with the skill-identity card above it, shared (Pillar-2 s0) by the CanvasShell and the
 * classic EditorWorkspace so there is ONE inspector. A frozen version shows the fork notice instead
 * (Decision D6).
 *
 * COLLAPSIBLE since `W-2` (`docs/editor-room/spec.md`, owner decision #13). Expanded it is 330px —
 * the largest fixed column in the editor, and until now the only one with no way to yield. At 1280
 * that 330px is the difference between a 90px plotting area and a legible figure.
 *
 * Collapsed it becomes a spine of the inspector's own tab icons, not an empty gutter: clicking one
 * expands the dock straight to that tab. That is what keeps auto-collapse honest — the editor opens
 * with the dock closed on a narrow screen, so the spine has to say what is inside it and cost one
 * click to reach, exactly as the project workrail's spine of stage dots does.
 */
export function InspectorDock({
  store,
  selection,
  readOnly = false,
  skill,
  collapsed = false,
  onCollapsedChange,
  tab,
  onTabChange,
}: {
  store: FigureStore;
  /** Click-to-select from the artboard (P3 §3.4): focus the clicked trace's series in Data. */
  selection: { trace: number; nonce: number } | null;
  readOnly?: boolean;
  /** Accepted so both hosts keep one call signature, but deliberately NOT rendered here — the
   *  frozen figure's single "Edit a copy" lives in the command cluster (decision #13). */
  onEditCopy?: () => void;
  /** Skill-specific pane shown atop the cosmetic inspector (owner layout 2026-06-23). */
  skill?: EditorSkill;
  /** Collapsed to a spine. Owned by the host, which defaults it from the viewport (`W-2`). */
  collapsed?: boolean;
  /** Absent → no collapse control is rendered and the dock behaves exactly as it did pre-`W-2`. */
  onCollapsedChange?: (next: boolean) => void;
  /** Active inspector tab, lifted so the collapsed spine can expand into a specific one. */
  tab?: string;
  onTabChange?: (value: string) => void;
}) {
  const tabs = useMemo(() => inspectorTabs(store.spec), [store.spec]);

  if (collapsed) {
    return (
      <aside
        aria-label="Inspector (collapsed)"
        className="flex w-12 shrink-0 flex-col items-center gap-1 border-l border-border bg-card py-2"
      >
        <button
          type="button"
          onClick={() => onCollapsedChange?.(false)}
          aria-label="Expand inspector"
          aria-expanded={false}
          className="grid size-8 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          <ChevronLeft className="size-4" />
        </button>
        <div className="my-1 h-px w-6 bg-border" />
        {/* A frozen figure has no tabs to offer — its dock is a notice, so the spine is just the
            expand control. Everything else gets the real tab list, never a guessed one. */}
        {!readOnly &&
          tabs.map(({ value, label, icon: Icon }) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                onTabChange?.(value);
                onCollapsedChange?.(false);
              }}
              // Not "<label> — expand inspector": that reads as a second expand control to a screen
              // reader AND collides with the chevron's own name under substring matching. This says
              // what the button does, in the order it happens.
              aria-label={`Open ${label} in the inspector`}
              title={label}
              className={cn(
                "grid size-8 place-items-center rounded-md transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                value === tab ? "bg-accent text-accent-foreground" : "text-muted-foreground",
              )}
            >
              <Icon className="size-4" />
            </button>
          ))}
      </aside>
    );
  }

  return (
    <aside className="flex w-[330px] shrink-0 flex-col border-l border-border bg-card">
      {onCollapsedChange && (
        <div className="flex shrink-0 justify-end border-b border-border px-1.5 py-1">
          <button
            type="button"
            onClick={() => onCollapsedChange(true)}
            aria-label="Collapse inspector"
            aria-expanded
            className="grid size-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <ChevronRight className="size-4" />
          </button>
        </div>
      )}
      {readOnly ? (
        <FrozenNotice />
      ) : (
        <>
          {skill && <SkillCard {...skill} />}
          <div className="flex min-h-0 flex-1 flex-col">
            <PropertyPanel store={store} selection={selection} tab={tab} onTabChange={onTabChange} />
          </div>
        </>
      )}
    </aside>
  );
}

/**
 * The inspector slot for a frozen "paper" version — editing is off; fork to change it.
 *
 * It EXPLAINS, and does not act. "Edit a copy" used to appear here as well as in the frozen command
 * cluster: one action, two affordances on one screen (owner call `Q-2`, decision #13 — keep the
 * command cluster's). Collapsing the dock made that structural rather than cosmetic: an action must
 * not become unreachable because a panel yielded its pixels.
 */
function FrozenNotice() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
      <span className="grid size-10 place-items-center rounded-xl border border-stage-figure/40 bg-stage-figure/10 text-stage-figure [&_svg]:size-5">
        <Lock />
      </span>
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">Frozen — the paper version</p>
        <p className="mx-auto max-w-[18rem] text-xs text-muted-foreground">
          This version is locked so it stays exactly as published. Use “Edit a copy” above to make
          changes — the original is kept, untouched.
        </p>
      </div>
    </div>
  );
}
