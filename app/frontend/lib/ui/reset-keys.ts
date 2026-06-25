/**
 * Shallow `resetKeys` comparison for `<ErrorBoundary>` / `<PaneBoundary>` (Task B1).
 *
 * A stuck boundary auto-clears only when the switch identity it watches actually changes
 * (figure / dataset / skill id, or the spec reference). `Object.is` so a stable reference — or a
 * `NaN` key — doesn't false-trigger a reset. Pure + framework-free so it unit-tests in node-env.
 */
export function keysChanged(
  a: ReadonlyArray<unknown> = [],
  b: ReadonlyArray<unknown> = [],
): boolean {
  return a.length !== b.length || a.some((v, i) => !Object.is(v, b[i]));
}
