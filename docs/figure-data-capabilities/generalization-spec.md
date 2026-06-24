# Spec — Capability generalization v2: global gesture flip + volcano threshold direct-manipulation

> **Status: DRAFT (2026-06-25) — author Claude (Opus 4.8), owner Steven.** Implements §11 of
> `docs/figure-data-capabilities/spec.md` (the shipped v1 capability contract). Two owner decisions
> set the scope (interview 2026-06-25):
> 1. **Shape = volcano flagship (deep).** Full direct-manipulation on the volcano: drag the FC /
>    p-value threshold lines → points re-colour LIVE client-side → up/down counts update → ONE
>    re-run commits to the stats table + methods. Prove the staged-edit pattern on the highest-value
>    chart, on a thin central capability stamp built to extend. (Heatmap/UMAP/etc. are a later pass.)
> 2. **Gesture default = flip globally to no-op.** Every figure, not just ERG, defaults the plot-area
>    drag to a no-op; zoom + pan become deliberate modebar buttons app-wide; wheel-zoom stays off.

## What
Two coupled changes that turn the ERG-only capability surface into the general model:

- **(A) Global gesture flip.** The resolved gesture default becomes **no-op** for *every* figure
  (`dragmode:false`), with zoom/pan as modebar buttons and wheel-zoom off — the model ERG already
  uses, now app-wide. A figure may still opt back into a drag mode by declaring
  `meta.selom.capabilities.gesture.default`. This is a deliberate, owner-chosen behaviour change: the
  v1 invariant "absent capabilities → Plotly box-zoom" is replaced by "absent → no-op".

- **(B) Volcano threshold direct-manipulation.** The volcano declares a new `thresholds` capability.
  The editor then wires a chart-specific plug-in (mirroring the ERG landmark-marks plug-in exactly):
  drag a threshold line on the canvas → a pure client-side transform **re-buckets every point**
  (up/down/n.s.) and **moves the lines** instantly → the change **stages** into the lifted `fdParams`
  (`fc_threshold` / `fdr_threshold`) → the **"Pending changes — Re-run"** banner appears → one
  explicit re-run recomputes the DE stats table, the top-N labels, and the methods text.

This is the same **instant-cosmetic vs staged-recompute** split the canonical UX model defines
(`memory selom-figure-edit-ux-pattern`): the recolour + line move are instant (client-side); the
re-measure (exact counts, labelled genes, the stats table, downstream methods) is staged behind one
re-run.

## Why this architecture (the ERG parallel)
The v1 ERG surface is already the template. Generalizing = adding a **second** chart-specific
direct-manipulation plug-in behind a **second** declared capability flag, while the generic spine
(contract resolver · staged-edit `fdParams` lift · pending-changes banner · canvas gesture model)
is reused unchanged. The parallel is exact:

| Concern | ERG (v1, shipped) | Volcano (this spec) |
|---|---|---|
| Declared capability flag | `tools.landmarkMarks` | `tools.thresholds` |
| Client-side live transform | `lib/erg/marks.ts::applyStagedMarks` (move dots) | `lib/volcano/thresholds.ts::applyStagedThresholds` (re-bucket + move lines) |
| Canvas drag wiring | `components/figure/mark-drag.ts::wireMarkDrag` | `components/figure/threshold-drag.ts::wireThresholdDrag` |
| Numeric editor panel | `components/project/marks-editor.tsx` | `components/project/threshold-editor.tsx` |
| Staged param(s) | `manual_marks` (+ `marks`) | `fc_threshold`, `fdr_threshold` |
| Re-run refreshes | measured µV, stats table, downstream | DE counts, top-N labels, stats table, methods |

The generic machinery (`project-workspace` `fdParams`/`fdDirty`/banner, `figure-data-panel` gating on
a resolved capability, `deriveFigureModel`) needs only **additive** changes — a new boolean and a new
gate — never a rewrite.

