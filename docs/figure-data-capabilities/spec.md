# Spec — Capability-driven figure editing surface (`figure-data-capabilities`)

> **Status: SHIPPED + VERIFIED LIVE (2026-06-25 00:50 +10:00).** Hardened from the stub via the owner
> interview, owner-confirmed, then built + verified on real Diagnosys `453_AAV` data (FE tsc/eslint/vitest
> 199 · BE focused subset + 2 regenerated goldens). **Live-review refinements beyond the original §1–§6
> (owner, 2026-06-25), now the canonical model — see memory `selom-figure-edit-ux-pattern`:** (1)
> **wheel-zoom turned OFF** (a stray scroll on a multi-panel grid is fiddly to undo; zoom = deliberate
> modebar button; `_tracegrid` stamps `scrollZoom:false`, the FE forces it off too); (2) **dot-drag +
> numeric time edits STAGE into one lifted `fdParams` and move the dot LIVE (`applyStagedMarks`,
> client-side) — NO re-run per drag**; the backend re-measures on ONE explicit re-run; (3) a prominent
> **"Pending changes — Re-run" banner** at the top replaced the per-control LIVE/RE-RUN chips (kept only a
> single LIVE tag on the labels toggle); (4) **"Figure data" (amber `--stage-figuredata`) vs "Figure
> styling" (cyan)** — distinct stage colours + the "Figure" → "Figure styling" rename; (5) **magnet**
> proximity dot-grab (24px); (6) label toggle = instant `hideDotLabels` restyle. The §11 generalization
> across all skills remains a next-session roadmap item.

## Interview decisions (owner, 2026-06-24)
The five topics from the resume prompt, answered:

| # | Topic | Decision |
|---|---|---|
| a | **Where the contract lives** | **Extend `meta.selom`** — per-figure, render-inert; `deriveFigureModel` already reads it; the contract can vary by skill *and* by the actual figure instance/data. Inference stays the floor. |
| b | **Default gesture** | **Select / no-op by default; zoom + pan as toolbar (modebar) buttons.** A stray drag must never box-zoom. |
| c | **Figure → tools mapping** | **Per-figure capability flags.** Each figure declares discrete capabilities; the editor inspector tabs **and** the Figure-data panels compose tools from the declared set. No `if skillId` and no figureKind coupling. |
| d | **Scope / build order** | **ERG-first, with a schema built to generalize.** Wire the ERG family now (trace · flicker · bar · intensity); non-ERG figures keep today's behaviour (no regression). **Generalizing the contract across ALL skills is a separate roadmap/phase/pillar item to plan next session** (owner-flagged — see §11). |
| e | **a/b dot UX** | **Synthesis** of options 1+2+3 (owner note): role-**coloured** dots + **pinned** role labels (a/b/N1/P1) with a **show/hide-labels toggle** + a compact **role legend** + a **hover/drag readout** (t·µV·role). Confirm the synthesis in §6. |

## What
The figure editor (cosmetic inspector) and the **Figure-data** window must **recognize each figure's data
+ skill** and present only the right tools. Today the affordances are wired too broadly:
- the ERG landmark-dot **drag** is bound to *any* editable, non-overlay figure (it silently no-ops when
  there are no dots — `figure-canvas.tsx` wires `wireMarkDrag` whenever `store && !overlay && onMarkMove`);
- the landmark **Marks editor** shows whenever `seededMarks.length > 0` (`figure-data-panel.tsx`);
- **zoom** is Plotly's default drag gesture (the canvas sets no `dragmode`).

The fix: generalize `meta.selom` from per-feature hints into a **per-figure capability contract** that
drives the whole editing surface declaratively. A figure that declares `landmarkMarks` gets dot-drag +
the Marks editor; one that doesn't (a UMAP scatter, a volcano, a heatmap) gets none of that — only the
cosmetic floor. The gesture default becomes a contract value (ERG → no-op; zoom/pan are buttons).

This is purely about **which editing tools appear and how gestures behave.** The backend landmark
re-measure + provenance (`erg-manual-marks` v1) is shipped and correct — **do not touch the measurement.**

