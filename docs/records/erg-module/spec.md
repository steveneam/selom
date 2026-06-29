# Spec — ERG analysis module + generic trace-grid figure primitive

Status: **approved; Phase 1 built + validated** (2026-06-22). Author: Claude (Opus 4.8).
Owner: Steven Eamegdool. Driving deadline: Gene Therapy revision due **12 Aug 2026**.

## What

Build a reusable **trace-grid / small-multiples figure primitive** (a grid of floating
line panels — `rows × cols`, per-panel axes hidden, one shared scale bar, row/column
labels) and, on top of it, a **Selom ERG analysis module**: layered ingest of
electroretinogram data (legacy wide CSV → LabScribe `.txt` → raw `.iwxdata`), a canonical
star-schema set of tables, an analysis engine (a/b-wave, intensity-response, principled
representative selection), and figure skills. **Phase 1** produces the figure a reviewer
asked for — representative scotopic ERG traces for the 6 conditions of **Figure 1E**
(7 flash intensities stacked vertically × 6 conditions across), and re-renders the existing
**Figure 2B** with a µV axis label + flash-intensity scale. Later phases add the b-wave bar
(Fig 1E itself), Naka-Rushton intensity-response curves, ISCEV-grade auto-methods, and FE polish.

## Context

### Why this matters
The manuscript *"AAV8-PDE6B with 3'UTR provides durable rescue … in rd10 mouse"* (Eamegdool
et al.) is in revision. **Reviewer 2** (major point 2): *"Please include representative ERG
traces corresponding to the data shown in Figure 1E."* Two minor asks hit the same figure
machinery: **R1** *"Figure 2B: add light intensity scale in the y-axis"* and **R2** *"Figure
2B: add a y-axis label and corresponding units to the representative ERG traces."* A further
R2 minor — *"include individual data points in all quantitative graphs"* — drives the Phase-2
b-wave bar.

The target layout is a grid of **floating ERG waveforms with no per-panel axes** and a single
shared scale bar (≈ `200 µV × 100 ms`) bottom-left — exactly what GraphPad Prism / Excel
cannot produce (faceted axis-less floating traces with a shared scalebar) and what Selom's
editable-figure + auto-methods pipeline is built for. The owner's original Fig 2B was made in
R (`ggplot2 … theme_void() + facet_grid(Group ~ sample)`); this module replaces that ad-hoc
script with a reusable, provenance-tracked skill.

### What exists today (verified)
- **Skill contract** — `app/backend/skills/contract.py`: `SkillSpec` (id, version, title,
  engine, omics, entrypoint, inputs, param_spec, outputs, `origin="commodity"`,
  `omics_type=["transcriptomics"]`, optional `catalog`). A skill is
  `run(data_path, params) -> dict` returning a Plotly `{data, layout}` spec; it may attach
  `figure["table"]`, which `run_skill_with_table` pops **before** `theme.apply` so the rendered
  spec stays pure `{data, layout}`.
- **Multi-panel precedent** — `app/backend/skills/normalization_qc/run.py::qc_panel_spec`:
  shared spec-builder, one sub-panel per item via `xaxis{N}`/`yaxis{N}` with `domain`+`anchor`,
  `showgrid:false`. This is the seed of the generic primitive.
- **Theme** — `app/backend/skills/theme.py`: `apply(spec, skill_id)` does base styling for all,
  figure-type polish dispatched by `_KIND[skill_id]`. `_apply_base` restyles only the *base*
  `xaxis`/`yaxis`, never per-panel `xaxisN` — so a grid of per-panel hidden axes is left intact.
- **Stats table** — `app/backend/skills/_table.py::table(columns, rows, title)`; FE mirror
  `StatsTable` in `app/frontend/lib/skills-api.ts`.
- **Table-contract guard** — `app/backend/tests/test_skill_table_contract.py`: every shipped
  skill must be `native` (attaches `spec["table"]`) ∪ `L3` (`extract.synthesize._SYNTHESIZERS`)
  ∪ `L4_ONLY` (reviewed node-link). `NATIVE` must equal the set whose runner source contains
  `spec["table"]`. A new tableless skill with no synthesizer fails the completeness assertion.
- **Golden tests** — `app/backend/tests/test_skills_golden.py` + `tests/regen_golden.py`:
  stub output is snapshotted and compared byte-for-byte.
- **Methods** — `app/backend/methods.py::build`: per-skill builder `_<skill_id>` else generic;
  returns `{text, citations}`.
- **FE editor** — `app/frontend/lib/figure-spec.ts` (`FigureSpec`, `normalizeSpec`) +
  `app/frontend/hooks/use-figure-store.ts` (`init({figure, table})`) renders any `{figure, table}`.

