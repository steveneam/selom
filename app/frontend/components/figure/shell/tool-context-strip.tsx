"use client";

/**
 * The top tool-context strip — a muted hint line describing what the active tool does. Inert
 * placeholder for Pillar-2 s0 (Select is the only live tool); it fills the region so the shell
 * reads as intentional rather than broken. Later slices swap in per-tool context controls.
 */
export function ToolContextStrip() {
  return (
    <div className="shrink-0 border-b border-border bg-background px-3 py-1.5">
      <p className="text-[11px] text-muted-foreground">
        Select tool — click a trace to focus its series; drag legends, labels, titles, and colour
        bars on the artboard to reposition them.
      </p>
    </div>
  );
}
