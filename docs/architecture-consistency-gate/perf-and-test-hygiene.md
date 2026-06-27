# Task E — Performance + memory proof (E1 + E2)

Last updated: 2026-06-27 — Claude. Companion to `roadmap.md` (Task E buckets) and
`plan.md`. Status: **E1 + E2 shipped + verified.** These are the last two DB-free buckets;
per the discussion gate in `roadmap.md`, **STOP for the owner before any materialization
bucket (C4 · D4 · F1–F3).**

Task E is the *proof* layer: it makes the figure-render path's memory behaviour and timing
explicit and guarded, rather than an emergent property. Most of it was already true (the
Task B exit measured a flat heap across ~150 switches); E1/E2 make purge/budget/timing
**explicit** and add **regression guards** so a future edit can't silently regress them.

---

## E1 — Plotly leak hardening

The figure is the one heavy, GPU-backed, listener-bearing surface in the app. Three moves,
all in `components/figure/figure-canvas.tsx` + `lib/figure/webgl-budget.ts`:

### 1. Explicit teardown on unmount
react-plotly.js calls `Plotly.purge(gd)` in its own unmount, which tears down the WebGL
context and Plotly's internal listeners (proven by the Task B exit: canvas count → 0 at
home). On top of that, FigureCanvas now **captures the graph div** (`gdRef`) and, on unmount,
**explicitly removes the three gesture listeners we bound directly** (`plotly_relayout` /
`plotly_restyle` / `plotly_click`), disposes every imperative drag wiring, and nulls the
refs — so nothing *we* attached can outlive the component (the leak surface in our control).
Idempotent with react-plotly's purge.

### 2. Stable data/layout references
The render spec (`figure`), the SVG-overflow projection (`renderData`), and `config` are all
`useMemo`'d, so Plotly is handed **stable** references across renders — a fresh object every
render would make react-plotly re-run `Plotly.react` needlessly and churn the WebGL context.

### 3. WebGL context budget — `lib/figure/webgl-budget.ts`
A `scattergl`/`*gl` figure consumes a scarce WebGL context; past the browser ceiling (~16)
the oldest context is silently lost (blank figure + "too many active WebGL contexts"). The
editor mounts ≤2 GL canvases today (Compare A/B; the editor canvas and the Figure-data
preview are mutually-exclusive views), so this is a **forward safety net**, not a present-day
limiter:

- a single named cap, `MAX_GL_CONTEXTS = 8`;
- each GL canvas claims a budget slot (keyed by a stable `useId` token) on mount, frees it on
  unmount, read via `useSyncExternalStore` so a denied overflow canvas re-upgrades the instant
  a slot frees;
- **under budget** (the only case the current UI reaches) → unchanged, always GL;
- **over budget** → the overflow canvas renders its GL traces as SVG (`toSvgTraces`,
  `scattergl`→`scatter`) instead of losing a context. Pure projection — the canonical spec is
  untouched.

### SSR discipline (audited)
plotly.js touches `window` at module scope, so a *value* import anywhere in the SSR graph
500s every page (it once did — `[[full-app-smoke-test-before-handoff]]`). `react-plotly.js`
enters only via `dynamic(() => import(...), { ssr: false })`; `plotly.js` is `import type`
only. Guarded by `lib/figure/ssr-plotly-import.test.ts`, which scans the whole frontend tree
and fails on any static, non-type Plotly import.

### Acceptance — heap-snapshot diff (chrome-devtools MCP, real fixtures, no backend)
Opened the volcano fixture (`p_3384a01f`, scattergl), reset telemetry, took a baseline heap
snapshot, drove **20 figure switches** (alternating the two versions through the real React
handlers), took a second snapshot. **The leak-defining counts are flat:**

| node class | before | after |
| --- | --- | --- |
| `HTMLCanvasElement` | 4 | **4** |
| `Detached HTMLCanvasElement` | 0 | **0** |
| `WebGLRenderingContext` | 6 | **6** |
| `WebGL2RenderingContext` | 1 | **1** |
| `EventListener` | 1452 | **1452** |
| `V8EventListener` | 1320 | **1320** |

