/**
 * The ONE changed-state language for figure-data controls — the amber/fuchsia tint + ring that marks
 * a control whose staged value differs from the figure's current run value. Shared by the param grid
 * AND the bespoke Marks / Threshold editors (#6) so the three surfaces never drift apart:
 *   "user"  — a manual edit (amber, matching the pending-changes banner accent, `--stage-figuredata`).
 *   "ai"    — an accepted AI value (fuchsia + a ✨ marker, `--stage-ai`).
 *   null    — unchanged → no highlight.
 * Returns only the tint+ring classes; each call site composes them (via `cn`) with its own layout.
 */
export function changedRingClass(author: "ai" | "user" | null | undefined): string | undefined {
  if (author === "user")
    return "bg-[color-mix(in_oklab,var(--stage-figuredata)_9%,transparent)] ring-1 ring-stage-figuredata/45";
  if (author === "ai")
    return "bg-[color-mix(in_oklab,var(--stage-ai)_9%,transparent)] ring-1 ring-stage-ai/45";
  return undefined;
}