### Data archaeology (done this session)
- The 6 Fig 1E conditions, at the **1-month** timepoint, map to specific eyes across four ERG
  sessions (Exp 9: 17–18 Sep 2020; Exp 10: 29 Sep & 1 Oct 2020). Each mouse's two eyes carry
  different vectors. **30 candidate eyes** are catalogued in
  `D:\selom-data\erg-fig1e\erg_manifest.csv` (condition, vector, eye, file path, log notes,
  intensity assignment). Counts: Control 8, Untreated 4, AAV8-RK-PDE6B 7, GFP-polyA-stuffer 3,
  CMV-GFP 4, PDE6B-3'UTR 4.
- **`.iwxdata` format (DECODED + VALIDATED this session)**: a ZIP of text headers (`SPEED 5000`,
  `NUM_CH_POINTS 1500`, channel µV) + 60 per-sweep `CH000.dat` binaries. `CH000.dat` =
  **128-byte header + 1500 records × 10 bytes** (each record = an 8-byte **big-endian IEEE
  float64** sample + 2 ignored bytes; 128 + 1500×10 = 15128). **µV = raw × 100.** Sweeps are
  grouped into the 7 intensities by the `SWEEP_INFO` **block-ID** (intensity in the high 16 bits)
  — robust to irregular sweep counts (two eyes had re-acquired intensities). Intensities map to
  **−1.7, −0.8, 0.1, 1.0, 1.9, 2.8, 3.1 log cd·s/m²** (Group1→Group7). Pure-stdlib parser at
  `D:\selom-data\erg-fig1e\iwx_parse.py` (driver `extract_fig1e.py`). **Decode validated by
  trend/shape match to `ERG Data - control.csv`: stacked Pearson r = 0.89** (per-group 0.88–0.96),
  correct b-wave magnitudes and intensity progression — not an exact animal match (owner: the
  sample `.iwxdata` may not be the exact animal behind that CSV).

### Extraction result + the b-wave reconciliation issue (RESOLVED 2026-06-23 — fallback is definitive)
**Resolution (session T5, 2026-06-23):** the R17-*preferred* source — LabScribe operator marks — **does
not exist in this dataset**. `iwx_parse.py::Eye.landmarks` documents (and the decode confirms) that every
`blkN/marks.txt` is header-only and `Views.txt`'s `BEGIN_MARKS..END_MARKS` block is empty: there are **no
operator-placed a/b-wave marks** to read. Fig 1E's bar was therefore not built from embedded marks (it was
measured another way in LabScribe / a separate analysis). So the **R17 smoothed-landmark fallback is the
only available metric, and it is definitive** — the dual-smooth peak-to-trough `_erg.landmarks` (a-wave on a
3 ms trace, b-wave = peak(40–120 ms) − trough(0–40 ms) on a 16 ms trace, measured on the RAW
baseline-corrected trace). It **reproduces Fig 1E's ordering** (`selection_report_v2.csv`, b-wave at log 1.0:
Control ≈ 210 ≫ 3'UTR ≈ 130 > PDE6B ≈ 99 > {Untreated ≈ 43, CMV-GFP ≈ 42, stuffer ≈ 31}), which meets the
owner's relaxed acceptance (O2/R18/R19 — trend/shape, not exact magnitude). The flats read ~30–50 µV
(vs the printed bar ~15–20 µV) because residual broadband noise still floors the metric a little high, but
they read **far** below the real b-waves and the ordering is faithful — selection is no longer noise-driven.
**Selection unblocked.** _Below: the original (pre-fix) symptom, kept for the record._