## Context — verified this session
- **Resolver** (`lib/figure-model.ts`): `resolveContract` (L253–276) maps
  `meta.selom.capabilities.gesture.default` → `GestureConfig.dragmode`. **Absent → `undefined`**
  today (L264–269), which the canvas reads as "leave Plotly's default = box-zoom". `FigureModel.
  capabilities` (L158–172) carries the inferred floor + declared `landmarkMarks`/`modelFit`.
- **Canvas** (`components/figure/figure-canvas.tsx`): applies `dragmode` only when
  `gesture.dragmode !== undefined` (research L72–86); `scrollZoom:false` is hardcoded (L216);
  `wireMarkDrag` is gated on `capabilities.landmarkMarks` (L189–197). A non-declaring figure today =
  box-zoom default.
- **Volcano** (`skills/volcano/run.py::_assemble`): `data` = three `scattergl` marker traces named
  `"n.s."`, `"up"`, `"down"` (+ optional `labels` text trace, `highlighted` markers+text). Their
  **union is every plotted point** `(x=log2FC, y=−log10 padj)`. `shapes` = two vertical dashed lines
  at `x=±fc_t` (`yref:"paper"`) and one horizontal dashed line at `y=y_cut=−log10(fdr_t)`
  (`xref:"paper"`). The full DE table is `spec["table"]` (`_table.de_table`). Params: `fc_threshold`
  (0–5, default 1.0), `fdr_threshold` (0–1, default 0.05), `top_n`, `highlight`.
- **No non-ERG skill stamps `meta.selom`** today; `_tracegrid.grid_spec` is the only stamper.
  `theme.apply(figure, skill_id)` (via `contract._execute`) is the single seam every figure passes
  through after its runner — the right home for a central, per-skill capability stamp.

## Design

### §A — Global gesture flip (FE only; no backend change)
One change in `resolveContract` (`lib/figure-model.ts`): the `dragmode` fallback flips from
`undefined` to `false`, and `scrollZoom` defaults to `false`.

```ts
// BEFORE: absent → undefined (canvas leaves Plotly default = box-zoom)
const dragmode: Dragmode | undefined =
  g?.default === "none" ? false
  : g?.default === "select"|"pan"|"zoom" ? g.default
  : undefined;
const gesture = { dragmode, zoomTools: g?.zoomTools !== false,
                  scrollZoom: typeof g?.scrollZoom === "boolean" ? g.scrollZoom : undefined };

// AFTER: absent OR "none" → false (global no-op); a chart may opt INTO a drag mode by declaring it.
const dragmode: Dragmode =
  g?.default === "select" || g?.default === "pan" || g?.default === "zoom" ? g.default : false;
const gesture: GestureConfig = {
  dragmode,
  zoomTools: g?.zoomTools !== false,                                  // keep zoom/pan buttons
  scrollZoom: typeof g?.scrollZoom === "boolean" ? g.scrollZoom : false, // wheel-zoom off by default
};
```
- `GestureConfig.dragmode` becomes non-optional (`Dragmode`, always resolved). `scrollZoom` becomes
  always-defined (`boolean`).
- **Canvas** reads `gesture.scrollZoom` instead of the hardcoded `false` (fixes the research-flagged
  hardcode; default behaviour identical since it now resolves to `false`).
- ERG figures (`gesture.default:"none"`) still resolve to `false` — unchanged. A future exploration
  chart that wants box-zoom declares `capabilities.gesture.default:"zoom"`.
