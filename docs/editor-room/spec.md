# The editor's room budget — a collapsible inspector dock + zoom

_Written 2026-07-25 21:45 +1000 (Sydney) · implements owner decision **#13** (`agent_handoff/DECISIONS.md`),
which answered board questions `Q-1` and `Q-2`. Scopes **`W-2`** in `docs/next-session-plan/plan.md`._

**Status: WRITTEN — paused for owner review. No `W-2` code before it is approved.**

## What

At 1280×800 the figure gets 90px of plotting area against a ~506px target, because fixed chrome
takes ~70% of the viewport. This spec gives the editor a **room budget**: the 330px inspector dock
gets a collapse control (and auto-collapses on a narrow viewport), and the inert tool-context strip
becomes a real **zoom control** with a Fit action. It also drops the duplicated "Edit a copy" from
the dock. It deliberately does **not** touch the artboard's sizing contract — `W-1` already made the
figure reflow into whatever room it is given, so every pixel this spec frees now reaches the plot.

## Context

**What exists.** The editor is a four-region shell (`components/figure/shell/canvas-shell.tsx`):
a command bar and a tool-context strip on top, a 48px tools rail on the left, `ArtboardHost` as the
hero, and a 330px `InspectorDock` on the right. The artboard's sizing rule lives in one tested place
(`lib/ui/artboard-frame.ts`): **the stage sizes the card, the card never sizes the stage.** A
responsive figure (no numeric `layout.width`) stretches to the stage; a fixed-size figure keeps its
declared export size and the stage scrolls.

**What was measured** (`agent_handoff/lane-wraps/lane3.md` §RESULTS ·
`e2e/browser-verify/remedy-sizing.spec.ts`, real EYG_28 volcano, 1280×800):

| state | stage | card | plotting area |
|---|---|---|---|
| as shipped | 298px | 266px | **90px** (7% of the viewport) |
| workrail collapsed | 506px | 474px | **294px** (23%) |

Fixed columns: app sidebar 256 + project workrail 256 + tools rail 48 + inspector dock 330 = 890px
of a 1280px viewport. The workrail already collapses. **The dock is the only fixed column with no
collapse control at all**, and it is the largest single spender.

**What just landed.** `W-1` (commit `7cc2bc0`) made a figure reflow when its *container* resizes, not
only when the window does. Before it, collapsing a rail bought the plot **zero** pixels — so every
remedy in this spec would have been invisible. The measured relations from that run, which the
projections below use: `card = stage − 32` exactly, and `plot = card − ~180` (Plotly's margins for
this volcano; the constant is figure-specific, the structure is not).

**Owner decision #13**, in force here: the dock collapses and the figure gets zoom-to-fit; **1280
stays a supported width** (so the 506px target is not renegotiable downward); the tools rail **stays**
as a placeholder for Track C's draw tools, so its 48px is not available to spend; and the frozen
figure's duplicated "Edit a copy" keeps the command-cluster affordance.

### The finding that shapes this spec

The board assumed the dock's 330px would close the gap. It does not, and the arithmetic should be on
the record before anything is built. Reaching a 506px plot needs `stage ≥ 718px`, i.e. **+420px** over
today's 298px:

| levers | stage | plotting area | clears 506? |
|---|---|---|---|
| today | 298 | 90 | no |
| workrail collapsed (ships today) | 506 | 294 | no |
| **dock collapsed only** | 580 | **368** | **no** |
| dock fully removed (0px, not proposed) | 628 | 416 | no |
| **workrail + dock collapsed** | 788 | **576** | **yes** |

So the target is reachable **only with both rails collapsed**. That makes "does the editor arrive
with them collapsed at 1280, or does the user collapse them?" the central question of this spec — it
is `D-2` below, and it is the one thing most worth the owner's attention.

## Requirements

1. **R1 — the inspector dock collapses.** A control on the dock collapses it to a thin spine and
   expands it back. Discoverable without hovering, and reachable by keyboard.
2. **R2 — collapsed does not mean gone.** The spine keeps the dock's tabs visible as icons; clicking
   one expands the dock *to that tab*. (Mirrors the workrail, which collapses to a spine of stage
   dots rather than vanishing — `components/project/workrail.tsx`.)
3. **R3 — the editor arrives usable at 1280.** At 1280×800 the plotting area reaches **≥506px** in
   the state the user actually lands in, without the user first discovering two collapse controls.
   (How this is satisfied is `D-2`.)
4. **R4 — the user's choice wins.** Once the user toggles a rail, that choice holds for the session;
   a later resize must not silently undo it.
5. **R5 — zoom exists and tells the truth.** The tool-context strip carries a zoom-% readout, zoom
   in/out, and **Fit**. Fit scales the artboard so the whole figure is visible in the stage. The
   control must never claim a zoom level the artboard is not actually at.
