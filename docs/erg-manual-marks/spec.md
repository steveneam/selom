# Spec — ERG manual a/b + N1/P1 marker override (`erg-manual-marks`)

## What
Let the scientist **set/move the ERG landmark points themselves** — the a-wave and b-wave on a flash
trace, N1 and P1 on a flicker trace — directly on the trace grid, and have the b-wave bar +
intensity-response (and the flicker summary) measure **at those user-set points** instead of the
auto-windowed peak/trough. The auto-detection (`_erg.landmarks` / `flicker_landmarks`) becomes the
**seed**; the operator confirms or drags. No manual marks supplied → today's behaviour, byte-identical.

> **v1 scope (owner-set 2026-06-24): MARKS ONLY** — R1–R5 + R8 (the draggable override that measures
> at the chosen point). **R6 (auto-vs-moved provenance log) and R7 (blinded marking) are DEFERRED to
> v2** — the data model below still tags each value `auto`/`manual` (cheap, used by the table caption),
> but the persisted provenance log and the blinding toggle are not built in v1.

## Context
### Why this matters
The T15 photopic work (`docs/erg-module/spec.md` D12–D14) showed the from-traces a/b metric is only
as good as the search window, and on real hum-heavy single-eye iWorx photopic recordings the window
can land on an artifact (a ~50 Hz hum crest, a rod-contaminated late peak). Web research (recorded in
the T15 build-log) confirmed the field-standard fix is **auto-seed + operator-adjust**, not a fully
automatic black box:
- **Diagnosys Espion** auto-places markers in a search window and lets the operator *"manually adjust
  if necessary."*
- **ISCEV 2022** defines the measurements this feature must honour: a-wave amplitude = pre-stimulus
  **baseline → a-wave trough**; b-wave amplitude = **a-wave trough → b-wave peak**; flicker amplitude
  = **N1 trough → P1 peak**; implicit time = stimulus → that point.
- **ERGAssist** (Feola 2023) recommends exactly this hybrid: auto-detect, flag ambiguous traces,
  allow manual adjustment.
The one integrity upgrade the literature flags as missing in existing tools: **record that a marker
was moved** (auto vs operator), plus support **blinded marking** (mark without seeing the group
label). Both fit Selom's honesty/provenance positioning.

### What exists today (verified)
- **Auto landmarks** — `_erg.landmarks(time_ms, y, fs, *, mode)` returns `{a_wave_uv, b_wave_uv,
  a_t_ms, b_t_ms}` by argmin/argmax over the mode's windows; `_erg.flicker_landmarks(...)` returns
  `{n1p1_uv, p1_implicit_ms, n1_implicit_ms, n1_uv, p1_uv}` from the phase-folded cycle.
- **Fan-out metric** — `_erg.metrics_from_waveforms(df, *, default_mode)` measures one a/b row per
  `(sample_id, condition, stimulus_type, intensity_group, eye)` segment. `erg_bwave_bar` /
  `erg_intensity_response` call it; `erg_flicker` measures N1→P1 per `(condition, freq)` (device
  markers preferred when the feed carries `device_n1p1_uv`).
- **Trace-grid overlay** — `_tracegrid.grid_spec` already draws a per-panel `markers:[{x,y,label,
  color,size}]` overlay against the panel's own hidden axis; `erg_flicker` uses it for N1/P1 dots
  (`_erg.flicker_first_cycle_marks`). This is the exact hook the editable dots ride on.
- **Figure editor** — `app/frontend/lib/figure-model.ts` already models editable primitives
  (`scalebar`, `annotation*Op`) and a **Marks panel** (`components/figure/panels/marks-panel.tsx`)
  shows/edits scale-bar + annotations. `meta.selom.primitives` carries the editor-resolvable bits.
- **Device markers stay authoritative** — when a metrics table carrying `a_wave_uv`/`b_wave_uv` (or
  flicker `device_n1p1_uv`) is supplied, that wins over from-traces measurement (D2). Manual marks
  sit **on top of the from-traces path** (the path that needs them); device-marker input is untouched.

