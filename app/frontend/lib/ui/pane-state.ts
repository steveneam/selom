/**
 * Pane state machine (architecture-consistency-gate, Task B3 · plan Spine 3).
 *
 * Selom's panes are bespoke and data-dependent: an inspector tab, the Figure-data inputs, a stats
 * table. Modelled as parallel booleans (`loading`, `error`, `data?`) they drift into impossible
 * combinations and render different OUTER shapes depending on what's arrived — a pane vanishes to
 * `null` while loading, an empty result looks identical to a failed one, a hung fetch spins forever.
 *
 * `PaneState` is the one discriminated union every pane resolves to; `<PaneShell>` (components/ui)
 * renders a STABLE outer shape from the tag, so a pane always occupies the same slot and the seven
 * states are visually distinct. B1 isolates a *throw*; B2 stops the throw at the spec seam; B3 gives
 * the surviving pane a typed state instead of an ad-hoc boolean soup.
 *
 * Pure + framework-free so it unit-tests in node-env vitest; the React `<PaneShell>` consumes it.
 */

export type PaneStatus = "idle" | "loading" | "empty" | "partial" | "stale" | "error" | "ready";

/**
 * The state of one pane. `data` rides only the content states (`ready`/`partial`/`stale`); `message`
 * annotates `empty`/`error`; `note` annotates the degraded content states; `retry` lets an `error`
 * fallback re-attempt (e.g. re-fetch a param-spec). The union — not parallel booleans — makes
 * impossible combinations unrepresentable.
 *
 * - `idle`    — nothing requested yet (no skill/figure selected).
 * - `loading` — a fetch/compute is in flight → a skeleton, never a vanished pane.
 * - `empty`   — loaded successfully, but there's nothing to show (no inputs, no points).
 * - `partial` — usable data, but incomplete (some inputs missing) — content + a note.
 * - `stale`   — data shown, but known out of date (upstream changed) — content + a note.
 * - `error`   — the load/compute failed or timed out → a message + optional retry, NOT a spinner.
 * - `ready`   — complete data to render.
 */
export type PaneState<T = unknown> =
  | { status: "idle" }
  | { status: "loading"; label?: string }
  | { status: "empty"; message?: string }
  | { status: "partial"; data: T; note?: string }
  | { status: "stale"; data: T; note?: string }
  | { status: "error"; message?: string; retry?: () => void }
  | { status: "ready"; data: T };

/** A content state — one that carries `data` the pane can render. */
export type ContentPaneState<T> = Extract<PaneState<T>, { data: T }>;

/** True when the state carries renderable `data` (ready/partial/stale). Narrows the union. */
export function hasData<T>(state: PaneState<T>): state is ContentPaneState<T> {
  return state.status === "ready" || state.status === "partial" || state.status === "stale";
}

/** True while the pane is waiting on a first result (idle or loading) — show a skeleton, not data. */
export function isPending(state: PaneState): boolean {
  return state.status === "idle" || state.status === "loading";
}

/** True for the degraded-but-usable content states (partial/stale) → content plus a note. */
export function isDegraded(state: PaneState): boolean {
  return state.status === "partial" || state.status === "stale";
}
