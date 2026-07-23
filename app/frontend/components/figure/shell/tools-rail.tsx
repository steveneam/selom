"use client";

import { ArrowUpRight, MousePointer2, Ruler, Square, Type } from "lucide-react";
import { cn } from "@/lib/ui/cn";

const TOOLS = [
  { icon: MousePointer2, label: "Select", active: true },
  { icon: Type, label: "Text", active: false },
  { icon: ArrowUpRight, label: "Arrow", active: false },
  { icon: Square, label: "Shape", active: false },
  { icon: Ruler, label: "Guide", active: false },
] as const;

/**
 * The left tools rail. Select is live — a no-op button that signals the current (and only) artboard
 * mode; Text/Arrow/Shape/Guide are declared-but-disabled placeholders (aria-disabled + a title) so
 * the rail reads as intentional rather than empty. Real drawing tools arrive in a later Pillar-2 slice.
 */
export function ToolsRail() {
  return (
    <div
      role="toolbar"
      aria-label="Drawing tools"
      aria-orientation="vertical"
      className="flex w-12 shrink-0 flex-col items-center gap-1 border-r border-border bg-card/30 py-2"
    >
      {TOOLS.map(({ icon: Icon, label, active }) => (
        <button
          key={label}
          type="button"
          disabled={!active}
          aria-disabled={!active}
          aria-pressed={active || undefined}
          title={active ? label : "Arrives in a later update"}
          className={cn(
            "grid size-9 place-items-center rounded-md transition-colors [&_svg]:size-4",
            active
              ? "bg-accent/60 text-foreground"
              : "text-muted-foreground opacity-40",
          )}
        >
          <Icon />
          <span className="sr-only">{label}</span>
        </button>
      ))}
    </div>
  );
}
