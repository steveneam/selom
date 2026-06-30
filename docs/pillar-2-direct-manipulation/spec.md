# Pillar 2 — Direct-Manipulation Figure Editor (Prism phase 2) — design spec

_2026-06-30 22:05 +10:00 (Australia/Sydney). **Pillar-level — design-first.** The OUTPUT stage becomes a
canvas figure editor: "GraphPad Prism + Photoshop + PowerPoint + Inkscape in features/customisability, but
intuitive like Inkscape" (owner). Sits on the FE Experience Spine (`docs/fe-experience-spine/README.md`)
as Layer E. Foundation: `docs/figure-editor-contract/spec.md` (the adaptive editor, P1–P4). Process: this
is a **pillar** — it earns the full Prism discipline (research **done** → interview → design → spec → plan
per phase). Build is NOT started; §9 lists the owner decisions that gate it._

## 1. Goal

Turn the OUTPUT stage from a tabbed property inspector into a **direct-manipulation canvas**: the figure
is the hero on an artboard with a ruler on top and side, tool/function rails on the edges, gridlines you
can add, a proper color board, and an **editable Prism-style table** whose edits flow to the figure live —
while the figure stays a plain, reproducible, exportable Plotly spec.

**North-star (owner interview, `interview.md`, 2026-06-30): own the last mile.** The owner finishes figures
today by **exporting to Illustrator/Inkscape** — chiefly to add annotations (text · arrows · lines ·
shapes) and to align elements precisely. Pillar-2's success criterion is concrete: **make that export
unnecessary.** That promotes two things from "nice-to-have" to **core**: the **annotation/drawing layer**
(the direct cause of the export) and the **alignment chrome** (rulers/guides/snap). Multi-panel assembly is
*nice-to-have, later* (interview Q2) → the compositing artboard stays a deferred epic (§8).

**Non-goals:** a vector-illustration engine (no node/Bézier/path-boolean editing — that's the Inkscape
trap); a bespoke editor per skill (stay *kind-aware* via `FigureModel`, not skill-coded); the multi-panel
compositing artboard as an MVP requirement (§8, deferred epic).

## 2. The headline finding (why this is an extension, not a rewrite)

The canvas research (2026-06-30) confirmed Selom **already owns the hard parts**: the `FigureSpec` as the
canonical model, the JSON-Patch store with undo/redo (`use-figure-store.ts`), Plotly's *granular*
`edits:{…}` on-chart editing, and a **pixel-mapped DOM-overlay drag layer** (`mark-drag.ts`,
`threshold-drag.ts`, `colorbar-drag.ts`, `dendrogram-drag.ts`) that positions overlay elements via Plotly's
`d2p`/`l2p` axis converters and commits one patch per gesture. **Rulers and guides are that same technique
with no data binding.** So the vision is reachable as an *incremental* build on the shared backbone (FE
Experience Spine §"technical backbone"), holding all seven invariants.

## 3. Architecture — overlay-on-Plotly (decided)

Three options were evaluated (canvas research §4):