## Requirements
- **R1 — measure at a supplied time.** `_erg.landmarks` accepts an optional manual override of the
  a-wave and/or b-wave **time** and returns the amplitude measured at that time per ISCEV (a =
  baseline − value at `a_ms`; b = value at `b_ms` − a-trough), with the implicit time = the supplied
  time. A partial override (only a, or only b) leaves the other auto. `flicker_landmarks` likewise
  accepts an N1 and/or P1 time override.
- **R2 — per-segment marks.** `metrics_from_waveforms` accepts a `marks` lookup keyed by the segment
  identity `(condition, stimulus_type, intensity_group, eye)` and applies each segment's override.
  Missing key → auto (the seed). `erg_flicker` accepts marks keyed by `(condition, flicker_hz, eye)`.
- **R3 — skills pass it through.** `erg_bwave_bar`, `erg_intensity_response`, `erg_traces`, and
  `erg_flicker` accept a `manual_marks` param (JSON), parse it to the R2 lookup, and thread it to the
  metric. Default empty → byte-identical to today (no golden regen).
- **R4 — seedable dots.** `erg_traces` and `erg_flicker` emit each panel's current a/b (or N1/P1)
  **marker dots** (seeded from the auto-detection, or the supplied manual marks) on the existing
  `markers` overlay, tagged in `meta.selom` with the segment identity so the editor can bind a drag
  back to the right `manual_marks` entry.
- **R5 — draggable in the editor.** The figure editor lets the user drag an a/b/N1/P1 dot along the
  trace; the drop x-time updates the matching `manual_marks` entry in `figure-model.ts` and re-runs
  the affected figure. A **Marks panel** lists the per-cell marks with numeric time inputs, a
  **"reset to auto"** per marker/all, and shows the resulting amplitude.
- **R6 — provenance.** Each measured a/b/N1/P1 value carries `source ∈ {auto, manual}`; the attached
  table caption states the mix ("3 of 12 operator-adjusted"), and a per-marker log records
  `{segment, marker, auto_ms, set_ms, moved}`. This is recorded in the reproducibility config so the
  figure is auditable.
- **R7 — blinding.** The Marks panel has a **"blind"** toggle that hides condition/group labels (and
  greys the column headers) while marking, so adjustments can't be biased to a hypothesis; the marks
  persist when blinding is turned back off.
- **R8 — honesty/default.** With no `manual_marks`, all four skills are byte-identical to today
  (goldens unchanged). Device-marker input still wins where supplied (R2 applies only to the
  from-traces path).

## Design
### Data model — `manual_marks`
A JSON object param on the skills, e.g.
```json
{ "Control|scotopic_flash|Group4|RE": { "a_ms": 12.4, "b_ms": 58.0 },
  "Untreated|photopic_flash|Group5|LE": { "b_ms": 41.0 } }
```
Key = `"{condition}|{stimulus_type}|{intensity_group}|{eye}"` (the segment identity; empty parts
allowed for tables that lack a column — match on the parts present). Flicker uses
`"{condition}|{flicker_hz}|{eye}"` with `{ "n1_ms": …, "p1_ms": … }`. A `manual_marks` value is the
authoritative *time*; amplitude is always re-measured from the trace at that time (so a unit/scale
change still rescales correctly). Stored as a JSON string in `param_spec` (mirrors how other complex
params travel); parsed once per run.

### Backend
- `_erg.landmarks(..., manual: dict | None = None)` — when `manual` carries `a_ms`/`b_ms`, measure at
  that time on the same dual-smoothed trace the auto path uses (read a ±1-sample-window mean to avoid
  single-sample noise), keeping baseline + trough conventions; return the same dict plus
  `a_source`/`b_source ∈ {auto, manual}`.
- `_erg.flicker_landmarks(..., manual: dict | None = None)` — analogous for `n1_ms`/`p1_ms` on the
  phase-folded cycle.
- `metrics_from_waveforms(df, *, default_mode, marks=None)` — build the segment key per group, look
  up `marks`, pass to `landmarks`; carry `a_source`/`b_source` onto the row.
