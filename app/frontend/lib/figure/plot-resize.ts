/**
 * Reflow a Plotly figure when its CONTAINER changes size (W-1).
 *
 * Plotly's responsive mode — react-plotly.js's `useResizeHandler` — listens for `window.resize`
 * and nothing else. A container that changes size on its own (a rail collapsing, a dock opening,
 * a panel toggling) fires no window event, so the figure keeps its old width inside a bigger box.
 * Measured at 1280x800 on a real volcano: collapsing the project workrail grew the artboard card
 * by 208px and the plotting area by ZERO; a subsequent window nudge then added 205px, which is the
 * whole bug in one number (browser-verify `remedy-sizing`, 2026-07-25). Every collapse control the
 * editor grows — the inspector dock, the AI panel, the version bar — inherits it.
 *
 * The reflow is per-container, deliberately NOT a synthetic `window.resize`: that would re-lay-out
 * every figure on the page (the compare panes included) because one pane changed.
 */

/** The slice of the Plotly bundle we need. `Plots.resize` is what react-plotly calls itself. */
type PlotlyResize = { Plots: { resize: (gd: HTMLElement) => Promise<unknown> } };

let plotlyPromise: Promise<PlotlyResize> | null = null;

/**
 * The Plotly bundle, resolved lazily and only from a browser callback.
 *
 * It MUST stay a dynamic import: a static value-import of plotly at module scope puts it in the
 * SSR render graph, where it touches `window` at module scope and 500s every page — the ratchet
 * for that is `ssr-plotly-import.test.ts`, which also pins this file as the one allowed dynamic
 * plotly import. `react-plotly.js` requires `plotly.js/dist/plotly` internally, so this resolves
 * the very module instance the `dynamic(…, { ssr:false })` canvas already loaded — no second copy.
 */
function plotly(): Promise<PlotlyResize> {
  plotlyPromise ??= import("plotly.js/dist/plotly").then(
    (m) => ((m as { default?: unknown }).default ?? m) as PlotlyResize,
  );
  return plotlyPromise;
}

/**
 * Ask Plotly to re-lay-out `gd` at its container's current size. Best-effort: a hidden or
 * torn-down graph div rejects, and a figure that failed to reflow must never break the editor.
 *
 * A fixed-size figure needs no guard here — Plotly's own `Plots.resize` returns early when the
 * layout carries an explicit width and height — but callers skip observing one anyway (below).
 */
export async function resizeGraphDiv(gd: HTMLElement): Promise<void> {
  try {
    const Plotly = await plotly();
    await Plotly.Plots.resize(gd);
  } catch {
    // Intentionally swallowed: a reflow is an enhancement, never a failure path.
  }
}

/**
 * Call `onResize` when `el`'s size actually changes, at most once per animation frame.
 * Returns a disposer; safe where `ResizeObserver` is absent (jsdom, older engines) — it simply
 * does nothing, leaving the pre-existing window-resize behaviour untouched.
 *
 * Two things are deliberately NOT a resize, because re-laying-out on them would be work the user
 * did not ask for: the observer's initial callback (it reports the size the figure was already
 * laid out at) and any later callback reporting identical dimensions.
 */
export function observeContainerResize(el: Element, onResize: () => void): () => void {
  if (typeof ResizeObserver === "undefined") return () => {};

  let last: { w: number; h: number } | null = null;
  let frame = 0;

  const observer = new ResizeObserver((entries) => {
    const box = entries[entries.length - 1]?.contentRect;
    if (!box) return;
    // Sub-pixel jitter from a flex/zoom reflow is not a size change; round before comparing.
    const w = Math.round(box.width);
    const h = Math.round(box.height);
    if (last && last.w === w && last.h === h) return;
    const first = last === null;
    last = { w, h };
    if (first) return;
    // Coalesce a burst (a CSS transition fires one callback per frame) into a single resize.
    // A pending frame already covers this change: it re-measures the live DOM when it runs.
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      onResize();
    });
  });

  observer.observe(el);
  return () => {
    if (frame) cancelAnimationFrame(frame);
    observer.disconnect();
  };
}