## Context — what exists today (verified this session)
- **`meta.selom`** (render-inert; Plotly ignores `meta`) already carries `figureKind`, `layoutMode`,
  `overlayHideX/Y`, `series[]`, `primitives[]` (scale-bar), and `marks[]` (the seeded landmark dots).
  `lib/figure-model.ts::readHint()` reads it; `deriveFigureModel()` resolves it into a `FigureModel`.
- **`FigureModel.capabilities`** is the *inferred* floor: `{ markers, lines, colorscale, colorbar,
  scalebar, subplotRanges }` — derived from the raw spec so a third-party figure still gets a correct
  generic editor. `scalebar` resolves from `meta.selom.primitives`.
- **Landmark marks** are read on a *separate* path (`lib/erg/marks.ts::readSeededMarks` →
  `meta.selom.marks`), not yet a capability. The numeric **Marks editor**
  (`components/project/marks-editor.tsx`) is the contract-in-miniature: gated on seeded marks, it lists
  per-cell a/b (N1/P1) times + measured µV + reset-to-auto + a "show dots" toggle, writes `manual_marks`.
- **Dot-drag** (`components/figure/mark-drag.ts`) is imperative: a capture-phase `mousedown` arms on a
  hovered dot and blocks Plotly's box-zoom *for that gesture*; everywhere else a drag still box-zooms.
- **Cosmetic inspector** (`components/figure/property-panel.tsx`) builds tabs from `BASE_TABS` (Style,
  Axes, Legend, Data) + a conditional **Marks** tab (`hasMarks` = scale-bar or annotations) + Page,
  all from `deriveFigureModel`.
- **Canvas config** (`components/figure/figure-canvas.tsx`): `displaylogo:false`, `responsive:true`,
  `edits:{…}` (legend/annotation/shape direct-manip — independent of dragmode),
  `modeBarButtonsToRemove:["lasso2d","select2d"]`. **No `dragmode`** ⇒ Plotly default = box-zoom on drag.

### Plotly mechanics confirmed (research this session)
- `layout.dragmode: false` disables **drag-based** zoom AND pan → a plot-area drag becomes a true no-op.
  (`dragmode:"pan"` does *not* disable zoom, so `false` is the correct "no-op default".)
- The `zoom2d` / `pan2d` **modebar buttons** set `dragmode` when clicked → "zoom/pan as a button-
  activated mode" works out of the box; we keep the buttons and only change the *default*.
- `config.scrollZoom:false` disables wheel-zoom independently (good for fixed-range ERG grids).
- Element `edits` (legend/annotation/shape drag) and our capture-phase dot-grab both work with
  `dragmode:false` — they don't go through the dragmode path.

## Design

### §1 — The capability contract (`meta.selom.capabilities`)
The skill stamps a render-inert per-figure contract. **Declared wins; everything is optional; absent →
the inferred floor / today's behaviour** (so non-ERG figures never regress).

```ts
// layout.meta.selom.capabilities — declared per-figure editing contract (render-inert).
interface SelomCapabilities {
  /** Plot-area gesture config. Absent → the editor keeps Plotly's default (box-zoom) — no regression. */
  gesture?: {
    /** Default dragmode. ERG → "none" (a stray drag is a no-op). */
    default?: "none" | "select" | "pan" | "zoom";
    /** Keep zoom + pan available as modebar buttons (a mode the user presses). Default true. */
    zoomTools?: boolean;
    /** Wheel-zoom. ERG → true (owner: keep it — harmless, independent of dragmode). Absent → Plotly
     *  default, which is OFF for cartesian plots, so "keep wheel-zoom" must set this true explicitly. */
    scrollZoom?: boolean;
  };
  /** Data-coupled tool gates (default false → a figure that declares nothing gets none of these). */
  tools?: {
    /** Editable ERG landmark dots (a/b, N1/P1) → dot-drag + the numeric Marks editor. */
    landmarkMarks?: boolean;
    /** A tunable model fit the editor can expose (Naka-Rushton on intensity-response). v1: schema-reserved. */
    modelFit?: "naka_rushton" | null;
    /** Editable scale-bar primitive. Already inferred from primitives[]; may be declared to be explicit. */
    scaleBar?: boolean;
  };
}
```

