# Spec — Dendrogram line editing: leaf-tip length lever + per-line drag/highlight

> **Status: DESIGN COMPLETE — owner-requested 2026-06-25 (session T20). BUILD next session.** Author
> Claude (Opus 4.8), owner Steven. A follow-on to the shipped heatmap v2 dendrograms
> (`heatmap-clustermap-spec.md`). Owner directive: "spec, design and plan now, build next session."
>
> **Owner intent (verbatim distilled — 4 messages + 3 zoom screenshots):** the dendrogram **leaf
> end-tips are too short** (the short stub between a merge bar and the heatmap); make them **longer**,
> via BOTH a **uniform lever** AND **selecting an individual line and dragging it longer/shorter, with
> the hovered line highlighting**. The T20 gutter-spread "Dendrogram size" sliders are NOT this (they
> scale the whole tree and steal height from the heatmap — at 45% they squashed the map = the "why is
> it compressed" screenshot). Keep those; this is a separate, finer control.

## What we have today (after T20)
- The dendrogram is **one scatter trace** per tree (`skills/heatmap/run.py::_dendro_trace`): a
  None-separated polyline of every link (each link a ⊓ of 4 points). **Column (top) tree:** x = leaf
  positions (`xaxis3`, range `[0, 10·n_cols]`), y = distances (`yaxis3`, range `[0, max_d·1.05]`,
  **leaves at y = 0** abutting the heatmap). **Row (left) tree:** x = distances (`xaxis2`, range
  `[max_d·1.05, 0]` — reversed, so **leaves at x = 0** abut the heatmap on the right), y = leaf
  positions (`yaxis2`, range `[0, 10·n_rows]`).
- A "Dendrogram" Style section (`lib/heatmap/dendrogram.ts`) with **Row tree width** / **Column tree
  height** sliders that re-proportion the gutter-vs-heatmap axis **domains** (instant, layout edit).
  Orthogonal to tip length — keep them; the new "Leaf tip length" lever joins this same section.

## The crux — why "drag a tip" is NOT a trivial change (the design driver)
The leaf tip is part of the **dendrogram trace's coordinate arrays**. Editing `data[i].x/y` is, by
`lib/patch.ts`: (1) **classified as a SERVER re-run** (`DATA_VALUE_PATH` matches `/data/<i>/(x|y|…)`),
and (2) **insert-not-replace** under JSON-Patch (`set` = `add` shifts an array index). So we can NOT
lengthen a tip by editing the trace coords as an instant cosmetic edit — the same wall the heatmap
rename hit (it had to use axis `ticktext`; see `memory selom-figure-edit-ux-pattern`). **Tip length must
be driven from a layout/meta path (client/instant) and applied to the trace at RENDER time.**

## Mechanism — meta-pref + render-time PROJECTION (reuse `projectOverlay`)
Mirror `lib/figure-model.ts::projectOverlay` (which already projects an ERG grid → overlay from a
`meta.selom` pref the canvas applies before Plotly renders — pure + reversible, the canonical spec is
untouched):

1. **The pref (the only thing the figure store holds):** `meta.selom.dendrogramTips` — a `layout/meta`
   path, so the patch classifier treats edits as **client/instant** and they ride undo. Schema:
   ```
   meta.selom.dendrogramTips = {
     col?: { gap: number, tips?: { [leafKey: string]: number } },  // distance-axis units
     row?: { gap: number, tips?: { [leafKey: string]: number } },
   }
   ```
   `gap` = the uniform lever (added to EVERY leaf stub on that tree); `tips[leafKey]` = a per-leaf
   override from a drag (added on top of `gap`). `leafKey` = the leaf's position coordinate rounded to a
   stable string (col → its x; row → its y) — robust to re-render, no index bookkeeping.

2. **The projection (pure, applied by the canvas before Plotly):** `applyDendrogramTips(spec)` →
   a NEW render spec:
   - Find each dendrogram trace (a `scatter`/`lines` trace on `x2`/`y2` or `x3`/`y3`; or tagged via the
     OPTIONAL backend hint below). Determine its axis = col (x3/y3) or row (x2/y2).
   - **Identify leaf-base points heuristically** (no backend change needed): for col, every polyline
     point with `y ≈ 0`; for row, every point with `x ≈ 0`. Only leaf stubs touch distance 0, so this is
     unambiguous. The point's other coordinate (x for col, y for row) is the `leafKey`.
   - **Move each leaf-base point outward by `e = gap + (tips[leafKey] ?? 0)`:** col → `y: 0 → -e`; row →
     `x: 0 → -e` (away from the heatmap). The merge bars + internal segments are untouched → the tree
     SHAPE is preserved; only the stubs grow.
   - **Widen the gutter axis range** so the extended stubs stay inside the gutter (no heatmap overlap):
     col → `yaxis3.range = [-E, top]` where `E = max e`; row → `xaxis2.range = [top, -E]` (reversed).
     `top` = the trace's current max distance (unchanged). For small `gap`, the rest of the tree
     compresses negligibly.
   - `gap == 0` and no `tips` → identity (today's render). Tolerates row-only / col-only / both / none.

3. **Wire** `applyDendrogramTips` where the canvas builds its render spec — the SAME seam as
   `projectOverlay` (compose them). The figure store + export keep the canonical trace; the tips are a
   display-time view (and a render-inert pref, so an exported PNG/SVG bakes the projected geometry).

Alternatives rejected: a staged backend `dendro_tip` param (re-run per drag — not the live feel);
classifier exemption for this trace (fragile); re-drawing the tree as `layout.shapes` (a bigger rewrite
than the projection needs). The projection reuses a proven pattern and needs **no backend change for v1**.

## Feature 1 — Leaf-tip length LEVER (instant)
A **"Leaf tip length"** `SliderField` in the Style "Dendrogram" section (below the tree-size sliders),
shown per present tree (Row / Column). Drives the uniform `gap`.
- `tipLengthOps(spec, axis, gap): Operation[]` → one `set("/layout/meta/selom/dendrogramTips/<axis>/gap", gap)`
  (client/instant/undoable). Slider range e.g. 0–(0.5·max_d) in distance units, shown as a 0–100% of a
  sensible cap so the owner thinks in "stub length", not raw distances.
- Pure + node-unit-tested in `lib/heatmap/dendrogram.ts`.

## Feature 2 — Per-line DRAG + HOVER HIGHLIGHT (instant)
The ERG-dot-drag capability pattern (`components/figure/mark-drag.ts`) applied to dendrogram leaf tips,
in a new `components/figure/dendrogram-drag.ts`:
- **Hover highlight:** on pointer-move, project the leaf-tip segments to pixel space via
  `gd._fullLayout`'s axis→pixel, find the nearest stub within ~8px, and draw an **HTML/SVG overlay** on
  that stub (thicken + accent colour) — the mark-drag overlay approach (NOT restyling the trace, which
  can't highlight one segment of a multi-segment polyline). Cursor → `ns-resize` (col) / `ew-resize` (row).
- **Drag:** pointer-down near a stub captures that leaf; pointer-move sets its tip length from the
  cursor's distance-axis position (clamped ≥ 0), writing `meta.selom.dendrogramTips.<axis>.tips[leafKey]`
  via `store.set` (rAF-throttled, live); `store.flush` on release (ONE undo entry). No re-run.
- **`setLeafTipOps(spec, axis, leafKey, extra)`** (pure) builds the per-leaf `set` op; the drag handler
  calls it. Reset (drag to ≤ 0, or a double-click) removes the override (`remove` op).
- **Topology-SAFE** because a leaf tip extends into the reserved gap and never moves a merge bar.
- **Out of scope (v1):** dragging an INTERNAL branch (moving a merge bar cascades to connected branches
  — needs the linkage adjacency stamped in meta). Defer until asked. v1 = leaf tips = exactly the stub
  the owner pointed at.

## Composition with the existing controls
"Dendrogram" Style section after build = **Row tree width · Column tree height · Leaf tip length** (per
present tree) + canvas drag. Domains (tree-size sliders) set overall room; the projection (lever + drag)
sets stub length by moving leaf-base coords + widening the gutter range. They compose cleanly (different
layout channels). Gate everything on a present tree (`xaxis2`/`yaxis3`) as today — no new declared
capability required (optionally add `heatmapDendrogram` for self-documentation).

## Optional backend support (only if the heuristic proves fragile)
`_dendro_trace` may stamp a render-inert `meta.selom.dendrogram = { axis, leafBasePoints: [{ptIndex,
leafKey}], top }` so the FE doesn't re-derive leaf bases from `y ≈ 0`. v1 does NOT need this (the
baseline-coordinate heuristic is exact — only leaves sit at distance 0). If added: golden regen
(render-inert), and the projection prefers the tag when present.

## Test plan
- **Unit (`lib/heatmap/dendrogram.test.ts`):** `applyDendrogramTips` — leaf bases moved by `gap`(+`tips`),
  gutter range widened, merge bars unchanged, `gap=0`+no-tips = identity, row vs col vs both vs none;
  `tipLengthOps`/`setLeafTipOps` write the right meta paths; leafKey rounding stable.
- **`file://` pre-check** (local `plotly.min.js`): render real-iRPE col+row+both with `gap` set and a
  couple per-leaf extensions → confirm stubs lengthen, tree shape preserved, no heatmap overlap.
- **Live (real iRPE, full app):** lever lengthens every stub; hover highlights the right stub; drag one
  leaf tip longer/shorter; undo; Network tab shows **no `/run` POST** (proves instant). Per
  `memory verify-on-real-data-not-mock` + `full-app-smoke-test-before-handoff`.

## Build order (next session)
1. **FE pure** — `applyDendrogramTips(spec)` + `tipLengthOps` + `setLeafTipOps` in
   `lib/heatmap/dendrogram.ts` (+ leaf-base detection helper) + unit tests. No backend change.
2. **Wire the projection** into the canvas render path (sibling of `projectOverlay`); `file://` + live
   verify the geometry.
3. **Lever** — "Leaf tip length" slider in the Dendrogram Style section. Live verify.
4. **Drag + hover-highlight** — `components/figure/dendrogram-drag.ts` (mirror `mark-drag.ts`), gated on
   a present tree, wired on the canvas. Live verify drag on real iRPE.
5. (Optional) backend leaf tags if hit-testing needs them.
6. Gates (FE tsc/eslint/vitest · BE only if step 5) + commit + `CURRENT.md` + `memory
   selom-figure-edit-ux-pattern` (add "render-time projection from a meta-pref = the instant mechanism
   when an instant edit would otherwise hit a data trace").

## References
- `heatmap-clustermap-spec.md` (heatmap v2, T20) · `generalization-spec.md` (the capability plug-in recipe).
- `app/backend/skills/heatmap/run.py::_dendro_trace` (the polyline; optional leaf tagging).
- `app/frontend/lib/heatmap/dendrogram.ts` (gutter-size sliders → add lever + projection) ·
  `lib/figure-model.ts::projectOverlay` (the meta-pref render-time projection to mirror) ·
  `components/figure/mark-drag.ts` (the ERG dot-drag + HTML overlay to mirror for the tip drag) ·
  `lib/patch.ts` (the `DATA_VALUE_PATH` server-op constraint that forces the meta-pref mechanism).
- `memory selom-figure-edit-ux-pattern` (INSTANT must be a LAYOUT edit, never `/data/*`) ·
  `selom-erg-manual-marks` (the dot-drag plug-in) · `selom-figure-editor-architecture`.