- `_erg.parse_manual_marks(raw) -> dict` — shared JSON→lookup parser (tolerant: bad entries skipped,
  never raises) used by all four skills.
- Skills add a `manual_marks` (str, default "") param; `erg_bwave_bar`/`erg_intensity_response`/
  `erg_traces` thread it into `metrics_from_waveforms`; `erg_flicker` into its N1/P1 path. The table
  title gains the provenance line (R6).

### Frontend
- `erg_traces`/`erg_flicker` panels emit the seed dots via the existing `markers` overlay, with each
  dot's segment identity + role (`a`/`b`/`n1`/`p1`) in `meta.selom.primitives.marks`.
- `figure-model.ts` gains a `marks` primitive + `markMoveOp`/`markResetOp`; the canvas makes the dots
  draggable (constrained to the trace's x-domain, snapped to the nearest sample) → emits the op → sets
  `manual_marks` → re-runs.
- `marks-panel.tsx` (or a sibling) gains a per-cell marks table (time inputs + measured amplitude +
  reset-to-auto + the provenance flag) and the blinding toggle (R7).

## Decisions
- **D1 — override the TIME, re-measure the amplitude (not store a fixed amplitude).** Alternative:
  store the operator's amplitude directly. Chosen: store time, re-measure → a display-unit/scale
  change still rescales, and the value always matches the visible trace. Reversible: yes.
- **D2 — JSON `manual_marks` param, not a separate marks CSV.** Alternative: a second uploaded marks
  table. Chosen: marks are produced by dragging in the editor and belong to the figure config (travel
  with the reproducibility bundle), not a re-uploaded file. Reversible: yes (a CSV import can map to
  the same lookup later).
- **D3 — build on the existing `markers` overlay + Marks panel, not a new primitive type.** The
  flicker N1/P1 dots already prove the overlay; reuse keeps one editor vocabulary. Reversible: yes.
- **D4 — provenance is first-class (R6), exceeding Espion/ERGAssist.** Assumption: the owner wants the
  auditability (fits the honesty pillar); cheap to add, and the differentiator vs the incumbents.

## Invariants
- No `manual_marks` → every ERG skill is byte-identical (goldens unchanged); CI asserts the default
  path on the existing goldens.
- A supplied a/b/N1/P1 amplitude always equals the trace value at the marked time under the current
  display unit (rescales with `display_unit`).
- Device-marker input (a metrics table) is never overridden by `manual_marks` — manual marks apply
  only to the from-traces path.

## Error Behavior
- Malformed `manual_marks` JSON or an out-of-range time → that entry is ignored (fall back to auto),
  never a 500; the run still returns a figure. A `_design`-style note can flag dropped entries.
- A mark time outside the trace's sampled range → clamp to the nearest sample and tag the value
  `manual` (the editor also constrains the drag).

## Testing Strategy
- Unit (`tests/test_erg_units.py`): `landmarks(manual=…)` measures at the set time (a synthetic trace
  with a known a/b); partial override; `parse_manual_marks` tolerance; `flicker_landmarks(manual=…)`.
- Skill e2e: `erg_bwave_bar` / `erg_intensity_response` with `manual_marks` move a value off the auto
  seed and the bar/curve follow; provenance line appears; **no `manual_marks` → byte-identical** to
  the existing run (assert against the current output).
- FE (vitest): `figure-model` mark move/reset ops; the Marks panel reset-to-auto + blinding toggle.
- Real-data check: on the hum-heavy C57 photopic file, drag the b-mark to the real cone b-wave region
  and confirm the bar value changes + the provenance flags it operator-moved.

## Out of Scope
- Auto-fetching device operator marks (the iWorx `.iwxdata` carries none; that's why this exists).
- A full audit-trail server store — the provenance log lives in the figure's reproducibility config.
- Cross-figure mark propagation / a study-wide marking session manager (future; this is per-figure).
- Changing the auto windows (T15 owns those); this rides on top of them as the seed.
