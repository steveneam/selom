# Skills-agnostic figure editor + skill↔pipeline wiring — spec

Status: **DRAFT — review gate** · 2026-06-22 23:55 +10:00 (Australia/Sydney) · Author: Claude (Opus 4.8)
Owner decision required before any build (see §9).

## 1. Problem

Running real data (the ERG trace-grid) for real work surfaced that **the figure editor
and the skills don't talk to each other**, and the editor is implicitly built for
**scatter/marker** plots. Concretely:

- `lib/figure-spec.ts::normalizeSpec` force-injects `marker:{size:7,opacity:0.9}` onto
  **every** trace. The Style panel then reads `/data/0/marker/*` and always shows
  *Point size / Opacity / Okabe–Ito palette* — even for a line, heatmap, sankey, or
  radar figure where those controls do nothing.
- The Data-tab colour swatch reads/writes `marker.color`. The ERG grid is **line**
  traces (`line.color`), so the swatch shows the wrong colour and editing it is a no-op.
- The single colourway/palette picker only affects `layout.colorway`-driven figures.
- Layout primitives the skills emit — scale bars, threshold lines, multi-axis subplot
  grids, colour bars, annotations — are mostly invisible to the editor (only colour bar
  has partial support via `findColorbarTrace`).
- The skill's own parameters (`skill.json::param_spec`) never reach the figure. To change
  a filter / smoothing / representative you must leave the figure and re-run from the
  Workbench box.

### Evidence — skill-output survey (30+ skills)
- **11 distinct figure archetypes**: marker-scatter (pca/umap/annotate), scatter+overlays
  (volcano/trajectory/regression), heatmap (heatmap/corr_heatmap), bar/box
  (deg/composition/boxplot/pvca), dotplot (enrichment/markers), multi-axis grid
  (upset/normalization_qc/gsea), network (string_network/go_graph), radar (scorecard),
  sankey, violin, **small-multiples trace-grid** (ERG / `_tracegrid.py`).
- **4+ colour mechanisms**: per-trace `marker.color`; per-trace `line.color`; per-point
  numeric array + `colorscale`; heatmap `z` + `colorscale`; `layout.colorway`.
- **~13 of 30+ skills (~40%) do not fit** the current marker-centric controls.

The root cause is a **missing contract** between a skill's output and the editor: the
editor guesses "markers" from the raw Plotly spec and guesses wrong.

## 2. Goals / non-goals

**Goals**
1. A cosmetic editor that **adapts to any skill's figure** (the agnostic floor) — shows
   only the controls that apply, edits the correct colour channel, and is aware of the
   primitives present.
2. **Wire skill parameters into the pipeline**: a "Figure data" stage that surfaces a
   skill's `param_spec` next to its figure and re-runs in place (owner-decided).
3. **Figure-forward** layout: the artboard is the hero; analysis chrome relocates
   (owner-decided).

**Non-goals (this spec)**
- Editing underlying data values (x/y) client-side — stays a backend re-run.
- A bespoke editor per skill. We want *kind-aware*, not *skill-coded*.
- New skills or new figure types.

## 3. Design overview

Two halves, both skills-agnostic:

- **(A) Adaptive cosmetic editor** — driven by a derived `FigureModel` (inference-first,
  optionally refined by skill hints).
- **(B) Figure data stage** — driven by the declarative `param_spec` already in
  `skill.json` (so every parameterised skill gets it for free).

### 3.1 The contract — inference-first, hints-optional

The **agnostic floor is inference**: the editor derives everything it needs from the
Plotly spec, so *every* figure (including third-party / future skills that emit nothing
special) gets a correct editor. Skills may **optionally** stamp hints to sharpen it.

Derived (computed in `lib/figure-model.ts`, memoised from the spec):