All 30 eyes decoded. But the **derived b-wave metric** (max over 20–250 ms − baseline) does **not**
reproduce Fig 1E's pattern: conditions that should be flat read far too high (Untreated 254_LE ≈ 146 µV,
CMV-GFP 259_LE ≈ 128 µV, stuffer 249_LE ≈ 88 µV vs Fig 1E bar ≈ 15–20 µV), and Untreated even outranks
the PDE6B treatment — biologically backwards. Conditions with a *real* b-wave reconcile (PDE6B-no-3'UTR
255_RE ≈ 45 µV vs bar ~50; PDE6B-3'UTR 251_RE ≈ 113 µV vs bar ~135). **Diagnosis:** on flat averaged
traces the crude peak-minus-baseline metric is measuring **residual noise**, not a b-wave — caught by
the R19 acceptance check. The **decoded waveforms are sound** (control matched the oracle); only the
derived metric (hence b-wave-based *selection*) is affected. **Fix** (folded into L2 below): measure at
the **operator-placed a/b-wave marks embedded in the `.iwxdata`** (`marks.txt` per sweep + `Views.txt`)
— LabScribe's own landmarks, i.e. the values Fig 1E's bar was built from — with a smoothed-landmark
fallback; then reconcile the extracted b-wave-per-condition against the printed Fig 1E bar before
finalising representatives. Also surface honestly whether rd10-untreated genuinely retains partial rod
function at this timepoint (~P40) vs the metric over-reading.

### Locked scope decisions (owner, this session)
1. Build a **generic** no-axes floating small-multiples trace-grid primitive; ERG is its first
   consumer (reusable for EEG/ECG/patch-clamp / any time-series-by-`condition × parameter`).
2. Deliver **one phased design+spec**; Phase 1 = the ERG trace-grid skill that answers the reviewer.
3. **Single representative trace per condition** (not group mean), chosen by a principled,
   stated rule (below). Owner confirmed.
4. **Untreated** = saline *or* uninjected Rd10 (both null) — pick the cleanest flat trace.

## Requirements

### Generic trace-grid primitive (`skills/_tracegrid.py`)
- R1. Given an ordered list of panels each addressed by `(row, col)` with `{x: [...], y: [...]}`
  plus `nrows`, `ncols`, render a Plotly `{data, layout}` where each panel is one `scatter`
  `mode:"lines"` trace bound to its own `xaxis{N}`/`yaxis{N}` placed by `domain`+`anchor`.
- R2. All per-panel axes are hidden (`visible:false`): no ticks, lines, labels, or grid.
- R3. A **single shared scale bar** is drawn once (Plotly `shapes` + `annotations`, `xref/yref:"paper"`),
  configurable as `{x_len, x_unit, y_len, y_unit}` (default `100 ms × 200 µV`), default position
  bottom-left. It encodes both axes for the whole grid.
- R4. **Shared scaling**: every panel uses an identical y-range and x-range (computed across all
  panels unless explicitly supplied), so trace heights are comparable across the grid — the scale
  bar is meaningful.
- R5. **Row labels** (right side) and **column labels** (top) drawn as paper-ref annotations.
- R6. Per-panel line `color` overridable; a `color_by` ∈ {`row`, `col`, `none`} maps a palette.
- R7. Configurable `row_gap`, `col_gap`, baseline at `y=0` (optional faint zero line per panel: off by default).
- R8. Output is a pure, fully-editable `{data, layout}` (no numpy; route arrays through
  `skills/_plotly.py::jsonable`).

### ERG ingest (L0, layered)
- R9. **L0a (wide CSV)** — read the legacy R format `Time (ms),Group1..Group7` (µV, one file per
  condition) → long records. This is the proven floor; it works without any binary decode.
- R10. **L0b (LabScribe `.txt`)** — read the iWorx ERG `.txt` export (waveform-over-time and/or the
  "ERG Calculations" b-wave summary).
- R11. **L0c (`.iwxdata` native)** — decode the ZIP: parse `acq_setting.txt` for `SPEED`,
  `NUM_CH_POINTS`, channel µV scaling; decode each `CH000.dat`; group sweeps into the 7 intensities;
  average within intensity; baseline-correct (subtract pre-stimulus mean) → 7 traces × `NUM_CH_POINTS`
  samples + a `time_ms` axis. Pure stdlib (`zipfile`, `struct`). **Acceptance: trend/shape match to
  the control CSV oracle**, not exact identity.

### Canonical tables (L1, star schema, join on `sample_id`)
- R12. `erg_manifest.csv` — one row per eye/session (sample sheet + extraction index). **Pre-built.**
  Pipeline fills `decode_status`, `b_wave_max_uv`, `dev_from_group_mean`, and flips one `role`
  per condition to `representative`.
- R13. `erg_metrics_long` — `(sample_id, condition, animal, eye, intensity_group,
  intensity_log_cd_s_m2, b_wave_uv, a_wave_uv, b_wave_implicit_ms, a_wave_implicit_ms)`.
- R14. `erg_waveforms_long` — `(sample_id, condition, condition_order, intensity_group,
  intensity_log_cd_s_m2, time_ms, voltage_uv, role)`. Tidy; baseline-corrected µV; the trace-grid
  skill's canonical input.
- R15. A pivot view to the legacy wide `Time, Group1..7` per condition must be derivable (round-trip
  compatibility with the owner's existing files).

### ERG analysis engine (L2)
- R16. **Baseline correction**: subtract the mean of the pre-stimulus window (samples before t=0 /
  first ~5 ms) so each trace sits at 0 µV pre-flash.
- R17. **a/b-wave amplitudes** — preferred source = the **operator-placed marks** in the `.iwxdata`
  (`marks.txt` per sweep / `Views.txt`): LabScribe's own a/b-wave landmarks, matching the paper's Fig 1E
  bar. Fallback (wide-CSV / unmarked) = a *smoothed-landmark* estimate: a-wave = baseline − trough(0–40 ms);
  b-wave = trough → peak in a constrained window (~40–120 ms), measured on a low-pass-filtered trace, NOT a
  raw max over a wide window (which reads noise — see the reconciliation issue above). Record amplitudes (µV)
  and implicit times (ms). Reconcile the b-wave-per-condition against Fig 1E's printed values before use.
- R18. **Representative selection** (the integrity-critical rule): for each condition, select the eye
  whose **full b-wave-vs-intensity curve** is closest to the group mean by minimum sum-of-squared
  deviations (robust + trend-faithful); break ties by lowest pre-stimulus noise. Deterministic;
  QC-flagged eyes (cataract/failed-decode) excluded from both the mean and selection. The criterion is
  recorded and surfaced (not cherry-picked-to-hypothesis). **Pinning the exact Fig 1E stimulation point is
  NOT required** (owner 2026-06-22: the traces need only reflect Fig 1E's trend/pattern); a single
  reference intensity may still be reported for the caption, but it does not gate selection.
- R19. **Biology acceptance check** (asserted, not silent): the rendered representatives reflect Fig 1E's
  **trend/pattern** — `Control ≫ PDE6B-3'UTR (rescue) > PDE6B-no-3'UTR (partial) > Untreated ≈ stuffer ≈
  CMV-GFP (flat)`. **Exact magnitude/intensity reconciliation to the printed bar is NOT required** (owner);
  the check is the *ordering/shape*. *(The first crude metric failed even the trend — flat conditions
  over-read noise so untreated wrongly outranked treated; the fix R17 makes flats read flat.)* If the
  PDE6B-no-3'UTR representative is dead flat, investigate failed-injection eyes dragging its group mean.
- R20. **Naka-Rushton fit** (Phase 2): `V/Vmax = I^n / (I^n + K^n)`; report Vmax, K (log cd·s/m²), n.

### ERG figure skills (L3)
- R21. **`erg_traces`** (Phase 1, native): input = `erg_waveforms_long` (filtered to representatives
  by default; `role` selectable). Emits the trace-grid: **rows = 7 intensities** (top = dimmest
  Group1 → bottom = brightest Group7, matching the existing figure), **cols = conditions** in Fig 1E
  order, per-condition colors, shared `200 µV × 100 ms` scale bar bottom-left, intensity labels right,
  condition labels top. Attaches `spec["table"]` = the b-wave/a-wave metrics for the displayed
  representatives (→ native). Also serves Fig 2B (3-condition subset) with the axis label/scale satisfied
  by the scale bar + labels.
- R22. **`erg_bwave_bar`** (Phase 2): peak scotopic b-wave at one intensity per condition, bar + SEM +
  **individual data points** (reviewer ask). May reuse/extend the existing bar/boxplot skill.
- R23. **`erg_intensity_response`** (Phase 2): b-wave-vs-log-intensity curves per condition with
  Naka-Rushton fit overlaid.

### Methods + provenance (L4) and FE (L5)
- R24. `methods._erg_traces` (Phase 2): ISCEV-style prose — instrument (Phoenix Micron/Celeris +
  LabScribe iWorx IWX), 7 scotopic intensities (list the log cd·s/m² ladder), sweeps/intensity,
  baseline correction, b-wave definition, **representative-selection criterion stated**, n per group;
  with citations.
- R25. **Honesty invariant**: any displayed trace is captioned for what it is — "representative
  (eye nearest group mean, n=…)" — never a group mean mislabelled "representative", never a trace
  cherry-picked to flatter the hypothesis.
- R26. FE (Phase 3): the figure renders + is editable via `use-figure-store.init({figure, table})`;
  scale bar, row/col labels, and colors are all editable layout/shape/annotation properties.

## Design

### Components & data flow
```
.iwxdata / .txt / wide-CSV
        │  L0 ingest (layered)
        ▼
erg_manifest ──┐
erg_metrics_long  │  L1 canonical tables (join on sample_id)
erg_waveforms_long┘
        │  L2 engine: baseline · a/b-wave · selection · (NR fit)
        ▼
representative waveforms + metrics
        │  L3 skills call the primitive
        ▼
_tracegrid.grid_spec(...) ── erg_traces ─┐
                                          ├─ themed {data,layout}(+table) → API → FE editor
erg_bwave_bar · erg_intensity_response ──┘
        │  L4 methods.build → {text, citations}
```

### The generic primitive — `app/backend/skills/_tracegrid.py`
A shared spec-builder (sibling of `_table.py`/`_plotly.py`), **not** a skill. Signature sketch:
```python
def grid_spec(panels, *, nrows, ncols, scalebar=None, row_labels=None, col_labels=None,
              colors=None, share_y=True, share_x=True, row_gap=0.012, col_gap=0.012,
              title=None) -> dict: ...
# panels: [{"row": int, "col": int, "x": [...], "y": [...], "color": str|None, "name": str|None}, ...]
# returns pure {"data":[...], "layout":{...}} with hidden per-panel axes, one scalebar, labels.
```
Justification for a new pattern (vs cloning `qc_panel_spec`): the no-axes + shared-scalebar +
2-D `(row,col)` placement + shared-range is a distinct, reusable shape; centralizing it keeps every
future trace-grid skill consistent and lets the FE rely on one structure. `qc_panel_spec` stays as-is
(1-D, axis-titled) — this is the 2-D axis-less generalization.

### Theme
Add `_KIND["erg_traces"] = "trace_grid"` and a `_style_trace_grid(st, spec)` that applies base
font/colorway/title only, asserts all `xaxis*`/`yaxis*` stay `visible:false`, and styles the scale
bar line + annotation fonts. Per-panel axes are not otherwise touched (base already skips `xaxisN`).

### Skills (clone `skills/normalization_qc/`)
Each ERG skill dir: `skill.json` + `run.py` (deterministic stub) [+ `run_real.py` if a heavy path].
`erg_traces` stub renders a small synthetic grid (shape-faithful) for golden tests; the real path
reads `erg_waveforms_long` (a CSV `data_path`) and calls `grid_spec`. `origin="proprietary"`
(the editable axis-less ERG grid is Selom-original output; cf. `docs/proprietary-skills.md`),
`omics_type=["general"]` (cross-domain electrophysiology, not transcriptomics).

### File changes
**Phase 1**
- `app/backend/skills/_tracegrid.py` (new primitive)
- `app/backend/skills/erg_traces/{skill.json,run.py,run_real.py}` (new skill)
- `app/backend/skills/_ingest/iwx.py` (port the validated `iwx_parse.py`); CSV/long readers
- `app/backend/skills/theme.py` (+`trace_grid` kind)
- `app/backend/tests/test_skill_table_contract.py` (add `erg_traces` to `NATIVE`)
- `app/backend/tests/test_skills_golden.py` (+`erg_traces`) + `tests/golden/erg_traces.json`
- `app/backend/tests/test_tracegrid.py` (primitive unit tests)
- Data (not repo): the filled `erg_*_long.csv` + `rep_*.csv` under `D:\selom-data\erg-fig1e\`
**Phase 2**: `erg_bwave_bar/`, `erg_intensity_response/`, `methods._erg_traces` + citations.
**Phase 3**: FE wiring/polish, provenance/honesty surface, golden + table-contract registration finalised.

## Decisions

- **D1 — Generic primitive first.** Chosen (owner-locked). Alt: ERG-specific. Why: compounds across
  instruments/papers; the axis-less small-multiples shape is broadly reusable. Reversible: yes (could
  inline later), but the seam is cheap now.
- **D2 — Single representative, min-SSD-to-group-mean.** Chosen (owner-locked single rep + integrity).
  Alts: group-mean waveform (rejected — owner wants single; though it remains a selectable `role`);
  cherry-pick best (rejected — reviewer is already pushing on overstatement). Why: defensible, stated,
  reproducible. Reversible: yes (it's a selection param).
- **D3 — `erg_traces` is native (attaches a metrics table).** Alt: L3 synthesizer or L4-only. Why: the
  b-wave/a-wave per condition×intensity is a real, faithful table; native keeps the figure honest and
  satisfies the contract guard. Reversible: yes, but native is correct here.
- **D4 — Layered ingest, wide-CSV floor + `.iwxdata` native.** Why: the wide CSV is proven and
  unblocks immediately; native `.iwxdata` is the moat and is required for *single-representative*
  (per-animal) data, which the group-averaged CSVs don't carry. Reversible: yes (drop a layer).
- **D5 — Row order top→bottom = dim→bright (Group1→Group7).** Matches the owner's existing Fig 2B/PDF.
  Reversible: yes (a param).
- **D6 — Primitive lives in `skills/_tracegrid.py` (shared infra), not a skill.** Mirrors
  `_table.py`/`_plotly.py`. Reversible: yes.
- **D7 — b-wave source = operator marks first, smoothed landmark fallback.** Chosen because the
  `.iwxdata` carries LabScribe's own a/b-wave marks (the values Fig 1E was built from) and the crude
  peak-minus-baseline metric demonstrably over-reads noise on flat traces. Alt: re-derive everything
  with a peak finder (rejected — reproduces the noise problem; not anchored to the paper). Reversible:
  yes (the fallback path stays for unmarked inputs).
- **D8 — Open-core: this module is proprietary IP** (owner-affirmed 2026-06-22). The native
  `.iwxdata` decoder, the `_tracegrid` primitive, and the `erg_traces` skill are genuine
  Selom-original IP — `erg_traces` ships under `skills/proprietary/` with `origin="proprietary"`
  (cf. `docs/proprietary-skills.md`). The moat is raw-instrument-file ingest + the editable
  axis-less figure + provenance, not the line-drawing. The primitive itself stays general (shared
  infra) so other domains reuse it; ERG-specific value is proprietary.
- **O1 — RESOLVED (session T5, 2026-06-23):** there are **no operator marks** to reconcile against (the
  marks-based path R17-preferred does not exist — `marks.txt` header-only, `Views.txt` marks empty), so the
  smoothed-landmark fallback is the metric. On the smoothed metric the flat conditions read ~30–50 µV vs
  Control ≈ 210 and 3'UTR ≈ 130 — i.e. mostly residual noise floor, **not** a retained rod b-wave: rd10 is
  effectively flat at ~P40, consistent with the biology. The small residual (flats at ~30–50 not ~0) is the
  display/metric noise floor, addressed cosmetically by display smoothing (see the smoothing decision,
  handoff point 3), **not** a real partial response. Caption the flats honestly as no/negligible response.
- **O2 — RESOLVED (owner 2026-06-22):** Fig 1E's bar = one stimulation point (my first pass wrongly keyed
  on Group7), BUT the figure need only **reflect Fig 1E's trend/pattern** — exact intensity-point and
  magnitude matching are NOT required. So: keep the metric fix (R17) so flat conditions read flat and
  selection isn't noise-driven; select by full-curve closest-to-group-mean (R18). Backing out the exact
  reference intensity is now optional (caption nicety), not a gate.
- **Assumption A1 (RESOLVED):** the `.iwxdata` decode succeeded and is validated (r = 0.89). The
  LabScribe-export fallback (L0a/L0b) remains specified for inputs without raw files.
- **Assumption A2:** Fig 1E condition order = legend order (Control, Untreated, AAV8-RK-PDE6B,
  GFP-polyA-stuffer, CMV-GFP, PDE6B-3'UTR). Encoded as `condition_order` in the manifest.

## Versions
- **Python** backend pinned 3.12 (uv); **Plotly** as already vendored by Selom skills (no new dep).
- **`.iwxdata` parser**: pure stdlib (`zipfile`, `struct`, `array`) — **no new dependency**.
- **Naka-Rushton fit** (Phase 2): prefer `scipy.optimize.curve_fit` *if scipy is already in the
  backend env* (verify at build); else a numpy least-squares fallback. No new heavy dep introduced
  for Phase 1.

## Invariants
- The spec the FE renders is pure `{data, layout}` — `spec["table"]` is popped in
  `run_skill_with_table` before theming (do not break this).
- All per-panel axes in a trace grid stay `visible:false`; the scale bar is the only axis cue.
- Table-contract guard stays green: `erg_traces` ∈ `NATIVE` **and** its runner attaches `spec["table"]`
  (both, or `test_native_classification_matches_source` fails).
- Golden determinism: the stub output is fixed; no `Date.now`/RNG in skill code.
- Honesty (R25): displayed trace label states representative-vs-mean and the selection criterion.

## Error Behavior
- **Decode failure / corrupt `.iwxdata`** → `decode_status="fail"` in manifest; eye excluded from
  selection; logged. Never silently substituted.
- **Condition with no usable eye** (all flat *and* all QC-failed) → emit the panel column with an
  honest empty/flat trace + a note; do not fabricate.
- **Missing input columns** in the long CSV → skill raises a clear `ValueError` naming the column.
- **Mismatched panel/row/col counts** in the primitive → `ValueError` (no partial grid).

## Testing Strategy
- **Primitive unit tests** (`test_tracegrid.py`): N panels → N traces each on its own `xaxisN/yaxisN`;
  all axes `visible:false`; exactly one scale bar; shared y-range across panels; correct row/col labels.
- **Decode oracle** *(PASSED, r = 0.89)*: averaging C57 control sweeps reproduces the *shape/amplitude
  trend* of `ERG Data - control.csv` (large positive b-wave at bright intensity, small at dim) — not
  exact identity. Keep as a regression guard.
- **trend check** *(gate, relaxed per owner)*: the rendered representatives reproduce Fig 1E's
  **ordering/pattern** (Control ≫ 3'UTR > PDE6B > flats) — exact magnitude/intensity match to the printed
  bar is NOT required. The marks-based metric (R17) must at least make the flat conditions read flat.
- **Biology acceptance check** (R19) on the extracted metrics.
- **Golden test** for `erg_traces` stub (byte-stable) via `regen_golden.py`.
- **Table-contract guard** passes with `erg_traces` added to `NATIVE`.
- **Dogfood**: the produced Fig 1E figure visually matches the target layout (the supplied example)
  and Fig 2B re-renders with the scale/label asks satisfied.

## Out of Scope
- OPs analysis, OCT, optomotor, IHC figures.
  **Photopic flash *decode + trace figure* + the cone a/b-wave *metric* are now IN scope** (generic
  protocol registry T14; cone landmark windows T15 below). Only the calibrated photopic energy
  ladder (cd·s/m² per group, from the lab's calibration sheet) remains pending — see T14's blank.
- Auto-fetching/streaming `.iwxdata` from the network share (manual paths via the manifest for now).
- A general LabScribe-format library beyond what ERG ingest needs.
- FE drag-to-recolor UX beyond the existing editor's layout/shape editing (Phase 3 uses what exists).
- Phase 2/3 detail beyond interfaces named here (separate slices once Phase 1 lands).

## Phase 1 build log (2026-06-22 — built + validated)
- `app/backend/skills/_tracegrid.py` — generic axis-less small-multiples primitive; 8/8 unit tests (`tests/test_tracegrid.py`).
- `app/backend/skills/proprietary/erg_traces/` — `skill.json` (proprietary, `origin:"proprietary"`), `run.py` (dependency-free stub) + `run_real.py` (reads `erg_waveforms_long`, cleans, attaches an a/b-wave table). Golden `tests/golden/erg_traces.json`; registered in the golden lists + the `NATIVE`/`STUB_NATIVE` table-contract sets. `theme._style_trace_grid` keeps every per-panel axis hidden.
- `app/backend/skills/_erg.py` — domain constants + `clean_trace` ("clean flats, keep OPs": FFT-notch 50/100/150/163 Hz + 300 Hz low-pass) + `landmarks` (validated dual-smooth, aligned to `iwx_parse.Eye.landmarks`: b-wave = peak(40–120 ms) − trough(0–40 ms) on a heavy 16 ms trace, measured on the RAW baseline-corrected trace).
- **Verified:** 79 backend tests pass (primitive + 30 goldens + contract guard). Real path on the actual representatives → 42 hidden-axis panels + shared scale bar + a/b-wave table; trend reproduced via Selom's own pipeline at log 1.0: Control 211 ≫ 3'UTR 131 > PDE6B 92 > {Untreated 43, stuffer 32, CMV-GFP 43}.
- **Reference data** (`D:\selom-data\erg-fig1e\`): reps Control 633_LE · Untreated 255_LE · PDE6B 256_RE · stuffer 248_LE · CMV-GFP 257_LE · 3'UTR 257_RE; `erg_metrics_long.csv`, `erg_waveforms_long.csv`, `fig1e_preview.png`.
- **Pending:** render the editable figure in the Selom FE + publication export; Phase 2 (b-wave bar with individual points, Naka-Rushton intensity-response, ISCEV methods text).

## T14 — protocol-generic `.iwxdata` (group-count blocker solved; photopic decodes) — 2026-06-24
Owner steer: *"different labs/people have different group counts & intensities — take whatever's
there and fill in the blanks for the values/labels."* So `skills/_iwx.py` no longer hard-rejects
non-7-group files; the **intensity-group count is read from the file** (the SWEEP_INFO block-ID
index — 7 scotopic, 5 photopic, any N) and a small **protocol registry** (`Protocol` /
`resolve_protocol`, filename-hinted) fills the calibration blanks: known protocol → its cd·s/m²
ladder + adaptation; unknown → ordinal `GroupN` labels + intensity `None` (honest, never fabricated).
- **D9 — Decode is file-driven; calibration is a registry, not a hardcode.** The file is
  self-describing about group *count/order* but NOT calibrated energy (the device `flash_param`
  repeats across ND-filter steps — scotopic Group1–4 all read 0.7), so cd·s/m² must come from lab
  calibration. Merge-to-target stays for the validated scotopic path (target from the protocol, not
  the constant `7`); unknown protocols pass through untouched. Reversible: yes (registry-only).
- **D10 — iWorx now emits `stimulus_type`** (`scotopic_flash`/`photopic_flash`/"") matching the
  Diagnosys vocabulary, so a combined scotopic+photopic cohort filters to one mode via the existing
  `_erg.resolve_flash_mode` instead of colliding on shared `GroupN` row labels. Scotopic output stays
  byte-identical (title `Representative scotopic ERG`, 7 traces).
- **D11 — Group count is fully dynamic, even under a name hint.** Only obviously-aborted SHORT runs
  (< 3 sweeps duplicating a sibling's flash param) ever fold; FULL groups are never force-collapsed to
  a protocol's expected count. So a *different lab's* 10- or 12-intensity "Scotopic"-named file decodes
  to 10/12, not the CMRI 7. Safe because a real-data scan (28 files) found **every** scotopic at exactly
  7 `[10,10,10,10,10,5,5]` and photopic at 5 `[10,10,10,5,5]` — the fold never fires on the owner's data
  (the block-ID index already absorbs re-acquisitions). Verified at counts 3/5/7/10/12, named + unnamed.
- **Verified on real CMRI data** (`…/13. 1 Dec 2020_Experiment 11/Rd10#288_LE Photopic UV.iwxdata`):
  decodes to 5 groups → `Representative photopic ERG` 5-row grid, intensity honestly unknown;
  combined scotopic(7)+photopic(5) cohort renders 7 *or* 5 rows by `adaptation`, never 12. Tests:
  `tests/test_iwx.py` (photopic-generic / scotopic-calibrated / unknown-count) + 185 ERG-family green.
- **THE ONE PENDING BLANK:** the **5 photopic intensities (cd·s/m² + labels)** from the lab's
  photopic calibration sheet — not in the file. Register on `PHOTOPIC.log_energies` in `_iwx.py` and
  photopic rows light up with real intensities automatically. Until then they read `Group1…5`.

## T15 — photopic/cone a/b-wave metric (landmark windows) — 2026-06-24
The photopic FLASH figure decoded + rendered (T14), but the a/b-wave *metric* (`_erg.landmarks`,
used by `erg_bwave_bar` + `erg_intensity_response` + `erg_traces` when measuring **from** waveforms)
used the SCOTOPIC search windows. Cone responses differ, so `landmarks` gained a `mode`
(scotopic | photopic) selecting a timing preset, chosen per segment from `stimulus_type`
(`metrics_from_waveforms`) and per skill from `adaptation` (`_erg.adaptation_mode`).
- **D12 — the cone windows are anchored to the published mouse cone-ERG timing (not just the raw data).**
  The cone a-wave is small and EARLY, so **a-window (0–25 ms)** isolates it (the scotopic 0–40 ms
  window under heavy smoothing wrongly latched a ~27 ms noise dip as the a-wave); literature anchor =
  Lyubarsky 1999 (~14 ms). The cone b-wave peaks ~40–45 ms (range ~40–75 ms; Bush 2019 IOVS, WT
  ~44 ms), FASTER than the rod b-wave, so **b-window (12–80 ms)**, centred on the cone range.
  **Smoothing stays heavy (3/16 ms = scotopic)**: the cone-is-narrow intuition was false here, and the
  16 ms b-smooth nulls the 20 ms-period ~50 Hz mains hum these recordings carry (a lighter kernel
  over-reads the b-wave). Default/unknown mode → scotopic, so every existing µV figure stays
  **byte-identical** (goldens not regenerated).
- **D13 — per-segment, not per-figure.** `metrics_from_waveforms` reads each segment's own
  `stimulus_type` (and adds it to the grouping keys so the two modes' shared `GroupN` labels never
  merge), so a mixed scotopic+photopic cohort measures each mode with the right windows; the skill's
  `adaptation` hint is only the *default* for a plain waveform CSV with no `stimulus_type` column.
- **D14 — look-at-data was necessary but NOT sufficient; the literature corrected it.** An early
  data-only tuning saw a dominant peak at rd10 57 ms / C57 **104 ms** in the real `.iwxdata` and
  widened the b-window to 15–130 ms to "not truncate the late cone b-wave." A web/literature backfill
  (owner-requested) then showed that is the WRONG read: a mouse *photopic* b-wave near 100 ms is the
  signature of the dim-flash **rod** b-wave (Saszik 2002, ~110 ms) / incomplete light-adaptation / the
  ~50 Hz hum — **not** a cone b-wave (which is ~44 ms). A 130 ms window CHASES that artifact. So the
  window was narrowed back to the cone range (12–80 ms): the metric now reports a cone-range value
  (C57 brightest 43.8 µV, hitting the 80 ms edge = an honest "no clear cone b-wave here, review this"
  signal) instead of the 156 µV / 104 ms artifact the wide window had reported. **Lesson: tune on the
  data AND check the value against the domain's published norms — the dominant peak is not always the
  feature you're measuring.** ([[figure-repro-match-numbers-exactly]], [[compound-capability-each-task]].)
- **The honest conclusion → the manual override is the real fix.** On hum-heavy single-eye iWorx
  photopic recordings the auto-windowed metric is only a SEED; the rigorous path (field-standard:
  Espion auto-peak + "manually adjusted if necessary"; ISCEV a=baseline→trough, b=a-trough→b-peak;
  ERGAssist hybrid auto-seed+manual-adjust) is to let the scientist place/adjust the a/b/N1-P1 markers
  and measure at those points, with a provenance log of auto-vs-moved. **Owner-requested; build next**
  (see CURRENT.md NEXT) — extends the M3 `_tracegrid` overlay to draggable marker dots consumed by the
  bar + intensity-response.
- **Flicker needs no window change** — 30 Hz flicker intrinsically isolates cones and is measured as
  N1→P1 (device markers preferred; phase-folded fallback), never the flash a/b windows. Re-confirmed
  on real `453_AAV.TXT`: 10 Hz 19.96 µV / 30 Hz 7.08 µV (device).
- **Verified on REAL data:** Rd10#288 photopic a-wave now timed at **7 ms** (the early cone a-wave)
  vs scotopic's wrong 27 ms; the cone b-window reports cone-range b-waves (rd10 49.8 µV @ 56.8 ms; C57
  43.8 µV at the 80 ms edge) instead of the 100+ ms rod/hum artifact; the real photopic feed
  (`stimulus_type=photopic_flash`) auto-selects cone windows even at the scotopic default. Diagnosys
  `453_AAV.TXT` photopic-flash from-traces path runs end-to-end (`Photopic b-wave by condition`).
  Tests: `tests/test_erg_units.py` (+4: cone-window timing, `adaptation_mode`, per-segment mode,
  end-to-end bar); 165 ERG-family green; ruff clean; goldens unchanged.
- **Still pending / honest limits:** these iWorx photopic recordings are hum-heavy and single-eye, so
  the from-traces cone metric is necessarily approximate (→ the manual override above). The **device
  markers stay authoritative** when a metrics table is supplied (D2). The calibrated photopic energy
  ladder (T14 blank) is still unregistered, so photopic intensity-response x-labels read `Group1…5`.
