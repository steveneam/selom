# Spec — Heatmap v2: publication clustermap (dendrograms · annotation tracks · rename · highlight)

> **Status: PARTIALLY BUILT — slices 1–3 + the owner's dendrogram-size control SHIPPED + live-verified
> 2026-06-25 (session T20). Remaining: annotation tracks · block-split · quant side track (slices 4–7).**
> Author Claude (Opus 4.8), owner Steven. Extends the shipped heatmap colour re-tone (`heatmap-spec.md`,
> `heatmapTones`). Driven by 5 owner reference screenshots (design targets) + the owner's
> rename-with-provenance discussion. **Build log at the bottom.**
>
> **Owner intent (verbatim distilled):** (1) a per-user **rename** of gene + sample labels that lives in
> **Figure Styling** so it's a cosmetic edit and **source provenance is never lost**; (2) the
> **connecting-line / clustering** treatment for BOTH genes and samples (we have rows only); (3) the
> publication clustermap furniture in the references — column dendrogram, **annotation tracks**, a
> quantitative side track, **gene-of-interest highlighting**, labels on the right, block splitting.

## Reference screenshots (the design targets)
Local copies: `graphify-out/scratch/heatmap-v2-refs/` (gitignored); originals in the owner's
`Pictures/Screenshots/`. What each demonstrates:
- **035134** — a **column dendrogram** (top tree clustering samples) + two stacked **categorical
  annotation tracks** (`type`, `dataset`) as coloured cell strips.
- **035617** — a **row dendrogram** (left) · gene labels on the **RIGHT**, some rendered **red**
  (genes of interest) · **coloured sample tick labels** (blue/red by group) · a `logFC` side track ·
  **row block-split** (a gap separating two row groups).
- **035636** — **BOTH** row + column dendrograms · a **group bar** on top (`DR` teal / `PD` red) · a
  **mean log₂FC** side bar-chart track (left) · gene labels right · `z-score` colour key · block-split.
- **035648 / 035701** — both-axis dendrograms with **coloured branches** (by cluster) · gene labels
  right · coloured sample labels (DR/PD).

## What we have today (heatmap v1)
One `heatmap` trace (row z-scored), `colorscale`/`zmid` (+ re-tone via `heatmapTones`), optional **row**
dendrogram (`dendrogram=row` → left-gutter SciPy tree, `skills/heatmap/run.py::heatmap_spec` +
`run_real.py::_order_rows`), gene **symbols** on the axis (`_genes.display_symbols`, this session).
Missing vs the references: **column** clustering, annotation tracks, a quant side track, gene
highlighting, right-side labels, block splitting, and a **rename** affordance.

## Feature set — classified INSTANT-cosmetic vs STAGED-recompute
The canonical split (`memory selom-figure-edit-ux-pattern`): cosmetic → figure store (instant,
undoable, **provenance-safe**); anything that changes the numbers/ordering → a backend re-run.

### STAGED (backend re-run; new heatmap params — the Figure-data Inputs + banner host them for free)
1. **Column clustering + top dendrogram.** `cluster: none | row | column | both` (supersedes
   `dendrogram`). Column clustering = `_order_rows` applied to the **transpose**; the top dendrogram is
   the left-gutter draw mirrored onto a top gutter (`xaxis2`/`yaxis2` analog). (035134/035636/035648.)
2. **Block splitting.** Split rows and/or columns into groups — by a chosen **categorical annotation**
   (e.g. condition DR vs PD) or by **cutting the dendrogram at k** — drawn as gaps + small group
   headers. Plotly: per-block subplot domains, or a single trace with gap rows/cols. (035617/035636.)
3. **Categorical annotation tracks.** Coloured category strips aligned to the columns (and optionally
   rows), from a **sample sheet** mapping `sample → {type, dataset, condition, …}`. Multiple stacked
   tracks. Each track = a thin 1-row `heatmap`/`bar` strip sharing the column axis, with its own
   discrete colour map + a small legend. (035134 type+dataset; 035636 DR/PD group bar.)
4. **Quantitative side track.** A bar-chart / heat strip aligned to rows (035636 "mean log₂FC") or
   columns — values computed from the data (e.g. per-gene mean log₂FC across a contrast) or supplied.
