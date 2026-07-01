# project-workspace.tsx — contract-frozen decomposition — spec

> Status: **draft, awaiting owner approval** · 2026-07-01 · Claude lane.
> A **behavior-preserving** refactor (no feature change): split the 1347-line `ProjectWorkspace`
> composition root into a thin shell + focused hooks + presentational view components, so the next
> additions (task 2 ingest `<AskAi>`, pillar-2, …) land in a structure, not a wall. Continues the
> established pattern ([[contract-frozen-refactor]] — `main.py→routers/`, the first
> `project-workspace→hooks` pass) and the repo conventions ([[selom-repo-structure-conventions]]:
> split on responsibility; extract orchestration into `useX`; cohesive ≤~600-line presentational
> components stay whole; no `lib` barrels — n/a here, components dir).

## What

`components/project/project-workspace.tsx` is a composition root that already delegates orchestration
to hooks (`useFigureRun`, `useAiHelpers`, `useFigureCrud`, `useWorkspaceView`) and ~18 panels. But at
**1347 lines** it still carries three concerns inline: (1) the **figure-data staging** cluster, (2) a
large **per-view JSX switch** (`view === figure|figuredata|compare|data|skill|stats|home`), and (3)
small nav/keyboard handlers. This refactor extracts (1) into a hook and (2) into presentational view
components behind a thin view-router, leaving `ProjectWorkspace` a ~300–400-line shell. **No behavior
changes**; the JSX and logic move verbatim; tsc + vitest (438) + the FE structure guard are the safety
net; the frozen external contract is "the running workspace behaves identically."

## Context — the current shape (what moves)

| Region (current lines) | Concern | Destination |
|---|---|---|
| `fdParams`/`fdBaseParams`/`fdScope`+reset/`fdDirty`/`previewSpec`/`markLabelsShown` (150–210) · `onThresholdChange` (373) · `onMarkChange` · the `onAutoTune` handler (997–1030) | **figure-data staging + live preview + Auto-tune** — one cohesive concern | **`hooks/use-figure-data-staging.ts`** (new) |
| `view === "figuredata"` block: pending banner + `<AskAi analyze>` + `<FigureDataPanel>` (861–1090) | the analyze dock | **`views/figure-data-view.tsx`** (new) |
| `view === "figure"` block: `<EditorWorkspace>` composition (702–843) | the figure editor view | **`views/figure-view.tsx`** (new) |
| `view === "skill"` block: `<WorkbenchPanel>` + route `<AskAi>` (1118–1160) | the run-skill view | **`views/skill-view.tsx`** (new) |
| `view === "compare"` (844–860) · `"data"` (1106–1117) · `"stats"` (1161–1196) | thin wrappers over existing `CompareView`/`DataPanel`/`StatsPanel` | stay inline in the router (already components) or a 1-line wrapper |
| header switch (590–621) | the per-view page header | **`workspace-header.tsx`** (new) if it clears ~40 lines; else leave |
| `ProjectOverview` / `EmptyState` / `OverviewStat` (1210–1347) | already private subcomponents | move to `views/project-overview.tsx` (co-locate) |
| the `return (…)`: header + `<Workrail>` + view-switch + `<AiPanel>` | the layout shell + view-router | stays in `project-workspace.tsx` (the thin root) |

The hooks already extracted (`useFigureRun`/`useAiHelpers`/`useFigureCrud`/`useWorkspaceView`/`useProjects`/
`useWorkspace`/`useFigureStore`) are unchanged.

## Requirements

- **R1. Byte-identical behavior.** No user-visible change, no changed props on the leaf panels
  (`FigureDataPanel`, `WorkbenchPanel`, `EditorWorkspace`, `CompareView`, `DataPanel`, `StatsPanel`,
  `AiPanel`, `Workrail`). The 7 spine invariants are untouched (this is pure code motion).