```ts
interface FigureModel {
  traceKinds: TraceKind[];                 // per trace: markerScatter | lineScatter |
                                           //   heatmap | bar | box | violin | sankey |
                                           //   polar | network | other
  series: Series[];                        // editable series with the CORRECT colour path
  primitives: Primitive[];                 // scalebar | threshold | colorbar | annotationSet | subplotGrid
  capabilities: {                          // which Style groups to render
    markers: boolean; lines: boolean; colorscale: boolean;
    colorbar: boolean; scalebar: boolean; subplotRanges: boolean;
  };
}
interface Series {
  label: string;                           // legend name (or grouped label, see §3.3)
  traceIndices: number[];                  // ≥1 trace (grouped)
  colorPath: string | null;               // "/data/3/line/color" | "/data/3/marker/color" | null (colorscale)
  color: string | null;
  visible: boolean;
}
```

Optional refinement — a skill stamps `layout.meta.selom` (Plotly ignores `meta` at
render, so it never affects the figure or export):

```ts
layout.meta.selom = {
  figureKind: "trace_grid",
  series: [{ label: "Control", traceIndices: [0,6,12,18,24,30], colorPath: "line.color" }, ...],
  primitives: [{ kind: "scalebar", shapeIdx: [0,1], annoIdx: [0,1], xLen: 100, yLen: 200 }],
}
```

Inference covers the floor; hints make grouping/primitives **deterministic** instead of
heuristic. The editor must work with `meta.selom` absent.

### 3.2 Adaptive inspector (Style + Data)

- **Style panel** renders control groups **conditionally** from `capabilities`:
  - lines present → **Line width / colour** (per series),
  - markers present → **Point size / opacity / colour**,
  - colour-mapped / heatmap → **colorscale + reverse + zmid/zmin/zmax**,
  - colour bar present → existing position/length controls,
  - **Background / fonts** stay universal.
- **Palette**: for colourway-driven figures, keep the colourway swap; for
  per-series-coloured figures, "Apply palette to series" writes each series' *real*
  channel.
- **Data panel**: read/write the **correct colour channel per trace** (fixes the
  `line.color` no-op), and **group traces into series** (a 42-trace ERG grid shows the
  **6 conditions**, not 42 rows) via `legendgroup` or the `meta.selom.series` hint.
- **Stop `normalizeSpec` force-injecting `marker`** onto non-marker traces (only ensure
  the substructure the panel will actually edit, per detected kind).

### 3.3 Series grouping

ERG emits 42 traces (6 conditions × 7 intensities) that share a colour per condition.
Group them so editing is per-condition:
- Preferred: the trace-grid emits `legendgroup` (= condition) + `meta.selom.series`.
- Fallback inference: group by identical colour + name prefix.

### 3.4 Click-to-select a line → recolour

`FigureCanvas` binds `plotly_click` → `points[0].curveNumber` → resolve to its **series**
→ focus it in the Data/Style panel and write colour to the correct channel. Offer "apply
to the whole series" (recolours all traces in the condition). Generic across kinds.

### 3.5 Primitives — generic, owner-controlled

- **Scale bar**: recognised as a first-class primitive (a tagged pair of paper-referenced
  line shapes + unit annotations). Editor can **show/hide**, **resize** (`xLen`/`yLen`),
  reposition. Tagged via `meta.selom.primitives` so the editor finds it deterministically
  (vs. guessing among `layout.shapes`). A generic **"Add scale bar"** is available for any
  Cartesian figure with shared axes; the trace-grid keeps **emitting** it by default, and
  the editor manages it thereafter. (Answers "is it accurate? / how did it appear? / can I
  add-remove it?": it is computed by `_tracegrid.grid_spec` to the shared data→paper
  mapping — accurate for every panel because all panels share one range — and will become
  a toggleable primitive.)
- **Threshold lines / annotations**: list + show/hide/edit.

### 3.6 Figure data stage (owner-decided: new pipeline box)

- New stage between **Statistics** and **Figure**: `Data → Skill → Statistics →
  **Figure data** → Figure → Publish`.
- Renders the active figure's skill `param_spec` (declarative in `skill.json`) as controls,
  prefilled from the figure's `provenance.params`; **Re-run** → a new figure version
  (reuses `runSkill` + `projectStore.addFigure`, like the existing sweep/re-run).
- **Generic**: any skill with a `param_spec` gets this stage for free. For ERG the controls
  are filter / low-pass / scale-bar size / representative.