- Net: every figure's plot-area drag is a no-op; **Zoom**/**Pan** modebar buttons enter those modes
  deliberately; wheel does not zoom. Cosmetic `edits` (legend/annotation/shape drag) and the
  capability-gated dot-/line-drag are unaffected (they don't go through the `dragmode` path).

### §B — The `thresholds` capability (contract + resolver)
Add a declared tool gate, parallel to `landmarkMarks`.

```ts
// SelomCapabilities.tools (lib/figure-model.ts)
tools?: { landmarkMarks?: boolean; modelFit?: …; scaleBar?: boolean; thresholds?: boolean; };

// FigureModel.capabilities
thresholds: boolean;   // declared volcano FC/FDR threshold direct-manipulation

// resolveContract
const thresholds = caps?.tools?.thresholds === true;   // declared-only, no inference fallback
```
No migration fallback (unlike `landmarkMarks`' `hasSeededMarks`) — the volcano declares it explicitly.

### §C — Backend stamp seam (`skills/_capabilities.py` + `theme.apply`)
A small central module stamps `meta.selom.capabilities` by skill id, injected once in `theme.apply`
so it is not scattered across 30 skills.

```python
# skills/_capabilities.py
_PROFILES = {
    "volcano": {
        "gesture": {"default": "none", "zoomTools": True, "scrollZoom": False},
        "tools": {"thresholds": True},
    },
}
def stamp(spec: dict, skill_id: str) -> dict:
    prof = _PROFILES.get(skill_id)
    if not prof or not isinstance(spec, dict) or "layout" not in spec:
        return spec
    selom = spec["layout"].setdefault("meta", {}).setdefault("selom", {})
    selom.setdefault("capabilities", {}).update(prof)   # never clobber a richer existing stamp
    return spec
```
- Called from `theme.apply` after styling, before return. **Render-inert** (Plotly ignores `meta`).
- ERG keeps stamping in `_tracegrid` (already richer/figure-instance-aware); `_capabilities.stamp`
  only fills skills with no existing stamp — `setdefault`/`update` must not overwrite ERG's block.
  (ERG ids are absent from `_PROFILES`, so they're untouched regardless.)
- The volcano `gesture` block is redundant with §A's global flip but stamped for self-documentation
  and to keep the contract explicit per the v1 design (D6: declared > inferred).

### §D — Volcano threshold transforms (`lib/volcano/thresholds.ts`, pure)
The client-side engine, sibling of `lib/erg/marks.ts`.

```ts
interface VolcanoThresholds { fc: number; fdr: number; }     // fdr is the p-value cut, not y_cut
interface ThresholdReadout  { up: number; down: number; ns: number; } // live counts

/** Read the figure's current thresholds from its shapes (fc = |vertical x|, fdr = 10^(−horizontal y)). */
function readThresholds(spec: FigureSpec): VolcanoThresholds | null;

/** Gather every plotted point from the union of the up/down/n.s. traces (always re-gather the union,
 *  never assume the current partition — re-bucketing is idempotent). */
function gatherPoints(spec: FigureSpec): { x: number; y: number }[];

/** Pure: re-bucket all points by {fc,fdr} and move the 3 threshold lines. Returns the new spec +
 *  the live up/down/ns counts. No DE table, no gene names, no re-run. Labels/highlight left as-is. */
function applyStagedThresholds(spec: FigureSpec, t: VolcanoThresholds):
  { spec: FigureSpec; readout: ThresholdReadout };
```
Bucketing (mirrors `run_real.py` exactly): `y_cut = −log10(fdr)`;
`up` iff `x ≥ fc && y ≥ y_cut`; `down` iff `x ≤ −fc && y ≥ y_cut`; else `ns`. Clamp `fc∈[0,5]`,
`fdr∈(0,1]`. The three bucket traces are identified **by name** (`"up"`/`"down"`/`"n.s."`); the
`labels`/`highlighted` traces are excluded from the gather and left untouched (they refresh on
re-run). The three line shapes are identified by orientation (two with `x0==x1` → FC; one with
`y0==y1` & `xref:"paper"` → FDR).

### §E — Threshold drag (`components/figure/threshold-drag.ts`)
A capture-phase drag, sibling of `mark-drag.ts`, gated on `capabilities.thresholds`:
- Arm on `mousedown` within a **magnet** band (≈24px in pixel space) of a threshold line; show a
  crosshair readout (`FC ≥ 1.4` / `p ≤ 0.032  ·  up 212 · down 188`).
- A vertical (FC) line drags **horizontally only**; both FC lines mirror to `fc = |x|`. The FDR line
  drags **vertically only** → `fdr = 10^(−y)`.
- On each move: call `onThresholdChange(next)` (stages into `fdParams`) and re-apply
  `applyStagedThresholds` to move the lines + recolour live. Block Plotly's gesture for that drag
  (consistent with the dot-grab); with the global `dragmode:false` there is no box-zoom to fight.
- Wired in `figure-canvas.tsx` **iff** `model.capabilities.thresholds` (parallel to the
  `wireMarkDrag`/`landmarkMarks` gate). Never attached otherwise.

### §F — Threshold editor panel (`components/project/threshold-editor.tsx`)
A numeric panel in the **Figure-data** window, gated on `capabilities.thresholds` (parallel to the
Marks editor's `landmarkMarks` gate in `figure-data-panel.tsx`):
- Two numeric inputs (FC ≥, p ≤) bound to `fc_threshold` / `fdr_threshold` via the existing
  `onParamsChange` lift — a numeric edit **stages** (does not re-run), exactly like a mark-time edit.
- A live **up / down / n.s.** count readout from `applyStagedThresholds` on the staged values.
- The preview compositing in `project-workspace.tsx` (`previewSpec`) applies `applyStagedThresholds`
  for a volcano (when `capabilities.thresholds`), the same place it applies `applyStagedMarks` for
  ERG. The shared `fdDirty`/banner needs no change — `fc_threshold`/`fdr_threshold` differing from
  the figure's run params already trips `fdDirty`.

### §G — Staged-edit wiring (reuse, minimal additions in `project-workspace.tsx`)
- `previewSpec` (today applies ERG staged marks + label hide): add a branch — when the active model's
  `capabilities.thresholds` and `fdParams` carry `fc_threshold`/`fdr_threshold`, run
  `applyStagedThresholds(base, {fc, fdr})` for the live preview.
- `onMarkMove` has an analog `onThresholdChange(next)` →
  `setFdParams(p => ({ ...p, fc_threshold: next.fc, fdr_threshold: next.fdr }))`.
- The re-run path (`rerunFigureWithParams(fdParams)`), the banner, and `fdDirty` are unchanged.

### §H — Gene labelling (slices 7–9; owner interview 2026-06-25, design LOCKED)
The third volcano direct-manipulation, and the first **instant cosmetic** one (the threshold edit is
staged; a label is not). Owner decisions: **both surfaces** (canvas click + a Statistics-table Label
toggle) write **one shared `label_genes` set**; a label is **live/instant** — a text annotation on an
already-plotted point, no re-run, riding the figure store's undo/JSON-Patch. `top_n` stays the
auto-suggest seed (the auto text-trace labels); the amber `highlight` gene-set panel stays separate.

- **(C2) Backend substrate.** `volcano/run.py::_assemble` stamps each up/down/n.s. point's gene SYMBOL
  (+ adj p) as per-point `customdata` (`[gene, padj]`) and a `hovertemplate` (gene · log2FC · adj p).
  This is what lets the canvas read a clicked point's gene and the table toggle find a gene's
  coordinates by name. `customdata` is optional in `_assemble` (proteomics_de reuses it with bare
  `(x,y)` pairs → keys omitted, its golden unchanged). The volcano golden regens (render-inert hover).
- **`geneLabels` capability** (`tools.geneLabels`, declared-only) → `model.capabilities.geneLabels`;
  stamped for volcano in `_capabilities.py` next to `thresholds`.
- **`lib/volcano/labels.ts` (pure, sibling of `thresholds.ts`):** `gatherLabelablePoints` /
  `labelableGenes` / `findPoint` (union of the bucket traces by their `customdata` gene) ·
  `labeledGenes` / `isLabeled` (on a volcano every `layout.annotations` entry is a label, identified
  by its `text` = the gene) · `toggleLabelOps(spec, point)` + `toggleGeneLabelOps(spec, gene)` (the
  JSON-Patch add/remove of one label annotation) · `pointFromClick(pt)`.
- **Surface 1 — canvas click** (`figure-canvas.tsx`, new `onToggleLabel`, gated on `geneLabels`): a
  click on a point that carries a gene toggles its label and stops (else falls through to
  click-to-select). Threaded through `EditorWorkspace`; `project-workspace.onToggleLabel` commits the
  ops to the **figure store** (instant + undoable).
- **Surface 2 — Statistics-table Label column + gene search** (`stats-panel.tsx`, optional `labeling`
  prop): a Tag toggle per row (checked from `labeledGenes`, disabled when not plotted) + a search box.
  `project-workspace.statsLabeling` supplies it for a volcano open in the store; `onToggleGeneLabel`
  commits to the **same** figure store. `openStats` now `figure.init`s the figure so the table and the
  canvas share one editable spec (one label set, undoable).
- **Threshold coherence.** `applyStagedThresholds` / `gatherPoints` now carry per-point `customdata`
  through a re-bucket, so a gene's row stays aligned with its point after a threshold drag.

## Requirements
- **R1 — global gesture flip.** Absent/`"none"` gesture default resolves to `dragmode:false` +
  `scrollZoom:false` for every figure; zoom/pan buttons stay. Canvas reads `gesture.scrollZoom`
  (no hardcode). A declared `gesture.default∈{zoom,pan,select}` still wins.
- **R2 — `thresholds` capability.** New declared `tools.thresholds` → `model.capabilities.thresholds`
  (declared-only). Backward-compatible, tolerant reader.
- **R3 — central stamp.** `skills/_capabilities.py::stamp` injects the volcano profile in
  `theme.apply`; never clobbers an existing (ERG) stamp; render-inert.
- **R4 — live re-bucket.** `applyStagedThresholds` re-buckets the union of up/down/n.s. by new
  thresholds + moves the 3 lines, pure + client-side, returning live counts. Idempotent.
- **R5 — capability-gated drag.** `wireThresholdDrag` is wired **iff** `capabilities.thresholds`;
  never on a non-declaring figure.
- **R6 — staged edit.** A drag or a numeric FC/FDR edit stages into `fdParams`, moves the lines +
  recolours live, trips the pending-changes banner; one re-run recomputes the DE table + top-N
  labels + methods. No re-run per drag.
- **R7 — no regression elsewhere.** Non-volcano, non-ERG figures gain only the global gesture flip
  (intended) — no threshold tools, no new panels. ERG behaviour byte-identical (its stamp is richer
  and untouched; its gesture already resolved to `false`).
- **R8 — goldens.** Only `volcano` gains a `meta.selom.capabilities` block + per-point `customdata`/
  `hovertemplate` (golden regen, render-inert). No other skill's output changes (proteomics_de reuses
  `_assemble` with bare `(x,y)` → no customdata, byte-identical). ERG goldens unchanged.
- **R9 — gene labelling (§H).** `geneLabels` declared-only capability; a click on a plotted point OR a
  Statistics-table Label toggle pins/unpins the gene as a `layout.annotations` text label — instant,
  undoable (figure store / JSON-Patch), NO re-run, one shared set across both surfaces. The gene
  symbols ride each point's `customdata`. `top_n` (auto text labels) + `highlight` (amber) unchanged.

## Decisions
- **D1 — flip in the resolver, not per-skill stamp.** The global no-op default is one change in
  `resolveContract`; stamping `gesture` on 30 skills is redundant. Skills opt OUT (back to box-zoom)
  by declaring `gesture.default:"zoom"`. Reversible (revert the fallback to `undefined`).
- **D2 — volcano direct-manip as a chart-specific plug-in behind a flag** (owner: volcano flagship).
  Mirrors ERG exactly; the editor stays generic (reads a resolved boolean, never `if skillId`).
  Reversible.
- **D3 — live preview = recolour + line move + counts only; labels/table/methods on re-run.** The
  figure carries every point's (x,y) but only the top-N gene *names* — so arbitrary new labels can't
  be drawn client-side. Matches the ERG model (dot moves live; measured values refresh on re-run).
  Reversible/extensible (stamp per-point `customdata` names later for live labels).
- **D4 — identify buckets by trace name, lines by orientation.** Avoids coupling to trace/shape
  order. The volcano plug-in owns this knowledge (it's chart-specific by definition). Reversible.
- **D5 — central `_capabilities.py` stamp seam.** One home for per-skill profiles, injected in the
  one place every figure passes through (`theme.apply`); extends to the next chart by adding a row.
  Reversible.

## Invariants
- A figure with no declared capabilities now defaults to **no-op drag + zoom-button + no wheel-zoom**
  (the new global floor; supersedes the v1 "box-zoom" floor — intentional).
- `applyStagedThresholds` is pure and idempotent: re-gathering the union and re-bucketing twice with
  the same thresholds yields the identical spec.
- Stamping `capabilities` changes **zero rendered pixels** (render-inert `meta`); it changes only
  editor affordances. Volcano's plotted data/lines are unchanged until a threshold actually moves.
- One read surface: editor/canvas/Figure-data read `FigureModel`, never `meta.selom` directly.
- The re-run is the only thing that touches the DE stats table, labelled genes, or methods.

## Error behavior
- Malformed/partial `capabilities` → ignored field-by-field (existing tolerant reader); never throws.
- A volcano with unexpected trace names / missing lines → `readThresholds`/`gatherPoints` return
  null/empty; the drag finds nothing to arm and the editor shows its values without a live count
  (no crash). The numeric edit + re-run still work (params drive the backend regardless).
- `fdr ≤ 0` → clamp to a tiny positive (`y_cut` finite); `fc < 0` → `|fc|`.

## Testing strategy
- **FE unit:** `resolveContract` — absent → `dragmode:false`+`scrollZoom:false`; `"zoom"` declared →
  `"zoom"`; ERG `"none"` → `false`. (Updates the v1 tests that asserted `undefined`.)
- **FE unit:** `applyStagedThresholds` — re-buckets a known point set correctly at two thresholds;
  moves the 3 lines; idempotent; counts match; labels/highlight untouched.
- **FE unit:** `readThresholds` round-trips `{fc,fdr}` ↔ line coords (`fdr ↔ 10^(−y_cut)`).
- **FE unit:** the canvas gesture/drag wiring — `wireThresholdDrag` attached iff
  `capabilities.thresholds`; not on a UMAP/ERG figure.
- **BE:** `_capabilities.stamp` adds the volcano block; is a no-op for a non-profiled skill; never
  clobbers an ERG stamp. Volcano golden regen (render-inert); ERG + all other goldens byte-identical.
- **Live (real DE CSV — e.g. `D:\selom-data\eyg28` volcano):** drag the FC line → points recolour +
  counts update live, no re-run; the banner appears; one re-run updates the stats table + top-N
  labels; a UMAP figure → no threshold tools, no-op drag, Zoom button works; ERG trace grid still
  drags dots + stages. Full-app smoke test (keep WebGL behind `dynamic(ssr:false)`).

## Build plan (slices)
1. **Global gesture flip (FE).** `resolveContract` fallback → `false`; canvas reads
   `gesture.scrollZoom`; update gesture unit tests; **full-app smoke** (every chart no-op default +
   Zoom button; ERG unchanged). *Self-contained, app-wide, low-risk, reversible — ship + verify first.*
2. **`thresholds` capability + stamp (FE+BE).** Resolver `thresholds` boolean; `_capabilities.py`
   + `theme.apply` injection; volcano golden regen; BE stamp test + FE resolver test.
3. **Volcano transforms (FE).** `lib/volcano/thresholds.ts` (`readThresholds`/`gatherPoints`/
   `applyStagedThresholds`) + unit tests. *(no UI yet)*
4. **Threshold editor panel (FE).** `threshold-editor.tsx` gated on `capabilities.thresholds`;
   `previewSpec` + `onThresholdChange` wiring; live counts; staged numeric edits + banner.
5. **Threshold drag (FE).** `threshold-drag.ts` (magnet + axis-constrained + mirror + readout);
   canvas gate on `capabilities.thresholds`.
6. **Threshold verify.** FE gates + BE focused + golden regen + ruff. *(static-green this session;
   the live pass is deferred to slice 9, after labelling — owner-set order.)*
7. **Gene-label substrate (FE+BE, §H).** `volcano/run.py`+`run_real.py` per-point `customdata`
   (`[gene, padj]`) + `hovertemplate`; `geneLabels` capability + `_capabilities.py`; volcano golden
   regen; `applyStagedThresholds`/`gatherPoints` carry customdata through a re-bucket.
8. **Gene-label UI (FE, §H).** `lib/volcano/labels.ts` (pure) + unit tests; canvas `onToggleLabel`
   (click-to-label, gated) threaded through `EditorWorkspace`; Statistics-table Label column + search
   (`stats-panel.tsx` `labeling` prop); `project-workspace` handlers + `openStats` store-init.
9. **Combined verify.** FE gates + BE focused + ruff; **one live browser pass** on real DE data
   (`D:\selom-data\eyg28`): threshold drag (recolour + counts + banner + re-run) + gene labelling
   (canvas click + table toggle, instant + undoable) + the global-gesture-flip regression (UMAP/ERG);
   full-app smoke. Update `CURRENT.md` + `memory selom-figure-edit-ux-pattern`; commit (BE/FE/docs).

## Out of scope (this pass)
- Heatmap colorscale-midpoint drag, UMAP color-remap / lasso, bar/box direct-manip → a later §11 pass.
- Persisting the gene-label set across a re-run (labels are instant cosmetic, reset on a new version;
  `top_n` re-seeds the auto labels). Live re-labelling now IS in scope via §H (per-point `customdata`).
- Any change to the DE math, `de_table`, or the methods builder.
- A general "any threshold on any chart" descriptor language — volcano-specific plug-in for v1.

## References (exact integration points)
- `app/frontend/lib/figure-model.ts` — `resolveContract` (§A/§B), `FigureModel.capabilities`,
  `GestureConfig`, `SelomCapabilities`.
- `app/frontend/components/figure/figure-canvas.tsx` — gesture application + `scrollZoom` + the
  `wireThresholdDrag` gate (§A/§E).
- `app/frontend/components/figure/threshold-drag.ts` (new, §E) — sibling of `mark-drag.ts`.
- `app/frontend/lib/volcano/thresholds.ts` (new, §D) — sibling of `lib/erg/marks.ts`.
- `app/frontend/components/project/threshold-editor.tsx` (new, §F) — sibling of `marks-editor.tsx`.
- `app/frontend/components/project/{project-workspace,figure-data-panel}.tsx` — `previewSpec`,
  `onThresholdChange`, the capability gate (§F/§G).
- `app/backend/skills/_capabilities.py` (new, §C) + `skills/theme.py::apply` injection.
- `app/frontend/lib/volcano/labels.ts` (new, §H) — sibling of `thresholds.ts`; the gene-label set.
- `app/frontend/components/figure/{figure-canvas,editor-workspace}.tsx` — `onToggleLabel` (§H).
- `app/frontend/components/project/stats-panel.tsx` — the `labeling` Label column + search (§H).
- `app/backend/skills/volcano/{run,run_real}.py::_assemble` — per-point gene `customdata` (§H).
- `app/backend/skills/volcano/run.py::_assemble` — the trace/shape shape the transform reads (§D).
- `docs/figure-data-capabilities/spec.md` (v1, §11) · memory `selom-figure-edit-ux-pattern`
  (the canonical UX model) · `selom-erg-manual-marks` · `full-app-smoke-test-before-handoff`.