Example (an `erg_traces` flash grid):
```json
{ "meta": { "selom": {
  "figureKind": "trace_grid",
  "capabilities": {
    "gesture": { "default": "none", "zoomTools": true, "scrollZoom": true },
    "tools": { "landmarkMarks": true, "scaleBar": true }
  },
  "marks": [ /* … seeded a/b dots … */ ]
}}}
```

### §2 — Resolution in `deriveFigureModel` (one merge point, one read surface)
`deriveFigureModel` resolves the contract over the inferred floor; **declared wins**. The editor, canvas,
and Figure-data all read the resolved `FigureModel` — never `meta.selom` directly. New fields:

```ts
interface FigureModel {
  // … existing …
  capabilities: {
    // existing inferred floor (unchanged):
    markers: boolean; lines: boolean; colorscale: boolean; colorbar: boolean;
    scalebar: boolean; subplotRanges: boolean;
    // NEW — declared data-coupled tool gates (default false unless meta.selom declares them):
    landmarkMarks: boolean;
    modelFit: "naka_rushton" | null;
  };
  /** Resolved plot-area gesture config. `dragmode === undefined` → keep Plotly's default (no-regression). */
  gesture: {
    dragmode?: false | "select" | "pan" | "zoom";   // "none" → false
    zoomTools: boolean;     // default true
    scrollZoom?: boolean;   // undefined → leave Plotly default
  };
}
```
- `landmarkMarks` resolves from `capabilities.tools.landmarkMarks`. As a safety net during migration it may
  also be inferred true when `readSeededMarks(spec).length > 0`, but the skill **should declare it** so the
  gate is coherent even before dots are drawn. (The dot *presence* stops being the trigger; the *declaration* is.)