5. *(n_genes — existing.)*

### INSTANT cosmetic (figure store; provenance-safe; a new `heatmapLabels` capability)
6. **Rename labels (the headline owner ask).** Edit any gene (row) / sample (column) **display** label
   in Figure Styling → a JSON-Patch `set` on the trace's `x`/`y` array element, committed to the figure
   store (instant, undoable). **The dataset + run params + methods are untouched**, so provenance /
   reproducibility are intact — the figure merely *shows* the chosen label. The **original** label is
   preserved in per-point `customdata` + hover so the figure itself stays traceable.
7. **Highlight genes of interest.** Mark selected gene labels in a highlight colour (red in 035617) —
   a per-tick `tickfont`/annotation override (or a coloured label set). Cosmetic; no re-run.
8. **Label side + coloured tick labels.** Gene labels left|right; sample/gene tick labels coloured by
   their annotation group (needs the group mapping from track #3 or a manual assignment).
9. **Coloured dendrogram branches** by cluster (recolour the tree-line trace once a cut defines
   clusters — the colour is cosmetic; the cut that defines clusters is part of #1/#2).
10. *(Colour re-tone — shipped via `heatmapTones`.)*

## Architecture mapping (reuse the shipped spine — do NOT branch on skill id)
- **Staged** (#1–#5) → backend params on the heatmap skill + `run_real`; the generic Figure-data
  "Inputs" + pending-changes banner + re-run already host new params. Column clustering = transpose of
  `_order_rows`; annotation tracks = extra aligned traces + a sample-sheet input; split = subplot
  domains / gap rows. Goldens regen per slice (render-affecting, intended).
- **Instant** (#6–#9) → a new declared **`heatmapLabels`** capability (`_capabilities.py` +
  `resolveContract`, mirroring `heatmapTones`) gating a cosmetic plug-in:
  - pure `lib/heatmap/labels.ts` (sibling of `volcano/labels.ts`): `categoryLabels(spec)` (read the
    editable row/col labels), `renameLabelOps(traceIdx, axis, index, text)`, `highlightOps(genes)`,
    `labelSideOps(side)` — all pure JSON-Patch builders, node-env unit-tested.
  - a **Figure-Styling "Labels" panel** (sibling of `style-panel.tsx`'s Colour-scale section, or a new
    inspector tab): per-label rename fields (genes + samples) + a gene-of-interest multiselect + a
    left/right side toggle. Commits to the figure store (instant, undoable). Gated on `heatmapLabels`.
  - backend substrate: stamp each cell/axis the **original** label as `customdata` + a `hovertemplate`
    (so a rename keeps the source label in hover — the provenance guarantee), OPTIONAL so reuse stays
    byte-identical (the proteomics_de lesson).
- **Provenance invariant (owner-confirmed):** rename + highlight + side never touch the dataset, the
  run params, or the methods text → the canonical IDs stay the source of truth; the figure is a view.

## Build plan (next session, slices — ship + verify each)
1. **Column clustering + top dendrogram** (staged). `cluster` param (`none|row|column|both`); transpose
   `_order_rows`; draw the top dendrogram gutter (mirror the left one). Golden regen; BE test. FE
   control replaces the `dendrogram` select.
2. **`heatmapLabels` capability + rename** (instant). `_capabilities.py` + resolver + `lib/heatmap/
   labels.ts` (rename) + the Figure-Styling "Labels" panel + backend `customdata` original-label
   substrate. Unit tests + live verify (rename a gene + a sample; provenance/data unchanged; undoable).
3. **Gene-of-interest highlight + label side** (instant). Extend `labels.ts` + the panel. Live verify.
4. **Categorical annotation tracks** (staged) from a sample sheet — column tracks first (one colour
   strip per track + a legend). Golden regen.
5. **Block splitting** (staged) by a chosen categorical (gaps + group headers).
6. **Quantitative side track** (staged; mean log₂FC).
7. **Coloured dendrogram branches + coloured tick labels by group** (instant/cosmetic).
8. **Combined live verify** on the iRPE bulk data (+ a small sample sheet) + gates + commit; update
   `CURRENT.md` + `memory selom-figure-edit-ux-pattern`.

## Out of scope (this spec)
- Row annotation tracks beyond the single quant side track (column tracks first; rows can follow).
- Alternative clustering metrics/linkages (keep correlation→euclidean + average linkage as shipped).
- A general "annotation track" descriptor language — heatmap-specific for v2.
- Editing the underlying data (renames are display-only by design).

## Build log — T20 (2026-06-25)
Shipped + live-verified on the real iRPE bulk data (`D:\selom-data\alpk1\irpe_rawcounts`) through the
full app (upload → classify → run → editor → Figure-data re-run → style edits):
- **Slice 1 — column clustering + top dendrogram (staged).** New `cluster` param (`none|row|column|both`,
  replaces `dendrogram`); `_order_rows` gained an `orientation` arg; `_cluster` transposes the z-matrix
  to cluster samples and draws a TOP gutter mirroring the left one (`heatmap_spec` now takes
  `row_dendro` + `col_dendro`, lays out 4 cases). Rows still always cluster for ordering; the mode
  governs which trees draw + whether samples reorder. Golden regen (render-inert meta); BE tests.
- **Slice 2 — `heatmapLabels` capability + provenance-safe rename (instant).** Backend stamps the
  CANONICAL pre-symbol labels at `meta.selom.heatmapLabels` (render-inert) + declares the
  `heatmapLabels` capability (`_capabilities.py` → `resolveContract`). Rename writes the axis
  **`ticktext`** (a LAYOUT edit → client-side/instant/undoable) — NOT the data `x`/`y` (which are a
  server re-run AND insert-not-replace under JSON-Patch), so the data stays canonical, hover shows the
  original, and provenance is intact. `lib/heatmap/labels.ts` (pure) + a Figure-Styling "Labels" panel.
- **Slice 3 — gene-of-interest highlight + label side (instant).** Highlight wraps a label's ticktext in
  an inline colour span (`<span style="color:#dc2626">…`), since a uniform `tickfont.color` can't colour
  one tick; side = `yaxis.side`. The panel hides the side toggle and shows a "pinned right" note when a
  row dendrogram owns the left.
- **Owner add — dendrogram-size control (instant).** Owner asked mid-session for a way to give the trees
  more room so the connections read clearly. `lib/heatmap/dendrogram.ts` (pure) re-proportions the
  gutter vs heatmap axis DOMAINS (a layout edit → instant, undoable, no re-run); a "Dendrogram" Style
  section with **Row tree width** / **Column tree height** sliders (shown per present tree). Live-verified
  spreading the column tree to 45%.
- **Note (out of scope, carried):** a re-run resets the cosmetic ticktext labels (new version = fresh
  spec), mirroring the old volcano behaviour before `carryLabels`. A heatmap label-persistence analog
  could follow if the owner wants it.

## References
- `docs/figure-data-capabilities/heatmap-spec.md` (v1 re-tone, shipped) ·
  `docs/figure-data-capabilities/generalization-spec.md` ("Extending to a new chart kind" recipe).
- `app/backend/skills/heatmap/{run,run_real}.py` (`heatmap_spec`, `_order_rows` — the transpose target,
  the dendrogram-gutter draw to mirror onto the top axis).
- `app/backend/skills/_capabilities.py` (`heatmapTones` → add `heatmapLabels`) · `skills/_genes.py`
  (`display_symbols`, this session) · `skills/theme.py` (`automargin` preserve, this session).
- `app/frontend/lib/heatmap/colorscale.ts` (the v1 pure-transform pattern to mirror in `labels.ts`) ·
  `components/figure/panels/style-panel.tsx` (Colour-scale section → add a Labels section/tab) ·
  `lib/figure-model.ts` (`resolveContract`).
- `memory selom-figure-edit-ux-pattern` (INSTANT vs STAGED) · `generalize-via-flagged-plugins-over-shared-spine`.
- Reference screenshots: `graphify-out/scratch/heatmap-v2-refs/Screenshot 2026-06-25 0351*/0356*.png`.
</content>