- The **data-check** routing card and **data-fit** verdict relocate here (they are about
  the data behind the figure).

### 3.7 Figure-forward (owner-decided)

Figure view = toolbar + version bar + **artboard** (hero) + cosmetic inspector.
Publish-confidence collapses to a slim, expandable strip. Routing/data-fit move to §3.6.
(The artboard-top-clipping fix — `items-start` — already shipped this session.)

## 4. Files touched (estimate)

- New: `lib/figure-model.ts` (inference + hint merge), `components/figure/panels/*`
  (adaptive groups), a `FigureDataPanel` view component.
- Edit: `lib/figure-spec.ts` (normalizeSpec marker injection), `panels/style-panel.tsx`,
  `panels/data-panel.tsx`, `figure-canvas.tsx` (click), `pipeline.tsx` (+stage),
  `project/workrail.tsx` (+rail node), `project/project-workspace.tsx` (view routing,
  relocate chrome).
- Backend (small, opt-in): `_tracegrid.py` / proprietary `erg_traces` emit `legendgroup`
  + `layout.meta.selom` hints; a `scalebar` param toggle. No change to other skills.

## 5. Invariants

- **Render = f(spec)**; all cosmetic edits are JSON-Patch on the spec.
- **Agnostic floor**: the editor must produce a correct, useful inspector with **zero**
  `meta.selom` hints (inference-only path is tested).
- Cosmetic edits never touch the backend; **data edits** go through a re-run (versioned,
  provenance-stamped).
- `meta.selom` is render-inert (never affects the figure or the export).
- No regression for existing scatter/marker figures (umap, pca, volcano, …).

## 6. Risks

- Inference mis-classification (e.g. mixed trace kinds in one figure: trajectory =
  markers+lines+spline). Mitigation: per-trace kinds + capabilities are unions; show a
  control group if **any** trace needs it.
- Grouping heuristic wrong without hints. Mitigation: hints for the skills we own;
  conservative fallback (one series per trace) when ambiguous.
- Scope creep. Mitigation: phase gates (§8); P1 is independently shippable.

## 7. Test plan

- Unit: `figure-model` inference over a fixture per archetype (scatter, line-grid,
  heatmap, sankey, radar, multi-axis) → expected capabilities + series + colour paths.
- Golden: editor renders the right control groups per archetype (snapshot of which
  sections show).
- Regression: existing marker figures unchanged; ERG line colour edits now hit `line.color`.
- E2e (browser): ERG grid → click a Control line → recolour → all 7 Control panels update;
  Figure data stage → change low-pass → Re-run → new version.

## 8. Phases

- **P1 — Adaptive cosmetic editor** (the correctness win, fully agnostic): `figure-model`
  inference, conditional Style groups, per-channel colour in Data, fix `line.color`, stop
  marker injection, series grouping (inference). *Independently shippable.*
- **P2 — Figure data stage + figure-forward** (the decided IA): new pipeline box,
  `param_spec` → re-run, relocate routing/data-fit, slim publish strip.
- **P3 — Primitives + click-to-select + hints**: scale-bar toggle/resize, click-a-line,
  threshold/annotation editing; trace-grid emits `legendgroup` + `meta.selom`.
- **P4 — Design polish** via `impeccable` / `ui-ux-pro-max` (per repo guidelines).

## 9. Decisions for the owner (review gate)

1. **Contract approach** — inference-first with optional `layout.meta.selom` hints
   (recommended), vs require skills to emit hints. *Recommend: inference-first.*
2. **Series grouping** — OK to add `legendgroup` (+ `meta.selom.series`) to the trace-grid
   output so 42 traces edit as 6 conditions? *Recommend: yes.*
3. **Scale bar ownership** — skill keeps emitting it + editor manages (show/hide/resize)
   via a tagged primitive (recommended), vs make it fully editor-owned/optional.
4. **Phase scope for now** — build P1 first (agnostic editor), then P2 (the box)? Or P2
   first because the box is what you asked for? *Recommend: P1 then P2.*
5. **Design-skill pass** — run `/impeccable audit` + `ui-ux-pro-max` on the new surfaces
   before/after build?
