"use client";

import type { ComponentType } from "react";
import { ArrowUpRight, Asterisk, MousePointer2, Ruler, Square, Type } from "lucide-react";
import { cn } from "@/lib/ui/cn";
import type { FigureStore } from "@/hooks/use-figure-store";
import type { FigureSpec } from "@/lib/figure/figure-spec";
import type { Operation } from "@/lib/figure/patch";
import { addArrowOps, addSigBracketOps, addTextLabelOps } from "@/lib/figure/annotations";
import { annotationLayerEnabled } from "@/lib/config/env";

type ToolDef = {
  icon: ComponentType<{ className?: string }>;
  label: string;
  /** "select" = the always-live current mode; "draw" = adds an annotation; "soon" = a later slice. */
  kind: "select" | "draw" | "soon";
  /** For draw tools: the op builder that appends the primitive to the spec. */
  build?: (spec: FigureSpec) => Operation[];
};

/**
 * The annotation & drawing tools (Pillar-2 slice 5 — the export-killer). The three draw tools ADD the
 * owner's Illustrator toolset — significance bracket, text label, arrow/callout — as one undoable
 * JSON-Patch each (via lib/figure/annotations); the item then drags on the artboard and exports with the
 * figure. Shape (boxes/highlights) and Guide (alignment) are declared-but-disabled placeholders for a
 * later slice. The Annotate inspector tab is the richer surface (edit/show-hide/remove).
 */
// The three draw tools are behind `annotationLayerEnabled` (off by default — see lib/config/env.ts):
// they commit real annotations, but the layer has no selection model and a re-run destroys them, so a
// user could not undo or keep what they drew. With the flag off the rail is Select only, and the
// declared-but-unbuilt Shape/Guide placeholders go with them rather than advertising an empty rail.
const DRAW_TOOLS: ToolDef[] = [
  { icon: Asterisk, label: "Significance bracket", kind: "draw", build: addSigBracketOps },
  { icon: Type, label: "Text label", kind: "draw", build: addTextLabelOps },
  { icon: ArrowUpRight, label: "Arrow / callout", kind: "draw", build: addArrowOps },
  { icon: Square, label: "Shape", kind: "soon" },
  { icon: Ruler, label: "Guide", kind: "soon" },
];

const TOOLS: ToolDef[] = [
  { icon: MousePointer2, label: "Select", kind: "select" },
  ...(annotationLayerEnabled ? DRAW_TOOLS : []),
];

/**
 * The left tools rail. Select signals the current (and only) artboard mode; the draw tools commit an
 * annotation when the editor is live (a `store` + a loaded figure); Shape/Guide stay disabled with a
 * title so the rail reads as intentional. Read-only ("paper") figures pass no store → draw tools disable.
 */
export function ToolsRail({ store }: { store?: FigureStore }) {
  const spec = store?.spec ?? null;

  return (
    <div
      role="toolbar"
      aria-label="Drawing tools"
      aria-orientation="vertical"
      className="flex w-12 shrink-0 flex-col items-center gap-1 border-r border-border bg-card/30 py-2"
    >
      {TOOLS.map(({ icon: Icon, label, kind, build }) => {
        const isSelect = kind === "select";
        const enabled = isSelect || (kind === "draw" && !!store && !!spec && !!build);
        const onClick =
          kind === "draw" && store && spec && build ? () => store.commit(build(spec)) : undefined;
        return (
          <button
            key={label}
            type="button"
            disabled={!enabled}
            aria-disabled={!enabled}
            aria-pressed={isSelect || undefined}
            title={enabled ? label : kind === "soon" ? "Arrives in a later update" : label}
            onClick={onClick}
            className={cn(
              "grid size-9 place-items-center rounded-md transition-colors [&_svg]:size-4",
              isSelect
                ? "bg-accent/60 text-foreground"
                : enabled
                  ? "cursor-pointer text-foreground/80 hover:bg-accent hover:text-accent-foreground"
                  : "text-muted-foreground opacity-40",
            )}
          >
            <Icon />
            <span className="sr-only">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
