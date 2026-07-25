/**
 * Ambient types for `plotly.js/dist/plotly` — the PRE-BUILT bundle.
 *
 * `@types/plotly.js` only declares the package root (`plotly.js`), which resolves to the
 * source build. That is a *different module instance* from the dist bundle, so importing it
 * would ship a second full copy of Plotly and hand back an object that never saw our graph
 * divs. `react-plotly.js` requires `plotly.js/dist/plotly`, so that is the specifier we must
 * use to reach the live instance — and it is untyped, hence this file.
 *
 * Declared narrowly on purpose: only the surface `lib/figure/plot-resize.ts` actually calls.
 * Widen it deliberately, or not at all.
 */
declare module "plotly.js/dist/plotly" {
  const Plotly: {
    Plots: { resize: (gd: HTMLElement) => Promise<unknown> };
  };
  export default Plotly;
}