- **(A) Plotly-native** — `config.edits:{…}` (titles/legend/annotations/colorbar/shapes — *already wired*,
  and deliberately **not** blanket `editable:true` so users can't drag data points) + native gridlines
  (`xaxis/yaxis.showgrid/gridcolor/gridwidth/griddash` + `minor`). Trivial; no chrome.
- **(B) DOM/SVG overlay** *(chosen core)* — an absolutely-positioned layer over the Plotly div for rulers,
  guides, snap, selection handles, free annotations; px↔data via `gd._fullLayout` `d2p`/`l2p`, re-synced
  on `plotly_relayout`/resize. **Selom already runs this pattern** — the canvas chrome extends it.
- **(C) Compositing artboard** — the Plotly figure as one object among text/shapes/multiple panels
  (BioRender/Illustrator-style). The publication endgame (Fig 1 = panels A–D), but a large new subsystem
  (selection model, z-order, transform, export compositing, Plotly-in-a-transformed-scene). **Deferred to
  its own epic (§8).**

**Decision: B as the canvas spine, on top of A's native gridlines + granular edits, with C deferred.** No
rebuild; every slice bolts onto `FigureSpec` + the store + the overlay layer; render stays `f(spec)`;
undo/redo and WYSIWYG export already work.

## 4. The editable table — hybrid by column (owner-decided 2026-06-30)

The Prism payoff: edit a cell → the figure updates. This **reverses a locked non-goal**
(`figure-editor-contract` §2: client-side value edits stay a backend re-run) — deliberately, with a guard.

- **The plotted values already live in the spec** (`data[i].x/y/z`), and render is `f(spec)`, so a table
  bound to those paths writing one JSON-Patch (`set('/data/0/y/3', 4.2)`) re-renders **instantly,
  client-side, undoably** — identical mechanism to the existing colour/threshold edits.
- **Data model:** a `derivePlotTable(spec)` view-model paralleling `deriveFigureModel` — editable columns
  mapped to JSON-pointers, the column set typed by the trace kind (`inferTraceKind`), Prism-style. A cell
  edit emits one `commit` op.
- **The hybrid-by-column rule (invariant 4 applied):**
  - **Plotted-value columns → LIVE.** Patch the spec, re-render now, **mark the cell as a manual override**
    (auditable via the provenance discipline — a hand-edited point is a *claim about the data*, never
    silent analysis output). Covers ~90% (tidy the values you're plotting).
  - **Input/data columns → STAGED re-run.** Anything that changes *what was computed* (re-cluster,
    re-threshold, re-normalize) routes to the staged "Figure data" re-run through the chokepoint — it must
    **not** desynchronize the figure from its provenance/methods.
  - The table must make the two column classes **visually distinct** (which columns are live-editable vs
    re-run) — the single largest UX-clarity risk (§7).
- **Typed-table discipline (the Prism lesson):** the table's columns are *determined by the figure kind*,
  not a freeform grid — that's what makes Prism intuitive to non-bioinformaticians. `derivePlotTable`
  carries that typing.

## 5. Slices (each independently shippable, rides existing undo/export, verified on real data + live BE)

_Technical sequencing is cheap/foundational-first; the **★ last-mile-core** tags mark the export-killers
(the interview north-star) — the slices that, together, make the Illustrator/Inkscape round-trip
unnecessary. Prioritise landing the ★ set._

1. **Gridline controls** — a Style-panel group writing native Plotly layout patches
   (`showgrid/gridcolor/gridwidth/griddash` + `minor` major/minor + `dtick` spacing). Zero new infra;
   validates "Style panel writes layout patches". **Ship first.**
2. **reactbits color board** (Lane-P P5) — replace the native `<input type=color>` (`panels/data-panel.tsx`)
   with a popover `{S/V square + hue slider + preset swatches + hex}`, wired to `seriesColorOps` →
   `store.commit`; presets = the colour-blind-safe `COLORWAYS.okabeito`; a bottom palette strip
   (Inkscape ergonomics). Build via `react-colorful` (2.8 KB, MIT) + a swatch row, or hand-rolled HSV.
3. **★ Rulers** (top + left) — overlay reading `gd._fullLayout` axis `d2p`/`_offset`, re-syncing on
   `plotly_relayout`/resize. Same technique as `mark-drag.ts`. *(Alignment = an export cause.)*
4. **★ Guides + snap-to-guide** — draggable H/V guides from the rulers; snap objects to guides + gridlines.
   Extends the ruler overlay; reuses the imperative drag plumbing. (Angled/axonometric guides = overkill.)
5. **★ Annotation & drawing layer** (interview Q4 — promoted to core; the direct export cause) — free
   **text boxes · arrows · callouts · lines · basic shapes** (rectangle, ellipse) placed on the figure.
   Technical path: Plotly's **native draw tools** (`config.modeBarButtonsToAdd:
   ['drawline','drawrect','drawcircle','drawopenpath','eraseshape']`) writing `layout.shapes`, + free text
   as `paper`/`pixel`-referenced `layout.annotations`, + the overlay for selection/move handles. Stays
   reproducible (shapes/annotations live in the spec; WYSIWYG export) and stays undoable (one `commit` per
   add/move). **Hard line: basic primitives only — NO node/Bézier/path-boolean editing** (the Inkscape
   trap, §7.5).
6. **Editable table** (§4) — `derivePlotTable` + hybrid-by-column + manual-override marker. Includes the
   **white-table restyle** (Lane-P P1) as its visual precursor. Build the capabilities in the owner's
   priority order (interview Q3): **(1) fix/tweak a plotted value** [live, marked override] → **(2)
   relabel/rename** → **(3) change which rows are highlighted** [extends the existing volcano gene-label
   toggle] → **(4) hide/show or reorder series**. The Prism payoff.
7. **Methods/legend stage split** (§6) — the IA change that frees the figure view to be the canvas.
8. **Styling-AI** (the OUTPUT-stage `<AskAi mode="live">`) — one-click presets ("Colorblind-safe",
   "Publication-ready") + chat refine, applying cosmetic `restyle_figure`/`relabel` JSON-Patch **live**;
   recorded as a `provenance.actions[]` entry, tier `cosmetic`. *Conducted via Layer A's `<AskAi>`
   composer, but the surface/presets live in the editor* — this is the figure-styling AI folded out of the
   cross-stage spec per the owner directive.
9. **Journal-styles phase-2 hookup** — the style **Store** / import-your-own / capture-as-a-style on top
   of the shipped style registry ([[selom-journal-styles-feature]]); the "examples from other journals"
   the owner wants AI to draw on for styling.

**Toolbar layout** (across the slices): tools-left / commands + contextual controls-top / palette-bottom
(Inkscape ergonomics) + the artboard as hero (figure-forward, already an owner-decided IA in
figure-editor-contract §3.7).

## 6. Methods/legend stage split (the IA change)

Today the methods + legend are a read-only section inside the `PublishConfidence` card in the figure view
(FE reality-map). Split them into a dedicated **"Methods & Legend" stage between Figure and Publish** —
two reasons beyond freeing the canvas: the engine spine already names OUTPUT as "editable figure + table +
**methods**" (three things), and there's a shipped `methods.build_body` + `legends.py` backend to populate
it. The **AI draft + polish** that fills this stage is **Layer A's** methods-draft composer
(`docs/ai-cross-stage-entry-points/spec.md`), which attaches to the current card now and migrates here when
this slice lands. This slice owns the *stage/IA*; L-AI owns the *content generation*.

## 7. Risks (from the canvas research)

1. **Overlay ↔ Plotly coordinate drift** on zoom/pan/resize. Mitigation: drive rulers/guides from
   `gd._fullLayout` `d2p`/`l2p`; re-sync on `plotly_relayout` (the drag wirings already do this).
2. **Live table breaks provenance/reproducibility.** A client value-overwrite masquerading as analysis
   output corrupts the methods/score story. Mitigation: the hybrid-by-column split + the manual-override
   marker (§4); recompute stays staged. Mirrors [[selom-provenance-stamping-chokepoint]].
3. **Plotly editor ecosystem dormant** (react-plotly.js ~Jan 2025; react-chart-editor inactive).
   Mitigation: don't depend on react-chart-editor — Selom's `FigureModel`/store supersede it. Pin Plotly.
4. **Two "grid" concepts** — Plotly *data* gridlines vs an Inkscape *page* grid. Mitigation: label
   distinctly ("Axis gridlines" vs "Canvas grid"); ship axis gridlines (slice 1) first, page grid later.
5. **Scope creep into the vector engine.** Hard line: edit chart elements + free annotations + (later)
   composited objects — **never** paths/nodes/booleans.
6. **Compositing-artboard underestimation** (§8). Mitigation: keep it a separate, later epic.

## 8. Deferred epic — the compositing artboard (Option C)

Multi-panel figure assembly (Fig 1 = panels A–D + labels), selection + transform handles on free objects,
align & distribute, z-order, export compositing. The real publication endgame, but a large subsystem with
a live Plotly canvas inside a transformed scene. **Its own spec, after the slices land.** Do not let MVP
language imply it.

## 9. Owner decisions that gate the build

1. **Run the full Prism discipline?** Research is **done** (canvas research, 2026-06-30). Do an **owner
   interview** (how *you* edit a figure today; which Prism/Inkscape features you actually reach for) before
   the design pass — *recommended*, matches pillar-1.
2. **First slice = gridline controls** (cheapest, validates the loop), then color board? *Recommend yes.*
3. **Editable-table column language** — how to visually distinguish live-editable vs re-run columns
   (colour? icon? section split?). A `fe-review` + `impeccable` design call before slice 5.
4. **Toolbar IA** — adopt tools-left / commands-top / palette-bottom now, or evolve the current tabbed
   inspector incrementally? (Affects how disruptive slices 1–4 feel.)
5. **Sequencing vs Layer A** — pillar-2 design in parallel with the L-AI build (owner picked "cross-stage
   AI first"), or strictly after? *Recommend: design in parallel (it's writing), build after L-AI's first
   phases.*

## 10. Invariants (inherited from the FE Experience Spine — all seven hold)

Render = f(spec) · AI compiles away · one provenance chokepoint · apply-discipline by consequence
(hybrid-by-column is this) · deterministic path primary · one pending queue · inference-first editor
contract. Plus: `meta.selom` hints stay render-inert; no regression for existing scatter/marker figures;
WYSIWYG export unchanged.
