/**
 * The artboard's SIZING CONTRACT — the one place that decides how the white card is sized on the
 * dark stage, so the two hosts that render it (the CanvasShell and the classic EditorWorkspace)
 * cannot drift, and so the rule is checkable by an exit code rather than by eye (A24, which shipped
 * precisely because a CSS-only claim had no gate).
 *
 * The rule, in one sentence: **the stage sizes the card, the card never sizes the stage.**
 *
 *   • RESPONSIVE figure (no numeric `layout.width`) — the card STRETCHES to whatever the shell's
 *     fixed bands leave over. The pre-shell `height: min(74vh, 720px)` could not know about chrome
 *     added inside its own container, so it kept asking for 720px inside a 548px stage: ~24% of the
 *     hero sat below the visible area, reachable only by scrolling inside the stage, with the
 *     document itself not scrolling — nothing signalled that the x-axis title and legend existed
 *     (measured 1512x1050, milestone review A24). A viewport-relative height is the same mistake in
 *     a different unit: `vh` measures the WINDOW, and the artboard does not get the window.
 *   • FIXED-size figure (numeric `layout.width` — ERG trace grids, multi-panel) — the figure keeps
 *     its declared size, stays top-aligned, and the stage scrolls. Scrolling is the CORRECT
 *     behaviour there: the size is a property of the figure, not a guess about the viewport.
 *
 * A floor and a cap bracket the responsive card. Neither can clip the figure — a min/max only ever
 * resizes the card away from the stage's height, while an exact height is what overflows it:
 *   • floor (`min-h`) — a host that gives the stage no definite height would otherwise collapse a
 *     stretched card to zero (the stage is `overflow-auto`, so the floor scrolls instead of clips).
 *   • cap (`max-h`) — the same reasoning as the existing 88rem width cap: on a very tall display an
 *     unbounded stretch distorts a figure that is normally wider than it is tall.
 */
export type ArtboardFrame = {
  /** Cross-axis alignment for the stage (composed with the stage's own layout classes). */
  alignClass: string;
  /** Card sizing classes — the floor + cap that bracket a stretched card. */
  cardClass: string | undefined;
  /** Inline card sizing. Carries NO height: the stage owns the vertical axis. */
  cardStyle: { width: string; maxWidth: string } | undefined;
};

export function artboardFrame(fixed: boolean): ArtboardFrame {
  if (fixed) {
    // Declared size wins: top-align so a tall figure overflows downward and stays scrollable
    // (centring would push its top out of view AND out of scroll reach).
    return { alignClass: "items-start", cardClass: undefined, cardStyle: undefined };
  }
  return {
    alignClass: "items-stretch",
    cardClass: "min-h-[20rem] max-h-[56rem]",
    // Fill the available width (so collapsing the side rails gives the figure more room instead of
    // opening a dark gap), capped so it never stretches absurdly wide on an ultra-wide monitor.
    cardStyle: { width: "100%", maxWidth: "88rem" },
  };
}
