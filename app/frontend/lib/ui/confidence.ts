/**
 * Confidence tone palette — the single source of truth for the colour SEMANTICS shared by every
 * "how sure are we?" surface (the reproduction data-fit bands, the data-type detector, …). Each
 * surface keeps its OWN vocabulary (a band/level → tone map) and its own labels; this module owns
 * only what each tone LOOKS like, so green-means-good / amber-means-caution / slate-means-quiet
 * reads identically across the app. Pure data (no React) so libs and UI components can both import
 * it without dragging a client component into a server/lib module graph.
 */

export type ConfidenceTone = "positive" | "caution" | "neutral" | "negative" | "muted";

/**
 * Canonical colour per tone. `neutral` is a deliberately low-chroma slate so an "unsure / likely"
 * verdict recedes (quiet, not alarming) while the chromatic tones (good / caution / wrong) draw the
 * eye — yet still meets contrast, because quiet means low saturation, not low legibility. Consumed
 * for chip tints, the data-fit score-bar fill, and the picker dot: one colour, every place a tone
 * shows. Values are promoted from the reproduction data-fit bands (the original source of truth).
 */
export const TONE_COLOR: Record<ConfidenceTone, string> = {
  positive: "#10b981", // emerald — good / strong
  caution: "#f59e0b", // amber — fits, with caveats
  neutral: "#64748b", // slate — can't confirm (the quiet one)
  negative: "#ef4444", // red — wrong / not a fit
  muted: "#6b7280", // gray — couldn't read
};