Live DOM canvas count stayed at **3** throughout (never accumulated), console clean (only the
expected param-spec 404s — B3 floor, no backend — no error-boundary / Plotly / WebGL errors).
The +26 generic detached-DOM / +4.5 MB are transient React-reconciliation nodes pending the
next GC (a single-pass snapshot artifact), none of them canvases / contexts / listeners.

---

## E2 — Telemetry + test hygiene

### Render-timing telemetry — `lib/figure/perf.ts`
A bounded ring buffer of figure-draw durations + summary stats (count / mean / p50 / p95 /
peak). FigureCanvas stamps the commit time (`useLayoutEffect`) and records the commit→draw
delta when Plotly's `onInitialized`/`onUpdate` fires. `installPerfHook()` exposes a read API
on `window.__selomPerf` (`stats()`, `reset()`, `heapMB()`) for the audit. A relative
regression signal, not an absolute frame budget.

### Payload ceiling — `lib/figure/payload.ts`
`figurePayload(spec)` → `{bytes, points, traces}` (2-D `z` flattened) + advisory ceilings
(`PAYLOAD_BYTE_CEILING` 8 MB, `PAYLOAD_POINT_CEILING` 200k). FigureCanvas surfaces a
once-per-figure dev-console warning when a figure exceeds a ceiling (the `warnDeadKnob`
discipline — non-blocking telemetry).

### Perf-audit script — `scripts/perf-audit.mjs`
Playwright + **system Chrome** (`channel: "chrome"`, no Chromium download — matches
`playwright.config.ts`). Seeds a synthetic two-figure project into localStorage (no backend,
no curated fixtures needed), opens a figure, drives N switches, and reports cold vs warm
p50/p95/peak (from `window.__selomPerf`) + peak heap + max live canvas; exits non-zero if the
canvas count climbs past the budget. Run with `npm run test:perf` (dev server up).

### Fast vs slow test split
- **FE fast gate** — `npm run test:fast` (= `vitest run`): the pure `lib/**` unit suite, **340
  tests in ~8 s**. This is the "feature commit runs the fast gate in seconds" inner loop.
- **BE fast gate** — `pytest -m "not slow"`: **695 tests in ~56 s** (vs the full ~14 min
  suite). The heavy lanes (reproduction drives, golden renders across every skill, real-engine
  scverse validations) carry `@slow`, **auto-tagged by file** in `tests/conftest.py` (no
  per-test edits — a new heavy file joins the set there). Heavy lane: `pytest -m slow`
  (357 tests).
- **Slow / proof lanes** — `npm run test:e2e` (Playwright), `npm run test:perf` (this audit),
  the chrome-devtools heap-snapshot diff, and `pytest -m slow`.

### Acceptance — recorded cold/warm (this machine, dev/webpack)
| metric | value | note |
| --- | --- | --- |
| cold first draw | ~4.6–8.2 s | **dev-only** — includes the one-time webpack route compile + Plotly chunk load; not a production cold |
| warm render p50 | 60–89 ms | over 20 switches (varies with point count / load) |
| warm render p95 | 78–132 ms | |
| warm render peak | 95–138 ms | |
| peak JS heap | ~244–276 MB | live `usedJSHeapSize`; ~257 MB post-GC (heap snapshot) |

Measured two ways that agree: the chrome-devtools MCP pass on the real volcano fixture
(p50 88.6 / p95 131.8 / peak 138 ms; ~16.7k-row DE) and `scripts/perf-audit.mjs` on an 8k-point
synthetic (p50 60.1 / p95 78.5 / peak 94.6 ms; peak heap 243.9 MB; max canvas 3 / budget 8).

---

## Test / guard inventory (Task E)
- `lib/figure/webgl-budget.test.ts` — GL trace detection, SVG projection purity, budget
  claim/release + overflow denial + free-on-release + subscriber notify.
- `lib/figure/ssr-plotly-import.test.ts` — no static non-type Plotly import in the FE tree.
- `lib/figure/perf.test.ts` — percentile, ring-buffer cap, stats, SSR-safe window hook.
- `lib/figure/payload.test.ts` — point counting (scatter/heatmap/bar), ceiling warnings.
- `tests/conftest.py` `pytest_collection_modifyitems` — the `slow` auto-tagging (+ the marker
  registered in `pyproject.toml`).
