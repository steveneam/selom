/**
 * The editor's ROOM BUDGET — how much of a narrow viewport the figure gets (`W-2`,
 * `docs/editor-room/spec.md`, owner decision #13).
 *
 * Measured at 1280×800 on a real volcano: fixed columns take ~70% of the viewport (app sidebar 256 +
 * project workrail 256 + tools rail 48 + inspector dock 330), leaving the plotting area **90px**
 * against a ~506px target. Collapsing the workrail alone reaches 294px; collapsing the dock alone
 * reaches 368px; **only both together clear the target (576px)**. The owner declined to treat 1280 as
 * a degraded width, so at or below it the editor arrives with both rails as spines.
 *
 * Pure + framework-free, like `pane-state.ts`, so the rule is unit-tested by exit code rather than
 * by eye — and so it is stated exactly once for the two rails that obey it.
 */

/**
 * At or below this viewport width the editor arrives with its rails collapsed.
 *
 * **Derived from the target, not chosen.** The spec first proposed 1280 — the width the complaint
 * came from — on the assumption that "at 1440 the figure is already comfortable". A browser
 * disproved that the moment `W-2` was wired: with both rails expanded the fixed chrome eats a
 * measured **1193px** (sidebar 256 + workrail 256 + tools rail 48 + inspector dock 330, plus the
 * stage/card padding and Plotly's own margins), so at 1440 the plotting area is **247px** — worse
 * than the 571px a *collapsed* 1280 delivers. A 1280 threshold therefore produced the one result no
 * user would forgive: **widen the window and the figure gets smaller.**
 *
 * So the threshold is the width at which the expanded layout can finally afford the ~506px target:
 * `506 + 1193 ≈ 1699`. Below it the rails yield; at or above it they do not have to.
 *
 * A VIEWPORT rule, deliberately not a measured-stage rule: the stage's width is downstream of the
 * very collapse this decides, so keying off it would be a feedback loop. Selom is desktop-only, so
 * there is no mobile breakpoint to reconcile with.
 *
 * The number is held by `browser-verify d5`, which asserts the target at EVERY checked viewport —
 * if a rail's width changes, that gate fails rather than this comment going quietly stale.
 */
export const AUTO_COLLAPSE_MAX_WIDTH = 1700;

/** Should the editor's rails start collapsed at this viewport width? */
export function shouldAutoCollapse(viewportWidth: number): boolean {
  // A non-finite or zero width means "we don't know yet" (SSR, a detached measurement). Answer no:
  // arriving expanded and collapsing a frame later is a smaller error than the reverse, which would
  // hide the inspector on a wide screen for no reason the user can see.
  if (!Number.isFinite(viewportWidth) || viewportWidth <= 0) return false;
  return viewportWidth <= AUTO_COLLAPSE_MAX_WIDTH;
}

// --- Zoom ---------------------------------------------------------------------------------------
//
// The editor's second room lever (decision #13). Zoom MAGNIFIES the artboard; it does not re-lay-out
// the figure at a bigger width — that would be "more canvas", where text stays 12px while the plot
// grows, which is the opposite of what a zoom control promises. So it is a scale applied to the
// rendered card, and it writes NOTHING to the spec: `layout.width`/`layout.height` are the user's
// EXPORT size (the Page tab), not a view property, and zoom must never touch them.
//
// Worth being plain about: zoom is NOT what fixes the 1280 width defect — the rail collapse above is.
// Its real payoff is the FIXED-size figure (an ERG trace grid declares 960×640) which, in a stage
// narrower than itself, today just clips and scrolls with no way to see the whole thing at once.

/** The zoom steps, coarse on purpose: fewer states to verify than free numeric entry. */
export const ZOOM_LADDER = [0.5, 0.75, 1, 1.5, 2, 4] as const;

/** "Fit" is a MODE, not a number — the fitted scale depends on a stage only the host can measure. */
export type Zoom = number | "fit";

export const DEFAULT_ZOOM: Zoom = "fit";

/**
 * The next rung up (`+1`) or down (`-1`) from `current`. A value between rungs (a resolved "fit"
 * like 0.63) steps to the next rung in that direction rather than snapping to the nearest — so
 * pressing `+` always makes the figure bigger, which is the only behaviour a zoom button may have.
 */
export function stepZoom(current: number, direction: 1 | -1): number {
  const rungs = ZOOM_LADDER;
  if (direction > 0) return rungs.find((r) => r > current + 1e-9) ?? rungs[rungs.length - 1];
  return [...rungs].reverse().find((r) => r < current - 1e-9) ?? rungs[0];
}

/**
 * The scale at which `content` fits inside `stage`, never magnifying past 1:1.
 *
 * Capped at 1 deliberately. "Fit" means *see all of it*, and blowing a small figure up to fill a
 * large stage is a different intent the user can reach explicitly on the ladder. For a RESPONSIVE
 * figure the content is the stage, so this returns exactly 1 — the honest answer, since such a
 * figure already fits by construction.
 */
export function fitScale(
  stage: { width: number; height: number },
  content: { width: number; height: number },
): number {
  const ok = (n: number) => Number.isFinite(n) && n > 0;
  // An unmeasurable stage or a zero-size figure has no meaningful fit — 1:1 is the safe identity,
  // and it keeps a hidden or not-yet-laid-out editor from rendering at some absurd scale.
  if (!ok(stage.width) || !ok(stage.height) || !ok(content.width) || !ok(content.height)) return 1;
  return Math.min(1, stage.width / content.width, stage.height / content.height);
}

/** The zoom readout: `1` → "100%", `0.634` → "63%". */
export function formatZoom(scale: number): string {
  if (!Number.isFinite(scale) || scale <= 0) return "100%";
  return `${Math.round(scale * 100)}%`;
}