6. **R6 — zoom does not edit the figure.** Changing zoom writes nothing to the spec, creates no undo
   entry, and never touches `layout.width`/`layout.height` — those are the user's **export** size
   (`components/figure/panels/page-panel.tsx`), not a view property.
7. **R7 — one "Edit a copy".** On a frozen figure the action appears once, in the command cluster
   (`components/project/views/figure-view.tsx:135`). The dock's `FrozenNotice` keeps its explanatory
   copy and loses its button.
8. **R8 — both hosts, or neither.** Anything added to the shell must not silently skip the classic
   `EditorWorkspace` (`/extract`'s host). Where a rule is shared, it lives in one module both consult
   — the reason `artboardFrame()` exists.

## Design

### Files

| File | Change |
|---|---|
| `components/figure/shell/inspector-dock.tsx` | Add the collapse control + the collapsed spine; drop the `FrozenNotice` button (R7). |
| `components/figure/shell/canvas-shell.tsx` | Own the dock's collapsed state and the zoom level; pass both down. |
| `components/figure/shell/tool-context-strip.tsx` | Becomes the zoom home: keeps the tool hint, gains the zoom cluster on the right. |
| `components/figure/shell/artboard-host.tsx` | Accept a `zoom` prop and apply it (below). |
| `lib/ui/artboard-frame.ts` | Extend the ONE sizing rule to carry zoom, so both hosts get identical behaviour (R8). Its unit test extends with it. |
| `lib/ui/editor-room.ts` (new) | The room rules as pure functions: the auto-collapse threshold, and `fitScale(stage, content)`. Unit-tested in node-env vitest, like `pane-state.ts`. |
| `components/figure/editor-workspace.tsx` | Consume the same shared rule so `/extract` does not drift (R8). |

### The dock collapse

State lives in `CanvasShell` (view-local, like the existing `selection` nonce) — not in the figure
store, because it is not figure state and must not enter undo history. The dock renders one of two
shapes from one boolean, so an impossible half-collapsed state is unrepresentable:

- **expanded** — today's `w-[330px]` aside, plus a collapse button in its top-right corner
  (`aria-label="Collapse inspector"`, `aria-expanded={true}`).
- **collapsed** — a `w-12` spine of the inspector's tab icons (Style · Axes · Legend · Data · Marks ·
  Page) plus an expand button (`aria-label="Expand inspector"`). Clicking a tab icon expands the dock
  and selects that tab, so the spine is a shortcut, not a dead end (R2).

`PropertyPanel` owns the active tab today; the spine needs to *set* it, so the tab value lifts to
`CanvasShell` as a controlled prop with the current default (`style`) preserved — the e2e
`figure-gestures` spec asserts the "Colour bar" heading with no interaction, and that must keep
passing untouched.

### Zoom

**Mechanism: a CSS `transform: scale()` on the artboard card**, with the stage scrolling when the
scaled card overflows. Rationale: it is the only mechanism that is honest for *both* figure kinds.
A responsive figure has no intrinsic size to scale — it *is* the card — so anything that "zoomed" it
by changing its layout width would be creating canvas, not magnifying. A fixed-size figure has an
intrinsic size that must not be touched (R6). A transform magnifies both identically and writes
nothing.

- **Fit** = `min(1, stageW / contentW, stageH / contentH)`. For a responsive figure this is **exactly
  1** by construction (the card already fills the stage), which is the correct and honest answer —
  the control is not lying, the figure genuinely fits. For a fixed-size figure — a 960×640 ERG trace
  grid inside a 266px card, which today simply clips and scrolls — Fit is the first time the whole
  figure is visible at once. That is the real payoff of zoom here, and it is worth stating plainly
  that it is *not* what closes the 1280 gap; the dock collapse is.
- **Zoom in/out** step through a fixed ladder (50 · 75 · 100 · 150 · 200 · 400 %) rather than free
  input — fewer states to verify, and it matches the coarse control the strip has room for.
- Zoom resets to Fit when the figure changes (a new `spec` identity), so a stale 400% never greets
  the next figure.
- **Known trade:** SVG traces scale crisply; `scattergl` traces are canvas-backed and blur above
  100%. Only FACS density plots (`app/backend/skills/_flow.py`) emit `scattergl` today — the volcano,
  UMAP, heatmap and ERG paths are all SVG. Accepted, noted, not worked around.

### Auto-collapse

`lib/ui/editor-room.ts` exports the threshold as a pure predicate so the rule is testable and stated
once. Applied on mount and on a viewport crossing, and suppressed permanently for the session once
the user has toggled that rail themselves (R4).

## Decisions

