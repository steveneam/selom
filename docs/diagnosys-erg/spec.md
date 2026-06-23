# Spec — Diagnosys / Celeris ERG skill (tri-modal: scotopic · photopic · flicker)

Status: **DRAFT — awaiting owner approval** (no code until approved). Author: Claude (Opus 4.8), 2026-06-23.
Sibling of `docs/erg-module/spec.md` (the iWorx `.iwxdata` ERG module). Extends it; does not replace it.

## What

Add a second native ERG vendor path to the Selom ERG module: ingest a **raw Diagnosys Espion /
Celeris export** (the full tab-delimited multi-table `.TXT`, or the reduced comma `.CSV`) and emit
publication figures for **all three standard rodent ERG modes — scotopic (dark-adapted intensity
series), photopic (light-adapted single flash), and flicker** — as editable Selom figures with
paste-ready methods. The export holds several side-by-side tables in one file: chiefly a **Marker
Table** (the device's own a-/b-/c-wave amplitudes in µV + implicit times in ms, per step × eye) and a
**Data Table** (raw waveforms in nV); the full export adds a **Stimulus Table** that names each
step's adaptation state, intensity (cd·s/m²), and flicker frequency, and a **Contents Table** giving
exact sub-table bounds. A new parser maps these onto Selom's existing canonical ERG tables, so the
**existing scotopic skills (`erg_traces`, `erg_intensity_response`, `erg_bwave_bar`) run unchanged**;
the only genuinely new build is the **flicker output** (a periodic response needs a different graph
than the flash trace grid) and the parser itself. This effectively subsumes the parked C7 "photopic
`.iwxdata` path" optional, on cleaner data with all three modes present.

## Context

### Why this matters
- **Greenfield.** No no-code tool ingests a raw vendor ERG export and emits scotopic + photopic +
  flicker editable figures. Diagnosys Espion/Celeris is the dominant rodent-ERG instrument; its CSV
  export is widely produced and poorly served by general tools (GraphPad/Excel can't do faceted
  axis-less traces; the device's own software is not a figure editor).
- **Compounds, not a one-off** ([[compound-capability-each-task]]). ~half the machinery already
  exists and is reused verbatim: the `_tracegrid` primitive, the three ERG skills, `_erg.py`
  (Naka-Rushton, landmarks, summary stats), the publication theme, and the canonical table schema.
  The new parser is a sibling of the validated `_iwx.py`. The flicker skill is the one new figure.
- **Better lab for photopic + flicker than the owner's own data.** The owner's iWorx `.iwxdata` path
  currently *errors honestly* on a photopic file (`_iwx.load_eye` raises when grouping ≠ 7 scotopic
  intensities — `docs/erg-module/spec.md` Out of Scope). The Diagnosys export carries the device's
  own markers and a clean two-table structure, so it is the better place to build and validate the
  photopic + flicker handling; the iWorx photopic path can later inherit the same logic.

### What exists today (verified this session)
- **ERG module (`docs/erg-module/spec.md`, built + validated 2026-06-22):**
  - `app/backend/skills/_tracegrid.py` — generic axis-less small-multiples primitive (`grid_spec`).
  - `app/backend/skills/_erg.py` — `clean_trace`, `landmarks` (dual-smooth a/b detection), `naka_rushton` + `naka_rushton_fit`, `summary_stats`, condition order/colors.
  - `app/backend/skills/_iwx.py` — pure-stdlib iWorx `.iwxdata` decoder → `erg_waveforms_long` rows; **the pattern this parser mirrors.**
  - `app/backend/skills/proprietary/erg_traces|erg_bwave_bar|erg_intensity_response/` — each `skill.json` + `run.py` (stub) + `run_real.py`; `origin:"proprietary"`, `omics:"electrophysiology"`, `omics_type:["general"]`.
- **Canonical ERG tables** (the parser's output contract):
  - `erg_waveforms_long`: `sample_id, condition, condition_order, intensity_group, intensity_log_cd_s_m2, time_ms, voltage_uv, role`.
  - `erg_metrics_long`: `sample_id, condition, animal, eye, intensity_group, intensity_log_cd_s_m2, b_wave_uv, a_wave_uv, b_wave_implicit_ms, a_wave_implicit_ms` (+ optional `qc_excluded`, `condition_order`).
- **Ingest detection** (`app/backend/engine/cleaning.py`, rebuilt T8): `profile_data` ranks signals
  format → content → filename. `.iwxdata` is ERG-certain by **format**; an a/b-wave + intensity
  column signature is ERG by **content**. ERG profile → `plan_cleaning` returns an honest empty plan
  ("used as-is", no matrix cleaning). `engine/route.py::route_profile` routes a recognized ERG table
  to the electrophysiology skills.
- **Skill contract / guards** (`docs/erg-module/spec.md` "What exists today"): `SkillSpec`,
  `run_skill_with_table` pops `spec["table"]` before theming, the table-contract guard
  (`NATIVE ∪ L3 ∪ L4_ONLY`), golden tests (`regen_golden.py`).

### Format archaeology (done this session, on the sample export)
Sample: `C:\Users\seamegdool\Desktop\Github Projects\Diagnosys ERG\diagnosys_erg\data\raw\*.CSV`
(another lab's data — **format reference only**, not the owner's project). A friend's script
(`src/python/extract_erg_data.py`) extracts the Data Table only and **drops the Marker Table**.

Confirmed structure (web-backfilled against the Diagnosys rodent biomarker guide + ISCEV 2022):
- **One CSV, two side-by-side tables.** Row 1: `Marker Table,,,…,Data Table,,,…`. The Marker Table
  occupies the left columns, the Data Table the right.
- **Marker Table** columns: `Group, Name(animal), Cage#, Age, Date, S, C, R, Eye, Name(marker), uV, ms`.
  - `S`=Step (stimulus/intensity), `C`=Channel (`1`→RE, `2`→LE here), `R`=Result (the *averaged* trace).
  - Per-row marker `Name`: `a` = a-wave (corneal-negative trough), `B`/`b` = b-wave, `c-wave` = c-wave.
    **`B` vs `b` is a protocol-template convention, not a different feature**: uppercase `B` on the
    dark-adapted (scotopic) family, lowercase `b` on the light-adapted (photopic/PhNR) family — so
    **case-fold (`b≡B`)**. Flicker uses `N1`/`P1` (no a-wave); oscillatory potentials `OP1..3`;
    photopic negative response `PhNR`.
  - Amplitudes in **µV**; the Data Table waveform header reads **`Result (nV)`** → **1 µV = 1000 nV**.
    Export units are configurable → **read the unit from the column header, do not hard-code.**
- **Data Table**: repeating `Step N` blocks, each `Time (ms)` + `Chan 1..4` `Result (nV)` columns.
  **Multiple time bases occur** (the friend's `Time_ms_Group_2`): short flash window for most steps,
  a long window for the c-wave step.
- **No explicit photopic/scotopic or flash/flicker field.** Adaptation state + flash intensities live
  in the protocol, not the CSV — only `Step N`. **Derive, don't read** (see R-parser-3).
- **Real hazards seen in the sample:** (1) a **malformed line** — a date `3/7/2024` split across two
  physical lines (Mac CR/LF artifact) misaligns a naïve `read_csv`; (2) the **marker set varies by
  step** — steps 1–6 = `{a,B}`, step 7 = `{a,b,c-wave}` (do not assume every step is `{a,B}`);
  (3) **Data-Table `Chan` is not eye-resolved** unless mapped against the Marker Table's `C→Eye`.
- **The provided sample is a scotopic 7-step intensity series** (markers `a/B/b/c-wave`, **no
  `N1`/`P1` flicker markers**). See Decision **D7** — building+validating photopic and flicker needs
  representative photopic and flicker exports.

### Native Espion format vs the CSV export (the ingest-target decision — see D10)
The owner surfaced the device's **native raw files** (`\\cmri.com.au\…\Will Y\…\Diagnosys Epsion\
Raw files - ERG`, the Prom1 project — another project, format reference only): 29 × ~813 KB
`ESSAVE_…_FDB_…_*.BAK` files. Inspected: each begins with the magic bytes **`ESP`** (0x45 53 50) +
a version byte, then **little-endian `<int32 length><bytes>` record framing** with embedded strings
(an OLE/Excel-style date serial, and the source DB path `C:\Multifocal\Databases\rd19_database…`).
**This is Espion's proprietary binary database backup** (a whole database of many tests), *not* a
standard SQL `.BAK` and *not* the figure data directly. **The friend's CSV is an export out of this
database.** Conclusion: **Selom targets the CSV export, not the native `.BAK`** (D10) — the CSV is
the stable, documented, every-Espion-user-can-produce-it format that already carries everything we
need (Marker Table + Data Table). A native `.BAK` decoder is parseable-in-principle (the framing
resembles the cracked `.iwxdata`) but is a large, undocumented, version-fragile reverse-engineering
effort against a full database — an optional future moat, not this spec.

### Export-format lineage + all-three-modes data (RESOLVED this session)
The owner supplied real Espion exports from the Prom1 AAV-therapy project (Will Y; format reference
only). Four artefacts exist along the lineage:
- **Native `.BAK`** — proprietary `ESP`-magic DB backup (above; out of scope, D10).
- **Full multi-table `.TXT`** (TAB-delimited) — the RICHEST export and the **primary target**. Row 1
  names the tables present: **Contents Table** (Left/Top/Right/Bottom bounds of every sub-table — a
  built-in, *exact* table locator), **Header Table** (Parameter/Value — the Protocol name + Espion
  Version), **Marker Table** (+ a `Comment` column), **Summary Table** (per Step/Result trials &
  rejects), **Stimulus Table** (`Step → Description → cd.s/m²`), **Data Table** (Step×Chan waveforms,
  nV). Example: protocol `EGU Dark & Light Adapted ERG`, Espion v6.64.
- **Reduced `.CSV`** (COMMA-delimited) — the friend's file: **Marker Table + Data Table only**, no
  Contents/Header/Stimulus tables. The parser must support this leaner variant too.
- **Processed `.xlsx`** — a downstream analysis workbook (out of scope).

**The Stimulus Table is the key unlock**: it makes adaptation state + intensity + flicker frequency
**readable**, not merely inferable. The example file's 9 steps: `DA 0.01 / 0.1 / 1 / 3 / 10 cd.s/m²`
(scotopic series) · `LA Single 3.0 / 10.0 Flash` (**photopic** single-flash) · `LA 10 Hz / 30 Hz
Flicker` (**flicker**). **So one real export carries all three modes** — D7 is resolved: scotopic,
photopic, AND flicker validation data is in hand, no data gate remains. The mode→skill mapping is
direct: `DA *` → the scotopic skills; `LA Single * Flash` → photopic (same skills, `adaptation`
hint); `LA * Hz Flicker` → the new `erg_flicker`.

## Requirements

### Parser — `app/backend/skills/_celeris.py` (new; sibling of `_iwx.py`)
- **R-parser-1.** Detect a Diagnosys export by a **magic header**: the first non-empty row contains
  `Marker Table` and `Data Table` (case-insensitive; the full export also names `Contents Table`,
  `Header Table`, `Summary Table`, `Stimulus Table`). Format-grade signal (as certain as the
  `.iwxdata` suffix), independent of the `.csv`/`.CSV`/`.txt`/`.TXT` extension. **Sniff the delimiter**
  from the header row — **TAB** (full `.TXT` export) or **comma** (reduced `.CSV`) — and use it
  throughout.
- **R-parser-2.** Parse the **present tables** robustly (pure stdlib `csv`, no `pandas.read_csv`
  header-guessing — the side-by-side multi-table layout defeats it). **Locate each sub-table from the
  Contents Table** (its `Left/Top/Right/Bottom` bounds are exact) when present; **fall back to scanning
  the header row for the table-name banners** for the reduced CSV that has no Contents Table.
  - **Header Table → metadata**: Protocol name + Espion Version (carried onto outputs for methods/provenance).
  - **Marker Table → `erg_markers_long`**: one row per `(animal, eye, step, marker)` =
    `sample_id, condition, animal, eye, step, channel, marker_name, amplitude_uv, implicit_ms`,
    units normalized to µV from the header. `marker_name` case-folded for `b`.
  - **Stimulus Table → per-step stimulus metadata**: `step → description, intensity_cd_s_m2` (and the
    derived `stimulus_type`/`adaptation`/`flicker_hz`, R-parser-3). Absent in the reduced CSV → fall
    back to inference.
  - **Data Table → `erg_waveforms_long`**: one row per `(sample_id, step, time_ms)` with
    `voltage_uv` (nV→µV per the header), the step's `intensity_group` + `intensity_log_cd_s_m2` (from
    the Stimulus Table when present), and `eye`/`channel` resolved against the Marker Table's `C→Eye`
    map (R-parser-5). Baseline-correct (subtract the pre-stimulus mean, samples where `time_ms < 0`).
  - Derive `erg_metrics_long` (the existing a/b schema the current skills read) as a **view** over
    `erg_markers_long` (a-wave + the case-folded b-wave per step×eye), so `erg_traces` /
    `erg_intensity_response` / `erg_bwave_bar` consume it **unchanged**.
- **R-parser-3.** **Stimulus-type per step — layered read-then-infer** ([[layered-deterministic-extraction]]):
  - **L1 (read, when the Stimulus Table is present):** parse the Description → `stimulus_type`
    (`scotopic_flash | photopic_flash | flicker | c_wave`), `adaptation` (`DA`→dark/scotopic,
    `LA`→light/photopic), `intensity_cd_s_m2`, and `flicker_hz` (from `… Hz Flicker`). This is the
    authoritative signal in the full `.TXT` export.
  - **L2 (infer, reduced CSV with no Stimulus Table):** from the marker vocabulary (`a` present ⇒
    flash; `N1`/`P1` only ⇒ flicker; a `c`/`c-wave` marker ⇒ c-wave present) + lowercase `b` ⇒
    light-adapted hint. Tagged lower-confidence.
  - Recorded on every row so each skill filters by mode (scotopic/photopic flash → trace grid +
    intensity-response; flicker → `erg_flicker`).
- **R-parser-4.** **Malformed-line tolerance.** Normalize CR/LF/CR-LF; rejoin a physical line that
  splits a logical record (detected by column-count underflow against the header); never let one bad
  line drop a whole step. Log a recovered-line count.
- **R-parser-5.** **Channel→eye resolution.** Build the `C→Eye` map from the Marker Table
  (`C=1→RE, C=2→LE` in the sample, but read it, don't assume) and apply it to the Data Table's
  `Chan` columns; unmapped channels are carried with `eye=""` (not dropped).
- **R-parser-6.** **Multiple time bases** (R-parser per the `Time (ms)` blocks): group steps by their
  time vector; a long-window step (c-wave) is kept as its own step, never force-aligned to the short
  window.
- **R-parser-7.** Pure stdlib on the decode path (`csv`, `re`); pandas imported lazily only to
  assemble the final frames (mirrors `_iwx.py`). Honest `ValueError` (named cause) on a file with no
  recognizable Marker/Data table.

### Ingest detection + routing
- **R-ingest-1.** `engine/cleaning.py` recognizes a Diagnosys CSV as **ERG-certain by format** via the
  magic-header content sniff (R-parser-1) — a new content-magic candidate ranked alongside the
  `.iwxdata` format signal. (A Diagnosys CSV read naïvely is a messy two-table frame; the magic
  header, not the columns, is the reliable signal.)
- **R-ingest-2.** `engine.ingest` gains a **Diagnosys-CSV loader** (registry entry, sibling of the
  `.iwxdata` loader) that decodes via `_celeris.py` and materializes the canonical ERG table(s) to a
  temp CSV so the path-based skills run unchanged (mirrors `_iwx` materialize). The dropped file
  drop-and-runs as ERG.
- **R-ingest-3.** FE dropzones accept the Diagnosys CSV with no new affordance — it is a `.csv`, and
  the magic-header detection does the rest (the data-type strip shows "ERG / electrophysiology",
  with the override available per T8).

### Scotopic mode (reuse — no new skill)
- **R-scotopic-1.** `erg_traces`, `erg_intensity_response`, `erg_bwave_bar` run **unchanged** on the
  parser's `erg_waveforms_long` / `erg_metrics_long`. The win over the iWorx path: a/b amplitudes come
  from the **device's own markers** (Marker Table), not re-detected — `_erg.landmarks` is run only as
  a **cross-check column** (device-vs-Selom delta surfaced for QC), never overriding the device value.

### Photopic mode (reuse + validation; new param, not a new skill)
- **R-photopic-1.** Photopic is a **data variant**, not a new skill: the same three skills serve it
  (light-adapted flash steps → trace grid + b-wave; intensity series → Naka-Rushton). A small
  `adaptation` hint (`scotopic | photopic | auto`, default `auto` from R-parser-3) drives labels and
  caption wording only.
- **R-photopic-2.** **Trust device markers** (the design rule, validated here): photopic a-waves are
  small/absent and b is lowercase — re-detection is fragile, so the device markers are authoritative;
  `_erg.landmarks` stays a cross-check. No flash-vs-flicker auto-detection on the metric path.
- **R-photopic-3.** Acceptance: the `LA Single 3.0/10.0 Flash` steps render a faithful light-adapted
  trace grid + b-wave summary with no scotopic-specific assumption firing.

### Flicker mode (NEW skill + NEW graph)
- **R-flicker-1.** New skill **`erg_flicker`** (`skills/proprietary/erg_flicker/`), consuming the
  flicker-tagged rows. Two outputs, both editable `{data, layout}`:
  - **the flicker waveform** — a few steady-state cycles per condition (reuse `_tracegrid` for the
    per-condition small multiples), with `N1`/`P1` markers from the device;
  - **the flicker summary** — N1→P1 amplitude (µV) + implicit time (ms) per condition, and, when a
    **flicker-frequency series** is present, amplitude-vs-frequency (a line/scatter, the structural
    sibling of `erg_intensity_response`; **no Naka-Rushton** — flicker is not an intensity-saturation
    curve).
- **R-flicker-2.** Attaches `spec["table"]` = the per-condition flicker N1/P1 amplitude + implicit
  time (→ native; table-contract guard registration). `origin:"proprietary"`,
  `omics:"electrophysiology"`, `omics_type:["general"]`.
- **R-flicker-3.** The flicker metric is **N1→P1 peak-to-trough on the steady-state cycles**, taken
  from the device markers where present (Selom re-derivation only as a fallback/cross-check). No
  a-wave/b-wave language on a flicker panel. Validated on the real `LA 10/30 Hz Flicker` steps.

### Methods + FE
- **R-methods-1.** Extend the ISCEV methods builder for the three modes: instrument = Diagnosys
  Espion/Celeris; per mode the adaptation state, background, intensity/frequency ladder, marker
  definitions, n per group; with citations. Reuse `methods.build` per-skill builders.
- **R-fe-1.** Figures render + edit via `use-figure-store.init({figure, table})` (no new FE
  primitive). The flicker figure is a `{data, layout}` like any other.
- **R-honesty-1.** Every panel is captioned for what it is (representative vs mean; device-marker vs
  Selom-derived; adaptation state). Device-vs-Selom marker deltas are surfaced, not hidden.

## Design

### Components & data flow
```
Diagnosys/Celeris .CSV (two tables in one file)
        │  R-parser-1 magic-header detect → engine.ingest Diagnosys loader (R-ingest-2)
        ▼
_celeris.py: parse BOTH tables, normalize units, derive stimulus_type, resolve eye
        ├── erg_markers_long  (a/B/b/c/N1/P1/PhNR · µV · ms · stimulus_type)
        ├── erg_metrics_long  (a/b view → existing skills, unchanged)
        └── erg_waveforms_long (nV→µV, baseline-corrected, eye-resolved)
        │
        ├─ scotopic ─→ erg_traces · erg_intensity_response · erg_bwave_bar   (REUSE)
        ├─ photopic ─→ same three skills (adaptation hint)                    (REUSE + validate)
        └─ flicker  ─→ erg_flicker  (NEW: flicker grid + N1/P1 summary)       (NEW graph)
        │  methods.build → {text, citations}
        ▼  themed {data,layout}(+table) → API → FE editor
```

### The parser — `app/backend/skills/_celeris.py`
Pure-stdlib, mirrors `_iwx.py`'s shape: low-level `csv` row reader → a `DiagnosysExport` dataclass
(animals × eyes × steps × markers + waveforms) → `markers_long()` / `metrics_long()` /
`waveforms_long()` projections + a top-level `read_celeris(path) -> {table: DataFrame}`. Unit
normalization and stimulus-type derivation are small pure helpers (unit-tested in isolation).

### The flicker skill — `app/backend/skills/proprietary/erg_flicker/`
Clones the `erg_intensity_response` structure: `skill.json` + `run.py` (dependency-free synthetic
stub for goldens) + `run_real.py` (reads the flicker rows, builds the grid + summary, attaches the
table). Reuses `_tracegrid.grid_spec` for the waveform panel and a plain line/scatter for the
amplitude-vs-frequency summary.

### Theme
`erg_flicker` → `_KIND["erg_flicker"]="trace_grid"` for the waveform panel; the summary panel uses
the base line styling. No new theme kind needed.

### File changes
**Phase 1 (parser + scotopic reuse):**
- `app/backend/skills/_celeris.py` (new parser: delimiter sniff, Contents-Table locate, all sub-tables, Stimulus-Table read) + `tests/test_celeris.py`.
- `app/backend/engine/cleaning.py` (magic-header ERG-by-format candidate) + `engine/ingest` loader registration.
- `app/backend/tests/test_cleaning.py` / `test_data_inspect.py` (Diagnosys export → ERG cases).
- Validate the scotopic `DA *` steps end-to-end on a real `.TXT` export.
**Phase 2 (photopic):** `adaptation` param wiring on the three skills + methods wording; validate the `LA Single * Flash` steps.
**Phase 3 (flicker):** `skills/proprietary/erg_flicker/{skill.json,run.py,run_real.py}`, golden + table-contract `NATIVE` registration, FE seed (Electrophysiology shelf), param overlay, MSW spec fixture; validate the `LA * Hz Flicker` steps.
**Phase 4 (methods + FE polish):** `methods._erg_flicker` + the three-mode ISCEV wording; FE verify on real data; `/impeccable` pass.

## Decisions

- **D1 — Parser lives in `skills/_celeris.py`, emits the canonical tables.** Chosen: a sibling of
  `_iwx.py`. Alt: a generic CSV loader in the engine (rejected — the two-table layout needs bespoke
  parsing, not a generic reader). Why: maximal reuse — once the canonical tables are emitted the
  existing skills work. Reversible: yes.
- **D2 — Trust the device's Marker Table; `_erg.landmarks` is a cross-check only.** Chosen. Alt:
  re-detect a/b from the waveform (rejected — fragile for photopic small a-waves and flicker; the
  device already placed correct markers; this is the photopic-robustness rule the web backfill
  confirmed). Why: sidesteps the entire photopic/flicker detection problem and gives ground truth to
  validate Selom's auto-detection. Reversible: yes (the landmark path stays for marker-less inputs).
- **D3 — Flicker is a NEW skill (`erg_flicker`), not an `erg_traces` mode.** Chosen. Alt: a `mode`
  param on `erg_traces` (rejected — flicker's graph + metric [N1/P1, amplitude-vs-frequency] differ
  enough that overloading muddies both). Why: a clean, separately-tested figure. Reversible: yes.
- **D4 — Photopic REUSES the three scotopic skills (data variant, `adaptation` hint), no new
  skill.** Chosen. Alt: separate `erg_photopic_*` skills (rejected — duplication; the skills are
  condition×intensity agnostic). Reversible: yes.
- **D5 — Detect Diagnosys exports by a content magic-header, ranked ERG-certain (format-grade).**
  Chosen. Alt: filename hint (rejected — unreliable; the sample names are `dr1.CSV` etc.). Reversible: yes.
- **D6 — `erg_markers_long` is a new canonical table (superset); `erg_metrics_long` is a derived
  a/b view.** Chosen so c-wave/N1/P1/PhNR are captured without breaking the existing a/b-only schema.
  Alt: add nullable columns to `erg_metrics_long` (rejected — wide and sparse). Reversible: yes.
- **D7 — RESOLVED: all three modes have real validation data.** The full `.TXT` exports (Will Y Prom1
  AAV experiments 8 & 9) carry, in a single file, a scotopic DA intensity series (0.01–10 cd·s/m²),
  photopic `LA Single 3.0/10.0 Flash`, and `LA 10/30 Hz Flicker`. **No data gate remains** — Phases
  1–3 all build + validate on real data. (The earlier scotopic-only `.CSV` was the friend's *reduced*
  export, not the full picture.)
- **D8 — Condition/group labels** derive from the Marker Table `Group`/animal `Name` + filename stem
  (configurable), defaulting to the file/group identity. The owner's own conditions would come from
  the filename as today; another lab's groups (`dr`/`ivt`/`noivt`) come from the file stem.
  Reversible: yes (a param).
- **D9 — This is proprietary IP** (consistent with `docs/erg-module/spec.md` D8): the Diagnosys
  parser + `erg_flicker` ship under `skills/proprietary/` with `origin:"proprietary"`. Reversible: yes.
- **D10 — Ingest target = the CSV export, NOT the native Espion `.BAK`.** Chosen (confirmed by
  inspecting the native files — proprietary `ESP`-magic binary DB backups). Alt: a native `.BAK`
  decoder so the user drops the raw device file like a `.iwxdata` (deferred — large undocumented
  reverse-engineering effort against a whole-database container, high version fragility, and the user
  must run Espion to produce/restore it anyway). Why: the CSV export is stable, documented, carries
  everything we need, and every Espion user can produce it — the robust layer the promise anchors to
  ([[layered-deterministic-extraction]]). Reversible: yes — a `.BAK` decoder could be added later as a
  parallel moat (like the `.iwxdata` decode was), only if manual CSV export proves a real friction
  point (e.g. batch-automating hundreds of tests without opening Espion).

## Versions
- Python 3.12 (uv), Plotly as vendored — **no new dependency** (parser is stdlib `csv`/`re`;
  Naka-Rushton reuses the existing scipy path; flicker summary is numpy/plain-Python).

## Invariants
- The FE-rendered spec stays pure `{data, layout}`; `spec["table"]` is popped in `run_skill_with_table` before theming.
- Trace-grid per-panel axes stay `visible:false`; the scale bar is the only axis cue.
- Table-contract guard green: `erg_flicker ∈ NATIVE` **and** its runner attaches `spec["table"]`.
- Golden determinism: stubs fixed, no `Date.now`/RNG in skill code.
- Unit normalization is header-driven (µV markers, nV traces → µV); never hard-coded.
- Device markers are authoritative; Selom-derived landmarks never silently overwrite them.

## Error Behavior
- **Not a Diagnosys export** (no Marker/Data header) → `_celeris` raises a named `ValueError`; ingest
  falls back to generic-table profiling (no false ERG claim).
- **Malformed line** → recovered per R-parser-4; if unrecoverable, that step is dropped with a logged
  note, never a silent partial figure.
- **Step with no usable marker / unmapped channel** → carried honestly (`eye=""`, marker absent),
  never fabricated.
- **Flicker/photopic requested but absent in the file** → honest empty result naming what's missing
  (e.g. "no flicker steps in this export").
- **Missing required columns** downstream → the existing skills' named `ValueError` (unchanged).

## Testing Strategy
- **Parser unit tests** (`test_celeris.py`) over a committed **synthetic** two-table fixture (CI-safe,
  no real-data dependency): both tables parsed; units normalized (a µV marker + its nV waveform peak
  reconcile at 1000×); `b`≡`B` case-fold; stimulus_type derivation (flash/flicker/c-wave); the
  malformed-line recovery; channel→eye mapping; multi-time-base separation.
- **Real-sample test (opt-in, owner machine):** parse the provided scotopic sample → assert
  `erg_metrics_long` a-waves negative / b-waves positive, 7 steps × 2 eyes, c-wave only on the top
  step, 0 dropped steps. Skipped without the staged sample (CI stays green).
- **Scotopic reuse:** `erg_traces` / `erg_intensity_response` / `erg_bwave_bar` run on the parser
  output → golden + table-contract unchanged; a device-vs-`landmarks` delta column is sane.
- **Ingest:** a Diagnosys CSV → `profile_data` ERG-certain (by magic header); `plan_cleaning` empty
  ("used as-is"); `/data/inspect` shows "ERG / electrophysiology"; routes to electrophysiology skills.
- **Flicker (Phase 3):** `erg_flicker` golden (synthetic stub) + table-contract `NATIVE`; on the real
  `LA 10/30 Hz Flicker` steps, N1/P1 amplitudes + the summary render.
- **Photopic (Phase 2):** the real `LA Single 3.0/10.0 Flash` steps render without a scotopic assumption firing.
- **Verify LIVE** (not `dev:mock`, [[verify-on-real-data-not-mock]]): real uvicorn + `npm run dev`,
  drop the Diagnosys CSV, confirm classification + each figure renders + edits.

## Out of Scope
- The owner's iWorx `.iwxdata` photopic path (C7) — this spec subsumes the *capability* on Diagnosys
  data; retrofitting the iWorx decoder for photopic is a later, separate item.
- VEP / PERG / pattern markers (`P1/N1/P2`, `VP1/VN1`), OCT, optomotor, IHC — other modalities.
- Auto-fetching exports from any share/network (manual paths only).
- **Decoding the native Espion `.BAK` database** (proprietary `ESP`-magic binary) — deferred optional
  moat (D10); this spec ingests the `.TXT`/`.CSV` export.
- The downstream processed `.xlsx` analysis workbook (a consumer of the export, not an input).
- A general Espion-format library beyond what these three ERG modes need.
- Multi-file → one multi-condition grid (the ERG-module C6 optional) — orthogonal; handled there.

## Open questions for review
1. **D7 is resolved** — the full `.TXT` exports carry all three modes, so Phases 1–3 build straight
   through, no data gate. Confirm you're happy building against the Will-Y Prom1 exports as the
   format/validation reference (another project; figures are not shipped — format only).
2. Confirm the proprietary placement (D9) and that scotopic+photopic should reuse the existing three
   skills verbatim (D1/D4) with flicker as the one new skill (D3), rather than a Diagnosys-specific
   skill family.
3. Primary target = the full tab-delimited `.TXT` (richest), with the reduced `.CSV` supported as a
   leaner variant (D1/lineage). OK?