- **R2. `use-figure-data-staging` owns the fd* concern** and returns a typed bundle consumed by the
  root + the figure-data view. It encapsulates: `fdParams`/`setFdParams`, `fdBaseParams`, `fdScope`,
  the derive-on-scope-change reset (incl. `applyAcceptedProposals`), `fdDirty`, `previewSpec`,
  `markLabelsShown`/`setMarkLabelsShown`, `onThresholdChange`, `onMarkChange`, and `autoTune` (the
  deterministic Auto-tune handler shipped in `docs/auto-tune/spec.md`). It takes what it needs
  (`activeFigure`, `activeDataset`, `figure.spec`, and the AI-helper setters it currently shares).
- **R3. View components are presentational** — they receive explicit props (everything the moved JSX
  references today) and render; they hold no orchestration state of their own beyond trivial local UI.
  Each is its own file under `components/project/views/`.
- **R4. A thin view-router** in `project-workspace.tsx` maps `view` → the view component (a `switch`/
  ternary chain, same conditions as today). **No barrel `index.ts`** for `views/` — the root imports
  concrete paths (structure-guard rule).
- **R5. The memoization eslint warnings are resolved, not relocated.** Moving `onThresholdChange`/
  `onMarkChange`/`onAutoTune` into the focused hook lets their deps be stated correctly (the current
  `preserve-manual-memoization` warnings at project-workspace 366/373 stem from the React Compiler on
  the big component). Target: **eslint 0 warnings** on the touched files (down from the 5 pre-existing).
- **R6. `project-workspace.tsx` ends ≤ ~450 lines** (from 1347) and reads as: hooks wiring → derived
  values → the layout shell + view-router. (Guideline, not a hard cap — R1 wins over any line target.)

## Design

- **Extraction order (each step compiles + tests green before the next — no big-bang):**
  1. `use-figure-data-staging` hook (the largest cohesive logic block; unblocks the figure-data view).
  2. `views/figure-data-view.tsx` (consumes the hook bundle; the biggest JSX block).
  3. `views/figure-view.tsx`, `views/skill-view.tsx`, `views/project-overview.tsx`.
  4. The view-router + `workspace-header.tsx`; delete the now-dead inline blocks.
- **Frozen contracts (the safety net's anchor):** the leaf panels' props do not change; each new hook/
  view exposes a typed interface; the JSX moves verbatim (same class names, same handlers). A diff that
  changes a leaf panel's props is out of scope — flag it, don't fold it in.
- **Directory:** new `components/project/views/` (peer of the existing `hooks/`); the hook joins
  `components/project/hooks/`. No `index.ts` barrels.

## Invariants

- The FE **structure guard** (`lib/structure.guard.test.ts`) stays green; no new `lib` flat modules or
  barrels; heavy/WebGL stays behind `dynamic(ssr:false)` (unchanged — the moves don't touch imports of
  plotly). The **SSR-plotly import test** stays green.
- The 7 spine invariants hold trivially (no logic change): render=f(spec), AI-compiles-away, one
  provenance chokepoint, apply-discipline, deterministic-primary, one pending queue, inference-first.
- Undo/redo, the pending banner, staleness, versioning, the AI panel overlay — all behave identically.

## Testing Strategy

- **tsc** clean; **vitest** 438 unchanged (no test should need editing — behavior is identical; if a
  test needs changing, the refactor changed behavior → stop and reassess).
- **eslint** 0 errors AND 0 warnings on the touched files (R5).
- **Browser smoke** ([[full-app-smoke-test-before-handoff]] — this is exactly the SSR/integration class
  a refactor can break): load the running app (real backend, `npx next dev --webpack`) and walk each
  view — home → figure → figure-data (Auto-tune still works) → compare → stats → data → skill → AI
  panel — confirming each renders and the console is clean. One end-to-end pass, since code motion can
  break a wiring tsc/vitest won't catch.

## Out of Scope

- **Task 2** (Layer A ingest AI half) — separate; it *benefits* from this landing first.
- Any behavior/feature/prop change to the leaf panels or the hooks' logic. A tempting "while I'm here"
  fix is a separate change.
- Pillar-2 / the editor canvas.
- Renaming or re-homing the already-extracted hooks (`useFigureRun` et al.).