- `scalebar` keeps its inferred resolution from `primitives[]`; a declared `tools.scaleBar` may force it.
- `gesture.dragmode`: `"none" → false`; otherwise the declared mode; **absent → `undefined`** (the canvas
  then sets nothing → Plotly's current default → non-ERG figures unchanged).

### §3 — Gesture model (canvas)
`figure-canvas.tsx` reads `model.gesture`:
- **`layout.dragmode`** ← `model.gesture.dragmode` when defined (ERG → `false`); when `undefined`, set
  nothing (today's behaviour). Applied to the figure passed to `<Plot>` (and re-asserted on overlay
  projection, which keeps its own axes).
- **`config.scrollZoom`** ← `model.gesture.scrollZoom` when defined (ERG → `true` — owner: keep
  wheel-zoom; cartesian's default is off, so this must be set explicitly to honour "keep it").
- **Modebar**: keep `zoom2d`/`pan2d`/`zoomIn2d`/`zoomOut2d`/`autoScale2d`/`resetScale2d`. When
  `gesture.zoomTools === false`, also remove the zoom/pan buttons (not needed for ERG, but default keeps
  them — owner kept zoom-as-a-button). `lasso2d`/`select2d` stay removed.
- **Dot-grab** (`wireMarkDrag`) is now gated on **`model.capabilities.landmarkMarks`** (was: any editable
  non-overlay figure). A figure that doesn't declare landmark marks never gets the drag wiring — not even
  a no-op listener. With `dragmode:false` on ERG, the capture-phase interceptor is what *performs* the
  drag; with the contract, it's only attached where it's meaningful.
- Net ERG feel (GraphPad/Illustrator): default tool = select/no-op; **grab a dot → drag it**; press the
  **Zoom** or **Pan** modebar button to enter that mode deliberately; the mouse **wheel zooms** (kept).

### §4 — Surfaces driven by the contract
One contract → both editing surfaces compose declaratively.

**Cosmetic inspector (`property-panel.tsx`):** tab list derives from `model.capabilities`:
- Style / Axes / Legend / Data — always (the cosmetic floor).
- **Marks** (cosmetic: scale-bar + annotations) — when `capabilities.scalebar || annotations`. (Already
  inference-driven; restate in contract terms.)
- **Page** — always.
- (Landmark editing stays in the **Figure-data** window, not the cosmetic inspector — see below.)

**Figure-data window (`figure-data-panel.tsx`):** panels derive from `model.capabilities`:
- **Landmark Marks editor** — when `capabilities.landmarkMarks` (was: `seededMarks.length > 0`). The
  editor still renders from `seededMarks`; the *gate* becomes the capability so it's coherent and a future
  figure can declare it without seeded dots present.
- **Model-fit knobs** — when `capabilities.modelFit === "naka_rushton"` (**schema-reserved in v1**; the
  panel is a stub/no-op in v1, built in a follow-on — see §10).
- Data-check routing + data-fit + the generic Inputs/Re-run — unchanged.

### §5 — Figure → tools mapping (the ERG family, this pass)
What each ERG figure declares. Non-ERG figures declare nothing → inferred floor only.

| Figure | `gesture.default` | `scrollZoom` | `landmarkMarks` | `scaleBar` | `modelFit` |
|---|---|---|---|---|---|
| `erg_traces` (flash trace grid) | none | true | **yes** (a/b) | yes | — |
| `erg_flicker` — waveform view | none | true | **yes** (N1/P1) | yes | — |
| `erg_flicker` — summary view | none | true | no | no | — |
| `erg_bwave_bar` | none | true | no¹ | no | — |
| `erg_intensity_response` | none | true | no¹ | no | naka_rushton² |
| UMAP / volcano / heatmap / bar / … | *(unset)* | *(unset)* | no | no | — |

¹ The bar + intensity-response *consume* `manual_marks` (the metric re-measures at the operator's marks),
but the **editable dots live on the trace grid** (`erg_traces` / `erg_flicker` waveform). They host no dots
and no Marks editor — matches today. ² Schema-reserved; the fit-knobs panel is a v1.x follow-on.

**v1 stamp scope (shipped):** the contract is stamped on the **trace grid** (`_tracegrid.grid_spec` →
`erg_traces` + `erg_flicker` waveform) — the figures that carry editable dots, where the gesture model
matters most. `landmarkMarks` there resolves to `bool(marks_meta)` (true when the grid has landmark
marks). **The bar / intensity-response / flicker-summary gesture defaults are NOT stamped in v1** — they
have no dots and box-zoom there is harmless, so their no-op-default is folded into the §11 generalization
(applying the gesture contract across all skills), consistent with the owner's ERG-first scope. They keep
today's behaviour (box-zoom default) until then.

### §6 — Landmark dot UX (synthesis of owner options 1+2+3 — confirm)
Base = pinned role labels + role colours (option 1), with hover/drag readout (2) and a legend (3):
- **Role colours.** Each dot is coloured by its role from a fixed map (proposed: `a → blue`,
  `b → amber`, `n1 → teal`, `p1 → violet`). Carried on the existing `markers` overlay `color`.
- **Pinned role labels.** Each dot draws a small text label (`a` / `b` / `N1` / `P1`) adjacent (Plotly
  `mode:"markers+text"`, `text`, `textposition` chosen per role so the label clears the trace — e.g.
  troughs `bottom`, peaks `top`). **Default ON.**
- **Show/hide-labels toggle** (MarksEditor) — a render-time restyle between `"markers"` and
  `"markers+text"` (no re-run). Lets a clean export drop to dots-only + legend.
- **Role legend.** A compact FE legend strip co-located with the Marks editor / above the canvas:
  `● a-wave  ● b-wave` (or `● N1  ● P1`) using the role colours — readable without reading each label.
- **Hover / drag readout.** The dot carries a `hovertemplate` (`role · t ms · µV`); the existing drag
  crosshair label gains the role (`b · 58 ms · 113 µV`).

Backend (dot emission only — `_tracegrid` / `_erg` mark builders): add `color` (role map), `text` +
`mode:"markers+text"` + `textposition`, and `hovertemplate` to the seeded dots. FE owns the toggle, the
legend, and the crosshair-label role. **No change to the measurement or `manual_marks` round-trip.**

## Requirements
- **R1 — contract schema.** Add `meta.selom.capabilities` (§1). Optional, render-inert, backward-compatible
  (absent → today's behaviour). A tolerant reader (bad/partial → ignored, never throws).
- **R2 — resolution.** `deriveFigureModel` resolves the contract over the inferred floor into
  `model.capabilities.{landmarkMarks,modelFit}` + `model.gesture` (§2). Declared wins; one read surface.
- **R3 — gesture model.** Canvas applies `dragmode`/`scrollZoom`/modebar from `model.gesture` (§3). ERG →
  no-op default + zoom/pan buttons + no wheel-zoom. Unset → unchanged. Cosmetic `edits` still work.
- **R4 — capability-gated dot-drag.** `wireMarkDrag` is wired **iff** `capabilities.landmarkMarks`
  (§3) — never on a non-declaring figure.
- **R5 — descriptor-driven panels.** The Figure-data Marks editor gates on `capabilities.landmarkMarks`;
  the cosmetic inspector's Marks tab gates on the contract terms; both compose from `model` (§4).
- **R6 — figure→tools mapping.** Each ERG skill stamps its row from §5. Non-ERG skills stamp nothing.
- **R7 — dot UX.** Role colours + pinned labels (toggleable) + role legend + hover/drag readout (§6).
- **R8 — no regression.** A figure that declares no `capabilities` is byte-identical in behaviour to
  today (box-zoom default, no landmark tools); ERG goldens are byte-identical unless dots are drawn
  (`marks=true`), and the dot-styling additions are gated behind that existing flag.

## Decisions
- **D1 — contract in `meta.selom`, not `skill.json`** (owner a). Per-figure + data-aware; reuses the
  existing render-inert hint channel and the single `deriveFigureModel` merge point. Reversible.
- **D2 — `dragmode:false` for the no-op default, not `select`** (owner b). `select` draws a meaningless
  marquee on an ERG trace and we already remove `select2d`/`lasso2d`. `select` stays in the schema for a
  future scatter that supports point-selection. Reversible.
- **D3 — capability *flags*, resolved into `FigureModel`** (owner c). The editor never branches on skill
  id or figureKind; it reads resolved booleans. Adding a skill's editor = declaring a flag. Reversible.
- **D4 — ERG-first; non-ERG unchanged via `undefined` gesture default** (owner d). The schema is general;
  only the ERG family declares it now. Flipping the *global* default to no-op is part of the §11 roadmap
  item, not this pass. Reversible.
- **D5 — dot styling rides the existing `markers` overlay + `marks=true` flag** (owner e + `erg-manual-marks`
  D3). No new primitive type; default path byte-identical. Reversible.
- **D6 — `landmarkMarks` should be *declared*, with seeded-marks presence as a migration fallback.** Makes
  the gate coherent (a figure can declare it before dots are drawn) without breaking the current figures.

## Invariants
- A figure with no `meta.selom.capabilities` behaves exactly as today (box-zoom default; no landmark
  dot-drag; no Marks editor unless seeded marks are present during migration).
- `dragmode:false` never disables the cosmetic `edits` (legend/annotation/shape drag) or the dot-grab.
- The contract is render-inert: stamping `capabilities` never changes a single rendered pixel of the
  figure (it changes only editor affordances). ERG goldens unchanged unless `marks=true`.
- One read surface: editor/canvas/Figure-data read `FigureModel`, never `meta.selom` directly.

## Error behavior
- Malformed/partial `meta.selom.capabilities` → ignored field-by-field (fall back to inferred/default),
  never a throw or a broken canvas.
- A version mismatch where `dragmode` isn't honoured degrades to "the default is still box-zoom" — the
  dot-grab interceptor remains the guard, as today.
- `landmarkMarks` declared but no seeded marks present → the Marks editor renders its empty/auto state;
  the dot-drag simply finds nothing to arm (no error).

## Testing strategy
- **FE unit (vitest):** `deriveFigureModel` resolves `capabilities.landmarkMarks`/`modelFit` + `gesture`
  from a stamped `meta.selom.capabilities`; declared-wins over inferred; absent → floor/undefined.
- **FE unit:** the gesture config the canvas computes (dragmode/scrollZoom/modebar) for an ERG contract
  vs an unstamped figure (pure helper, no Plotly).
- **FE unit:** mark-drag wiring is **not** attached when `landmarkMarks` is false (gate test).
- **FE unit:** the role colour/label/legend helpers (role→colour, role→label, textposition).
- **BE:** the ERG skills stamp the correct `capabilities` row (§5); default path byte-identical
  (`marks` unset → goldens unchanged); with `marks=true` the dots carry colour/text/hovertemplate.
- **Live (real Diagnosys 453_AAV.TXT):** ERG trace grid → drag = no box-zoom; grab a dot → drags; press
  Zoom button → zoom mode; **wheel zooms** (kept); a/b labels visible + colour-coded + legend; toggle labels off → dots-only;
  a UMAP/volcano figure → no dot-drag, box-zoom still default (no regression). Full-app smoke test
  (`[[full-app-smoke-test-before-handoff]]`): keep WebGL behind `dynamic(ssr:false)`.

## Build plan (after owner confirms this spec)
1. **Schema + resolution (FE):** `meta.selom.capabilities` types + `deriveFigureModel` resolution
   (`model.capabilities.{landmarkMarks,modelFit}`, `model.gesture`) + unit tests. *(no behaviour change yet)*
2. **Gesture model (FE):** canvas reads `model.gesture` → `dragmode`/`scrollZoom`/modebar; gate
   `wireMarkDrag` on `landmarkMarks`; crosshair label gains role. *(non-ERG unchanged)*
3. **Descriptor-driven panels (FE):** Figure-data Marks editor + inspector Marks tab gate on `model`.
4. **Dot UX (BE + FE):** role colour/label/hovertemplate on the seeded dots; FE label toggle + legend.
5. **Backend stamps (BE):** each ERG skill stamps its §5 `capabilities` row; default path byte-identical.
6. **Verify:** FE gates (tsc/eslint/vitest) + BE focused subset + ruff; live on real Diagnosys + a
   non-ERG figure; full-app smoke test.

## §11 — Future / generalization (next-session roadmap item — owner-flagged)
Scope (d) was **ERG-first now, general eventually.** Generalizing the capability contract across **all**
skills — defining `capabilities` for scatter (UMAP), volcano, heatmap, bar, box/violin, sankey, etc.,
and deciding whether the **global** gesture default flips to no-op everywhere (zoom-as-button universally)
— is its own **roadmap / phase / pillar planning item for next session**, not this build. Capture it at
handoff (CURRENT.md + memory) so it isn't lost. The schema here is built to absorb it with no rework: a
skill opts in by stamping `meta.selom.capabilities`; the resolver and both surfaces already compose from it.

## Out of scope
- The backend landmark re-measure + provenance (`erg-manual-marks` v1) — shipped + correct; untouched.
- The Naka-Rushton fit-knobs **UI** (schema-reserved `modelFit`; built in a follow-on).
- Flipping the global gesture default for non-ERG figures (→ §11 roadmap item).
- Any new measurement, `manual_marks` change, or skill math.

## References (exact integration points)
- `app/frontend/lib/figure-model.ts` — `deriveFigureModel`, `readHint`/`SelomHint`, `FigureModel`,
  `capabilities`, `scalebar` (the resolver to extend; §2).
- `app/frontend/components/figure/figure-canvas.tsx` — `config`, `bindGestures` (the gesture model + the
  `wireMarkDrag` gate; §3).
- `app/frontend/components/figure/mark-drag.ts` — `wireMarkDrag`, `readSeededMarks` (drag; crosshair role).
- `app/frontend/components/figure/property-panel.tsx` — `BASE_TABS`, `hasMarks` (inspector tab gating; §4).
- `app/frontend/components/figure/panels/marks-panel.tsx` — cosmetic Marks (scale-bar + annotations).
- `app/frontend/components/project/figure-data-panel.tsx` — gates `MarksEditor` (descriptor-driven panel; §4).
- `app/frontend/components/project/marks-editor.tsx` — numeric Marks editor (label toggle + legend; §6).
- `app/frontend/lib/erg/marks.ts` — `readSeededMarks`, `SeededMark` (dot data; role colour/label/legend helpers).
- Backend: `skills/_tracegrid.py` (markers overlay + `meta.selom` emit), `skills/_erg.py` (mark builders),
  `skills/proprietary/erg_{traces,flicker,bwave_bar,intensity_response}/` (stamp the §5 rows).
- `docs/erg-manual-marks/spec.md` (shipped v1) · `docs/figure-editor-contract/spec.md` (`meta.selom`).
- memory [[selom-erg-manual-marks]] [[selom-figure-editor-architecture]] [[selom-erg-module]]
  [[full-app-smoke-test-before-handoff]] [[verify-on-real-data-not-mock]].
