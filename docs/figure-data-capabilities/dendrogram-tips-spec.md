# Spec — Dendrogram line editing: leaf-tip length lever + per-line drag/highlight

> **Status: DRAFT — owner-requested 2026-06-25 (session T20), build NEXT.** Author Claude (Opus 4.8),
> owner Steven. A follow-on to the shipped heatmap v2 dendrograms (`heatmap-clustermap-spec.md`).
>
> **Owner intent (verbatim distilled, 3 messages + 3 zoom screenshots):** the dendrogram **leaf end-tips
> are too short** (the short vertical stub between a merge bar and the heatmap); the owner wants to
> **make them longer** — both a **uniform lever** AND the ability to **select an individual line and
> drag/pull it longer/shorter, with the hovered line highlighting**. The gutter-spread "Dendrogram size"
> sliders shipped in T20 are NOT this (they scale the whole tree together and steal height from the
> heatmap — at 45% they squashed the map, which is the "why is it compressed" screenshot).

## What we have today (T20)
- The dendrogram is **one scatter trace** (`skills/heatmap/run.py::_dendro_trace`): a None-separated
  polyline of every link. Column (top) tree: leaf positions on x (`xaxis3`), distances on y (`yaxis3`,
  range `[0, max_d]`, leaves at y=0 abutting the heatmap). Row (left) tree: the mirror on `x2`/`y2`.
- A "Dendrogram" Style section (`lib/heatmap/dendrogram.ts`) with **Row tree width** / **Column tree
  height** sliders that re-proportion the gutter-vs-heatmap axis **domains** (instant, layout edit).
  Keep these (overall tree room is a legit control) but they're orthogonal to tip length.

## The crux — why "drag a tip" is NOT a 5-minute change
The leaf tip is part of the **dendrogram trace's coordinate arrays**. Editing `data[i].x/y` is:
1. **classified as a SERVER re-run** by `lib/patch.ts` (`DATA_VALUE_PATH` matches `/data/<i>/(x|y|…)`), and
2. **insert-not-replace** under JSON-Patch (`set` = `add`, which on an array index shifts).
So we can NOT lengthen a tip by editing the trace coords as an instant cosmetic edit (same lesson as the
heatmap rename, which had to use axis `ticktext`; see `memory selom-figure-edit-ux-pattern`). The tip
length must be driven from a **layout/meta path** (client-side/instant) and applied at render time.

## Mechanism decision — meta-pref + render-time projection (reuse the existing pattern)
Mirror `lib/figure-model.ts::projectOverlay` (which already projects an ERG grid → overlay from a
`meta.selom` pref the canvas applies before Plotly renders):
- Tip edits write **`meta.selom.dendrogramTips`** — a `layout/meta` path, so the patch classifier treats
  it as a **client/instant** edit that rides undo (NOT a trace-coord edit). Shape:
  `{ axis: "col"|"row", gap: <data units>, tips: { <leafIndex>: <extraLen> } }` (a uniform `gap` for the
  lever + optional per-leaf overrides for the drag).
- The canvas applies a **pure projection** before render: for each leaf segment of the dendrogram trace
  (a segment with an endpoint at the leaves' baseline `y==0` for col / `x==max` for row), extend that
  endpoint **away from the heatmap** by `gap + tips[leaf]`, and widen the gutter axis range
  (`yaxis3.range[0] = -(gap+maxTip)` etc.) so the extended stubs stay inside the gutter (no heatmap
  overlap). The canonical trace + spec are untouched; the projection is display-time + reversible.
- Alternatives rejected: (a) a staged backend `dendro_tip` param — re-run per drag, not the live feel
  the owner wants; (b) special-casing the classifier to allow this one trace's coord edits — fragile;
  (c) re-drawing the whole tree as `layout.shapes` — a bigger rewrite than the projection needs.

## Features
### 1. Leaf-tip length LEVER (instant)
A "Leaf tip length" slider in the Style "Dendrogram" section (beside the tree-size sliders). Sets the
uniform `gap`; the projection extends every leaf stub by `gap`. Pure: `tipLengthOps(spec, axis, gap)` in
`lib/heatmap/dendrogram.ts` writes `meta.selom.dendrogramTips.gap` (one layout edit, undoable). Shown per
present tree (col / row). Default 0 = today's look.

### 2. Per-line DRAG + HOVER HIGHLIGHT (instant)
The ERG-dot-drag capability pattern, applied to dendrogram leaf tips:
- **Hover highlight:** as the cursor nears a leaf stub, draw a highlight overlay on that segment
  (thicken/recolour) so the owner sees what they'll grab. Hit-test the projected leaf-tip segments
  (the canvas knows the trace coords + the projection).
- **Drag:** grab a leaf tip → drag along the distance axis (vertical for the col tree, horizontal for
  the row tree) → write `meta.selom.dendrogramTips.tips[leaf] = extra` live (rAF-throttled), commit on
  release. Instant, undoable, NO re-run. Topology-SAFE because a leaf tip extends into the reserved gap
  and does not move any merge bar.
- **Out of scope (v1):** dragging an INTERNAL branch (moving a merge bar cascades to connected
  branches — needs the linkage adjacency stamped in meta; defer until the owner asks). v1 = leaf tips
  only, which is exactly the "end tip" the owner pointed at.

## Backend support needed
- `_dendro_trace` already emits the polyline; add a render-inert `meta.selom.dendrogram` block tagging
  the **leaf segments** (their index in the polyline + the leaf's x/row position) so the FE projection +
  hit-test don't have to re-derive "which segments are leaves" heuristically. Optional reserve of a small
  baseline gap so a tip has somewhere to grow even at lever=0 is a render choice (default no gap).
- Capability: declare `heatmapDendrogram` in `_capabilities.py` (or keep presence-gating on `xaxis2`/
  `yaxis3`). Resolve in `figure-model.ts`.

## Build order (next session)
1. Backend: stamp `meta.selom.dendrogram` leaf-segment tags (render-inert; golden regen).
2. FE projection: `applyDendrogramTips(spec)` in `lib/heatmap/dendrogram.ts` (pure) + wire it where the
   canvas builds the render spec (sibling of `projectOverlay`). Unit-test the projection geometry.
3. FE lever: the "Leaf tip length" slider → `tipLengthOps`. Live-verify it lengthens the stubs.
4. FE hover-highlight + leaf-tip drag plug-in (`components/figure/dendrogram-drag.ts`, sibling of the
   ERG `mark-drag.ts`). Live-verify drag on real iRPE data.
5. Gates + commit + update `CURRENT.md` + `memory selom-figure-edit-ux-pattern`.

## References
- `heatmap-clustermap-spec.md` (heatmap v2, T20) · `generalization-spec.md` (the capability plug-in recipe).
- `app/backend/skills/heatmap/run.py::_dendro_trace` (the polyline to tag) · `_capabilities.py`.
- `app/frontend/lib/heatmap/dendrogram.ts` (gutter-size sliders — add the tip lever + projection) ·
  `lib/figure-model.ts::projectOverlay` (the meta-pref render-time projection pattern to mirror) ·
  `components/figure/mark-drag.ts` (the ERG dot-drag to mirror for the tip drag) · `lib/patch.ts`
  (the DATA_VALUE_PATH server-op constraint that forces the meta-pref mechanism).
- `memory selom-figure-edit-ux-pattern` (INSTANT must be a LAYOUT edit, never `/data/*`) ·
  `selom-erg-manual-marks` (the dot-drag plug-in).