**D-1 — Zoom is a CSS transform, not a re-layout.** *Alternatives:* re-lay-out the figure at
`stage × zoom` and scroll (reuses `W-1`, stays crisp at any zoom for WebGL too) — rejected because
for a responsive figure that is "more canvas", not zoom: text stays 12px while the plot grows, which
is the opposite of what a zoom control promises. *Reversible:* yes, the mechanism is behind
`artboardFrame()` and swapping it touches one module.

**D-2 — ⚑ OWNER CALL: what is collapsed when the editor opens at 1280?** The arithmetic above says
`R3` (≥506px on arrival) is satisfiable only with both rails collapsed. Three ways to land it:

- **(a) auto-collapse both the workrail and the dock at ≤1280** — arrives at **576px**, meets `R3`.
  Cost: the inspector, which *is* the editing surface, starts as a spine, so the first style edit
  costs one click. Mitigated by `R2` (the spine shows the tabs and clicking one opens straight to it).
- **(b) auto-collapse the workrail only** — arrives at 294px; the user reaches 576px by collapsing the
  dock. Cheaper and less surprising, but **does not meet `R3`**, and decision #13 declined to treat
  1280 as degraded.
- **(c) auto-collapse both, and additionally collapse the app sidebar** — ~776px, more than needed,
  and the sidebar is navigation identity; not recommended.

**Recommendation: (a).** The sequence a user actually runs is *run a skill → look at the figure →
then edit it*: on arrival the figure is the subject and the inspector is not yet in use, which is
precisely when the pixels are worth more to the artboard. It is also the only option that satisfies a
requirement the owner has already refused to relax. *Reversible:* yes — it is one predicate in
`editor-room.ts`. **This is the decision this spec is paused for.**

**D-3 — The threshold is 1280, and it is a viewport-width rule.** Below/at 1280 auto-collapse
applies; above it, nothing is collapsed by default (at 1440 the figure is already comfortable, and at
1920 the stage is 938px). *Assumption:* Selom is desktop-only, so there is no mobile breakpoint to
reconcile ([[selom-desktop-only]]). *Alternative:* trigger on measured stage width rather than
viewport width — more precise, but it makes the rule depend on the very layout it changes (a feedback
loop). Rejected for v1.

**D-4 — Dock state is view-local, not persisted.** It resets per editor mount. *Alternative:*
persist per user in `localStorage`. Deferred: persisting a collapsed inspector risks a user who
collapsed it once at 1280 finding it collapsed forever at 1920 with no memory of why.

**D-5 — "Edit a copy" leaves the dock, not the command cluster.** Beyond the owner's call, `D-2`
makes it structural: an action must not become unreachable because a panel collapsed.

## Invariants

- **The stage sizes the card** (`lib/ui/artboard-frame.ts`). Zoom scales the *rendered* card; it must
  not become a second sizing authority. Guarded by `lib/ui/artboard-frame.test.ts`, extended here.
- **`W-1` keeps working.** Collapsing the dock is exactly the container-resize case `W-1` fixed, so
  `browser-verify remedy-sizing` must stay green — and a dock-collapse equivalent is added to it.
- **No new SSR path for Plotly** — `lib/figure/ssr-plotly-import.test.ts` stays green.
- **Zoom writes nothing to the store** — no spec mutation, no undo entry (R6).
- **Both hosts share the rule** — the structure guard plus `R8`'s shared module.

## Testing Strategy

- **`scripts/browser-verify.sh d5` is the acceptance gate.** The `D-5 (also-confirm)` check currently
  FAILS at 90px; it must go green at ≥506px at 1280×800. Per the board, its threshold may only change
  deliberately, to the owner's number, with a comment naming whose decision it was.
- **A new `e2e/browser-verify/dock-collapse.spec.ts`** — collapse the dock with no window resize and
  assert the plotting area grows (the `W-1` contract on a second control), that the spine's tabs are
  present, and that clicking one expands to that tab.
- **`remedy-sizing.spec.ts` gains the arrival state** — what the plotting area is when the editor
  *opens* at 1280, which is what `R3`/`D-2` are actually about and what no check measures today.
- **Unit (node-env vitest):** `lib/ui/editor-room.test.ts` for the threshold predicate and
  `fitScale()` (including the responsive case returning exactly 1, and a degenerate zero-size stage).
- **`scripts/verify.sh` 7/7**, raw, never piped.

## Out of Scope

- The app sidebar's 256px (`D-2` option (c)) and the tools rail's 48px (decision #13 keeps it).
- Persisting rail state across sessions (`D-4`).
- Any change to the export pipeline: zoom is a view property and export is unaffected (R6).
- The annotation layer's tools — Track C, behind `NEXT_PUBLIC_ANNOTATION_LAYER`.
- Free-form zoom entry, pan-by-drag on the stage, and keyboard zoom shortcuts. The ladder plus Fit is
  v1; add these when a user asks.
