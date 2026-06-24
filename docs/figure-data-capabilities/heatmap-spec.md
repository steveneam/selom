# Spec — Heatmap colour-scale direct-manipulation (`heatmapTones`)

> **Status: DRAFT (2026-06-25) — author Claude (Opus 4.8), owner Steven.** The third worked example of
> the capability-driven figure-editing surface (after ERG landmark marks and the volcano), built by
> following the **"Extending to a new chart kind"** recipe in `generalization-spec.md`. Owner interview
> (2026-06-25) chose: **heatmap**, **one chart deep** (a full plug-in like the volcano), after the
> gene-label-persistence quick-win.

## What
Give the expression heatmap the same direct-manipulation depth the volcano has — but for the
**colour mapping** instead of thresholds:

- **(INSTANT, cosmetic) Re-tone the colour scale** — shift the diverging **midpoint** (`zmid`) and set
  the **saturation / clip range** (`zmin`/`zmax`) so faint or saturated cells read clearly. A pure
  client-side restyle of the existing z-matrix → committed to the **figure store** (undoable, no re-run),
  exactly like the volcano gene labels. Two surfaces write the same edit:
  1. **Style inspector** — Midpoint + Saturation sliders added to the existing "Colour scale" section
     (live drag → one undo entry via `SliderField`'s `store.set`/`store.flush`).
  2. **Canvas colorbar drag** — drag on the colour bar itself: the **top** handle sets `zmax`, the
     **bottom** handle sets `zmin`, the **middle** shifts `zmid`. Gated on a declared capability.

- **(STAGED, recompute) Genes & clustering** — `n_genes`, `dendrogram` (none|row), `groupby` already
  re-run through the **generic Figure-data "Inputs" + pending-changes banner**. **No new code** — the
  staged half is free; this spec only adds the instant colour layer + the canvas drag.

## Why this architecture (the ERG / volcano parallel)
Same spine, third plug-in. The split is the canonical instant-vs-staged model
(`memory selom-figure-edit-ux-pattern`): the re-tone is **instant cosmetic** (figure store, like gene
labels), the gene/cluster change is **staged recompute** (the existing banner + re-run, like volcano
thresholds). The generic machinery is reused unchanged.

| Concern | ERG (shipped) | Volcano (shipped) | Heatmap (this spec) |
|---|---|---|---|
| Declared capability flag | `tools.landmarkMarks` | `tools.thresholds` / `tools.geneLabels` | `tools.heatmapTones` |
| Client-side transform | `lib/erg/marks.ts` | `lib/volcano/thresholds.ts` / `labels.ts` | `lib/heatmap/colorscale.ts` |
| Canvas drag plug-in | `mark-drag.ts` | `threshold-drag.ts` | `colorbar-drag.ts` |
| Numeric / panel editor | `marks-editor.tsx` | `threshold-editor.tsx` | `style-panel.tsx` "Colour scale" section |
| Edit class | staged (re-measure) | staged (re-bucket) + instant (label) | **instant** (re-tone) + staged-is-free (genes/cluster) |
| Commits to | `fdParams` → re-run | `fdParams` → re-run / figure store | **figure store** (undoable, no re-run) |

The only genuinely-new declared-gated surface is the **canvas colorbar drag**; the panel re-tone lives in
the existing inference-driven Style panel (a pure restyle valid on any heatmap, like the scale picker
already there). So the capability buys the *canvas direct-manipulation*, and documents the contract.

## Context — verified this session
- **Heatmap skill** (`skills/heatmap/run.py::heatmap_spec`): one `heatmap` trace — `z` (genes×groups,
  **row z-scored** so values ≈ [−3, 3]), `x`/`y` labels, `colorscale:"RdBu"`, `reversescale:true`,
  `zmid:0`, a `colorbar`. Optional 2nd `scatter` trace = the dendrogram lines (`dendrogram=row`). **No
  `table`.** Params: `n_genes` (5–100), `groupby` (scRNA), `dendrogram` (none|row).
- **Style panel** (`components/figure/panels/style-panel.tsx`): `ColorscaleControls` already offers a
  named-scale `SelectField` + a reverse `SwitchField`, gated on `cap.colorscale &&
  model.heatmapTraceIndices.length > 0` (inferred). `ColorbarControls` offers position + length. **No
  midpoint / clip control exists yet** — that's the gap.
- **Model** (`lib/figure-model.ts`): `heatmapTraceIndices`, `capabilities.colorscale`/`colorbar` are
  inferred today. The declared contract resolves in `resolveContract` (declared-only tools).
- **Canvas** (`components/figure/figure-canvas.tsx`): drag plug-ins (`wireMarkDrag`,
  `wireThresholdDrag`) are wired in `bindGestures`, each gated on a resolved capability; the styling
  artboard passes a `store`, the Figure-data preview does not. `edits.colorbarPosition:true` already
  lets Plotly drag the colour bar's *position* (not its tones).
- **`_capabilities.py`**: the one central per-skill stamp seam, injected in `theme.apply`; volcano is the
  only profile today. ERG stamps richer blocks in `_tracegrid` (never clobbered).

## Design

### §A — `heatmapTones` capability (contract + resolver)
Declared tool gate, parallel to `thresholds`/`geneLabels`.
```ts
// SelomCapabilities.tools (lib/figure-model.ts)
tools?: { …; heatmapTones?: boolean; };
// FigureModel.capabilities
heatmapTones: boolean;   // declared heatmap colour-scale direct-manipulation (canvas colorbar drag)
// resolveContract
const heatmapTones = caps?.tools?.heatmapTones === true;   // declared-only, no inference fallback
```

### §B — Backend stamp (`skills/_capabilities.py`)
Add the heatmap profile next to the volcano's:
```python
"heatmap": {
    "gesture": {"default": "none", "zoomTools": True, "scrollZoom": False},
    "tools": {"heatmapTones": True},
},
```
Render-inert (Plotly ignores `meta`). Injected once in `theme.apply`. Regen the heatmap golden(s)
(capabilities block only — render-inert). ERG/volcano/all other goldens byte-identical.

### §C — Pure transform (`lib/heatmap/colorscale.ts`, sibling of `volcano/thresholds.ts`)
```ts
export interface HeatmapTones { colorscale: string | null; reversed: boolean; zmid: number; zmin: number; zmax: number; }
export interface ZExtent { min: number; max: number; }

function heatmapTraceIndex(spec): number;          // first heatmap trace, or -1 (by TYPE, never order)
export function zExtent(spec): ZExtent | null;      // min/max over every finite z cell
export function readTones(spec): HeatmapTones | null;  // zmin/zmax fall back to the data extent; zmid → 0
export function clampToExtent(v, ext): number;      // clamp a z value into a padded data extent
export function toneOps(indices: number[], patch: Partial<...>): Operation[];  // JSON-Patch ops over ALL heatmap traces
```
- `toneOps` maps `zmid`/`zmin`/`zmax` → `/data/{i}/{leaf}`, `reversed` → `/data/{i}/reversescale`,
  `colorscale` → `/data/{i}/colorscale`, for **every** heatmap trace index (so a multi-heatmap figure
  stays consistent — mirrors the style panel's `apply` and `seriesColorOps`).
- Identify heatmap traces by **type** (`heatmap`/`heatmapgl`/`contour`), never index order.
- Pure + idempotent; node-env vitest. The panel + the canvas drag both build their edits with `toneOps`.

### §D — Style-panel re-tone (`style-panel.tsx`, the panel surface)
Extend `ColorscaleControls` (inference-driven, unchanged gate) with two `SliderField`s under the existing
Scale + Reverse:
- **Midpoint** — `value=zmid`, `min/max` = the z extent (rounded), `step 0.1`; `build=(v)=>toneOps(idx,{zmid:v})`.
- **Saturation ±** — symmetric clip half-range `sat = (zmax−zmin)/2`; `min` small (e.g. 0.5) → `max` =
  the z max-abs; `build=(v)=>toneOps(idx,{zmin:zmid−v, zmax:zmid+v})`. Lower = more contrast.
`SliderField` already does live-drag → `store.set` (preview) + `store.flush` (one undo) and reads the
displayed value from the spec — so a slider drag re-tones the heatmap live and undoably. No re-run.

### §E — Canvas colorbar drag (`components/figure/colorbar-drag.ts`, the flashy surface)
Sibling of `threshold-drag.ts`, gated on `capabilities.heatmapTones`, wired only when a `store` is present
(the styling artboard, not the read-only Figure-data preview):
- Resolve the colour-bar's pixel rect from the rendered DOM (`gd.querySelector(".colorbar")` →
  `getBoundingClientRect`) — more robust than `_fullLayout` internals. Read the bar's value range from
  `gd._fullData[idx].zmin/zmax` (Plotly's computed effective range). Both **guarded**: if either can't be
  resolved the drag never arms (the sliders are the fallback — exactly threshold-drag's degradation).
- Magnet-grab within ≈18 px of the bar. **Top third → `zmax`**, **bottom third → `zmin`**, **middle →
  `zmid`** (shift the diverging centre). Map `clientY` → z value through the bar rect (top = high).
- Live: `store.set(toneOps(idx, patch))` (one checkpoint stashed). Release: `store.flush()` (one undo
  entry). rAF-throttled. Block Plotly's own gesture for the drag (capture-phase mousedown), like the
  other plug-ins; with the global `dragmode:false` there's no box-zoom to fight.
- Wired in `figure-canvas.tsx` `bindGestures` **iff** `model.capabilities.heatmapTones && store && !overlay`.

### §F — Staged half (no code)
`n_genes` / `dendrogram` / `groupby` already render in the Figure-data "Inputs" section
(`visibleParamFields`) and re-run via the pending-changes banner. Confirmed, not rebuilt.

## Requirements
- **R1 — capability.** Declared `tools.heatmapTones` → `model.capabilities.heatmapTones` (declared-only,
  tolerant reader). Backend stamp via `_capabilities.py`; never clobbers an existing stamp; render-inert.
- **R2 — pure re-tone.** `toneOps` sets `zmid`/`zmin`/`zmax`/`colorscale`/`reversescale` on every heatmap
  trace; `readTones`/`zExtent` read current state by trace TYPE. Idempotent, pure.
- **R3 — panel re-tone.** Midpoint + Saturation sliders in the Style "Colour scale" section, live-drag →
  `store.set`/`store.flush`, undoable, no re-run. Shown for any heatmap (inference, like the scale picker).
- **R4 — canvas drag.** `wireColorbarDrag` attached **iff** `capabilities.heatmapTones && store`; drag the
  bar's top/bottom/middle to set zmax/zmin/zmid live; degrades to no-op if the bar rect / range can't be
  read. Never on a non-heatmap or the Figure-data preview.
- **R5 — staged free.** Genes/clustering re-run through the existing Inputs + banner unchanged.
- **R6 — no regression.** Only the heatmap gains a `meta.selom.capabilities` block (golden regen,
  render-inert). Volcano/ERG/all other goldens byte-identical. Non-heatmap figures gain nothing.

## Decisions
- **D1 — re-tone is INSTANT (figure store), not staged.** Colour mapping is cosmetic — it changes pixels,
  not the data — so it belongs on the artboard (JSON-Patch, undoable), like gene labels, not behind a
  re-run. The genes/cluster change (which DOES change the data) stays staged.
- **D2 — panel inference-driven, canvas declared-gated.** The Style panel already infers heatmap controls
  from the spec; the re-tone sliders join it (valid on any heatmap). The capability gates only the canvas
  colorbar-drag (a chart-specific direct-manipulation that should attach only where the skill opts in).
- **D3 — colorbar rect from the DOM, range from `_fullData`.** The rendered `.colorbar` bbox is stabler
  than `_fullLayout` math; `_fullData[idx].zmin/zmax` is Plotly's own effective range. Both guarded.
- **D4 — symmetric Saturation in the panel, independent zmin/zmax on the canvas.** The data model keeps
  zmin/zmax independent (the canvas sets either end); the panel offers a simpler symmetric half-range
  since a row-z-scored diverging heatmap is symmetric. Reversible.
- **D5 — central `_capabilities.py` row (the recipe).** One more profile row; the seam already exists.

## Invariants
- Stamping `heatmapTones` changes **zero rendered pixels** (render-inert `meta`); it only enables editor
  affordances. The heatmap's z/colorscale are unchanged until a tone actually moves.
- `toneOps` is pure; applying the figure's current tones is a no-op (idempotent).
- One read surface: editor/canvas/Style read `FigureModel`, never `meta.selom` directly.
- A re-tone never re-runs; only the Figure-data Inputs (genes/cluster) re-run.

## Error behavior
- Malformed/partial `capabilities` → ignored field-by-field (tolerant reader); never throws.
- A heatmap with an unreadable colour-bar rect or no computed range → the canvas drag doesn't arm; the
  panel sliders still work (they read `readTones`/`zExtent` from the spec).
- `zExtent` null (no finite z) → sliders fall back to a default ±3 range; no crash.

## Testing strategy
- **FE unit (`lib/heatmap/colorscale.test.ts`):** `zExtent` over a known matrix; `readTones` defaults
  (zmid→0, zmin/zmax→extent) + reads explicit values; `toneOps` emits the right leafs for N heatmap
  traces and round-trips via `applyPatches`; identifies the trace by type not order; idempotent.
- **FE unit (resolver):** `heatmapTones` declared → true; absent → false; tolerant of garbage.
- **BE (`test_capabilities` / golden):** `_capabilities.stamp("heatmap")` adds the block; no-op for a
  non-profiled skill; never clobbers a richer stamp. Heatmap golden regen (render-inert); others identical.
- **Live (real data — a DEG/marker heatmap):** slider drag re-tones live + undoable; colorbar drag
  top/bottom/middle sets zmax/zmin/zmid live; genes/cluster re-run via the banner; a volcano/UMAP gets no
  colorbar drag; global gesture flip intact. Full-app smoke (WebGL behind `dynamic(ssr:false)`).

## Build plan (slices)
1. **Capability + stamp (FE+BE).** Resolver `heatmapTones`; `_capabilities.py` heatmap profile; heatmap
   golden regen; BE stamp test + FE resolver test.
2. **Pure transform (FE).** `lib/heatmap/colorscale.ts` (`zExtent`/`readTones`/`toneOps`/`clampToExtent`)
   + unit tests. *(no UI yet)*
3. **Panel re-tone (FE).** Midpoint + Saturation sliders in `style-panel.tsx` "Colour scale".
4. **Canvas colorbar drag (FE).** `colorbar-drag.ts` (DOM rect + magnet + top/bottom/middle + rAF +
   store set/flush); canvas gate on `heatmapTones && store`.
5. **Verify + ratchet.** FE gates + BE focused + golden regen + ruff; one live browser pass on real data
   (re-tone slider + colorbar drag + genes/cluster re-run + the regression checks); full-app smoke. Update
   `CURRENT.md` + `memory selom-figure-edit-ux-pattern`; commit (BE/FE/docs).

## Out of scope (this pass)
- Column (sample) reordering / 2-D clustering UI; per-axis dendrogram toggles beyond the existing `row`.
- Drag-to-reorder rows on the canvas (a staged recompute; the clustering param already covers ordering).
- Custom (non-named) colorscale stop editing; per-stop colour pickers.
- Any change to the heatmap data math (z-score, marker ranking, top-variance selection).

## References (exact integration points)
- `app/frontend/lib/figure-model.ts` — `resolveContract` (§A), `SelomCapabilities.tools`,
  `FigureModel.capabilities.heatmapTones`.
- `app/frontend/lib/heatmap/colorscale.ts` (new, §C) — sibling of `lib/volcano/thresholds.ts`.
- `app/frontend/components/figure/panels/style-panel.tsx` — `ColorscaleControls` re-tone sliders (§D).
- `app/frontend/components/figure/colorbar-drag.ts` (new, §E) — sibling of `threshold-drag.ts`.
- `app/frontend/components/figure/figure-canvas.tsx` — the `wireColorbarDrag` gate (§E).
- `app/backend/skills/_capabilities.py` — the heatmap profile (§B) + `skills/theme.py::apply`.
- `app/backend/skills/heatmap/{run,run_real}.py` — the trace shape the transform reads.
- `docs/figure-data-capabilities/generalization-spec.md` ("Extending to a new chart kind" recipe) ·
  `memory selom-figure-edit-ux-pattern` (the canonical UX model).
</content>
</invoke>
