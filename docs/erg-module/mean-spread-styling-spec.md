# Spec — Mean ± spread, individual points, and trace styling (bar + traces)

Status: **BAR HALF BUILT (2026-06-24, session T12); TRACE HALF pending C6 for real-n.** Author: Claude (Opus 4.8), 2026-06-24.
Owner ask (2026-06-24): bar AND traces should show the **mean** with an **optional individual-data-point**
overlay (n = whatever), and the spread should be selectable as **SEM or SD**. The bar style is
"straightforward"; the **traces** need several selectable styles (7 reference figures attached, mapped
below). "Scope this out and plan… build it next session." This is the durable plan.

## Owner decisions (2026-06-24, on the Fig 1E "Scotopic B wave" GraphPad target)
- **D7 — Spread default = SEM** (SD/CI95/minmax one click away). *Built.*
- **D8 — Bar fills = replicate the GraphPad hatch patterns** per condition (solid Control + 3'UTR,
  hatched rest); colour = the Selom condition palette as the hatch foreground; also `filled`/`open`.
  Real-path default is `pattern`; the golden **stub** stays `filled` (byte-identical). *Built.*
- **D9 — Significance brackets = "both available":** Selom **computes** the p-value
  (Welch/Student/Mann–Whitney) and places the stars, AND every star is **overridable** (`A~B:**`
  or `A~B:0.003` in the `comparisons` string). *Built.*
- **D10 — Reference line is a GENERAL feature**, not a fixed 50%-WT threshold: the dashed line in
  the owner's figure is just a manual grouping cue. Expose an "add a line across the axis" knob
  (`hline`/`vline` + label, dashed). *Built (hline surfaced; vline available in `bar_spec`).*
- The bar's **values** come from the dropped data + chosen intensity — the owner's GraphPad numbers
  (~330 µV Control) reflect their own measurement/cohort, not a styling concern; the Selom extraction
  `D:\selom-data\erg-fig1e\erg_metrics_long.csv` reads ~208 µV at Group4. The styling LOOK is the deliverable.

## D11 — The styling is GENERIC, not ERG-locked (owner steer 2026-06-24)
The owner confirmed (with the 7 reference figures + "applies to all line graphs and bar graphs in
general") that this vocabulary is for **any** bar/line skill, not the ERG ones only. So the
primitives live in a new generic module **`app/backend/skills/_charts.py`** (the canonical home),
and the ERG skills are thin consumers. Any future categorical-bar or line skill calls the same
builder → one look + one param vocabulary everywhere. Also: **show/hide toggles** for *both* the
individual points (`points`) and the error bars (`show_error`).

## Built this session (bar half — GENERIC)
- **`skills/_charts.py`** (new generic module): `spread_stats(kind=sem|sd|ci95|minmax)` (n<2 guard,
  asymmetric minmax) · `rgba` · `sig_stars` · `compare_groups(welch|student|mannwhitney)` · `ERR_LABEL`
  · `jitter` · `resolve_stars` · `sig_brackets` · `ref_line` · **`bar_figure(...)`** — the generic mean
  ± spread bar (any categories): `error`, `show_error`, `points`, `bar_fill` (pattern/filled/open via
  `marker.pattern.shape`), `comparisons` → significance brackets (computed or overridden `(a,b[,ovr])`),
  `hline`/`vline` reference lines, per-category `legend`. `_erg` re-exports the stats primitives for back-compat.
- `erg_bwave_bar.bar_spec` is now a **thin wrapper** over `_charts.bar_figure` (supplies ERG colours/
  labels/`_PATTERN`/unit rounder). Default (filled·sem·no brackets/line/legend) byte-identical → golden unchanged.
- `run_real` param wiring + dynamic table header (`mean ± {SEM|SD|…}`); skill.json + FE `params.ts` controls.
- Tests: **`test_charts.py`** (generic, non-ERG categories) + `test_erg_units.py` (ERG wrapper: patterns/
  legend · error metric · significance + override · reference line · show/hide). Golden unchanged.
- **Rollout to other bar/line skills** = incremental: each categorical-bar skill (composition, abundance,
  dose-response, …) can drop in `_charts.bar_figure`; do it per-skill (each has its own golden) — not retrofitted in bulk this session.
- **TRACE / line half still pending** (`central=mean`, band/error/individual reps; flat-line band builder in
  `_charts`) — gated on C6 for real n (one .iwxdata = one eye); the `_tracegrid` overlay hook (M3) is ready.

Sibling of `docs/erg-module/spec.md` + `docs/diagnosys-erg/spec.md`. Applies to `erg_traces` (the grid)
and `erg_bwave_bar` (the amplitude bar); the primitives are generic (reusable by any future line/bar skill).

## What

Today `erg_bwave_bar` already draws **mean ± SEM + jittered eyes**, and `erg_intensity_response` already
draws **mean lines + per-point SEM error bars**. `erg_traces` draws **one representative trace** per
(condition × intensity) with **no aggregation or spread**. This feature unifies a **single orthogonal
styling vocabulary** across the bar and the traces:

- **Central tendency** — `representative` (today's single exemplar trace; default, back-compat) **or `mean`**
  (average the n recordings at each x). For the bar, the bar height is already the mean.
- **Spread** — show it as a **shaded band**, **per-point error bars**, **individual replicate traces**, or
  **none** (and `both` = band + error bars). Bars use error bars (+ point overlay).
- **Error metric** — **SEM** (owner default) | **SD** | `ci95` | `minmax`.
- **Individual data points** — overlay each eye/animal (n shown), already on the bar; add the trace analog
  (faint replicate lines).
- **Styling** — band opacity, error-bar cap width / line weight, **draw-every-Nth error bar** (de-clutter dense
  series), boundary-line style (none/solid/dashed), bar fill (filled/open).

### The 7 reference figures → the vocabulary
| # | Figure | central | spread | error | extras |
|---|---|---|---|---|---|
| 1 | blue mean line + gray filled band | mean | band | (sd/sem) | opaque-ish gray band, boundaries hidden |
| 2 | mean line + translucent band + per-point error bars + dashed boundaries + markers | mean | both | sem/sd | `boundary_lines=dashed`, `lines+markers` |
| 3 | OriginLab: error bars at every point vs "draw only N" (N=50) + cap/line width/color/transparency | mean | error_bars | sem/sd | `error_every`, cap width, color, alpha |
| 4 | 3 mean lines, each its own translucent ±band + legend | mean | band | sem/sd | one band block per condition, shared legend |
| 5 | open/white bars + jittered points + SEM caps | (mean bar) | error_bars | sem | `bar_fill=open`, `show_points` |
| 6 | filled red bars + jittered points + SEM caps | (mean bar) | error_bars | sem | `bar_fill=filled`, `show_points` |
| 7 | grouped multi-series bars + points + error bars + significance brackets | (mean bar) | error_bars | sem/sd | grouped, `sig_brackets` (phase 2) |

## Recommended param vocabulary (defaults + guardrails)

```
central:        representative | mean            # traces default: representative (back-compat). Bar: always mean.
spread:         none | band | error_bars | individual | both
                                                 # traces default: band ; bar default: error_bars
error:          sem | sd | ci95 | minmax         # default: sem (owner's words). ci95 = most defensible (noted).
show_points:    bool                             # bar default: true (reviewer ask) ; traces default: false
error_every:    int >= 1                         # 1 = every point ; >1 thins dense traces (Origin "Skip each group of N")
boundary_lines: none | solid | dashed            # band edge ; default none (dashed = style #2)
band_alpha:     0..1                             # default 0.25
cap_width:      px                               # default 6 (bar) / 3 (line)  — matches shipped skills
line_width:     px                               # whisker weight ; default 1.2 (bar) / 1 (line)
bar_fill:       filled | open                    # default filled ; open = white fill + dark outline (#5)
jitter_width:   0..1 of slot                     # default 0.34 (matches _erg/_jitter)
sig_brackets:   [{groupA, groupB, p}]            # PHASE 2 (optional) ; renders shapes + annotations (#7)
```
Guardrails: `error in {sem,ci95}` needs n≥2 (else degrade to points-only + a table note — never a NaN/zero
bar); `central=representative` disables `spread`; `spread=none` ignores `error`/`error_every`; never mix SD
and SEM on one figure (one `error` per figure); always caption what the band/bar is + state n.

## Design — shared primitives (build once, reuse)

1. **`_erg.spread_stats(values, kind)`** — generalize `summary_stats` to return `{mean, err, n}` for
   `kind ∈ {sem, sd, ci95, minmax}` (CI95 via the t-quantile, not a hardcoded 1.96; `minmax` → asymmetric
   `(lo, hi)`). n<2 guard built in.
2. **`_band` builder** (next to `bar_spec`) — emits the **3-trace `fill:"tonexty"`** band block per series:
   lower (invisible) → mean (`fill:"tonexty"`) → upper (`fill:"tonexty"`), `fillcolor=rgba(base,band_alpha)`,
   `showlegend:false` on the bounds + shared `legendgroup` (one legend entry). Boundary lines via
   `line.width/dash`. Use the single-trace `fill:"toself"` variant only when a series has internal NaN gaps.
3. **`_tracegrid` per-panel overlays** — extend `grid_spec` so a panel dict may carry optional
   `band={x,lower,upper}`, `error={x,y,err,every}`, `markers=[{x,y,label}]`, and `extra_lines=[…]` (faint
   replicates). Emits the extra traces against the panel's own axis. **This same overlay hook delivers M3
   (A): the N1/P1 marker dots on the flicker grid** — build it once, both features consume it.
4. **`_erg.rgba(hexcolor, alpha)`** — server-side colour→`rgba()` for `fillcolor` / open-bar fills (Plotly
   won't derive a translucent fill from the line colour).
5. **`error_y` every-Nth** — build `array = [e if i % every == 0 else None for i,e in …]` (null, not 0, so
   skipped points draw nothing). Origin "Skip each group of N" semantics.

### erg_traces changes
- Add `central` (representative|mean). When `mean`: per (condition × intensity), average the n eye/animal
  traces at each `time_ms` → mean trace; compute the band/error from `spread_stats` across those n at each t.
- `spread` (band|error_bars|individual|both|none) → drives the panel overlays above. `individual` overlays
  the n raw eye traces faintly (alpha ≈ 0.18) behind the mean.
- Keep `representative` as the default → today's goldens unchanged.

### erg_bwave_bar changes (straightforward)
- Add `error` (sem|sd|ci95|minmax; default sem) → which array feeds `error_y`. `points` already exists.
- Add `bar_fill` (filled|open). Keep stub/golden byte-identical when `error=sem`, `bar_fill=filled`.
- `sig_brackets` = **phase 2** (shapes+annotations; needs a stats input — out of scope for the first cut).

## Decisions
- **D1 — One vocabulary, two skills.** Same param names on bar + traces; primitives generic. Alt: per-skill
  ad-hoc params (rejected — inconsistent, doesn't compound).
- **D2 — Default `error=sem`** per the owner's words ("SEM or standard deviation"); expose SD + (bonus)
  CI95/minmax. Note for the owner: CI95 is the most defensible for precision (GraphPad/seaborn lean CI), SD
  for "show the variability." We default to SEM but make the others one click away.
- **D3 — `central` defaults to `representative` on traces** (back-compat; goldens unchanged). `mean` is opt-in.
- **D4 — Band via 3-trace `tonexty`** (Plotly's canonical continuous-error-band pattern; round-trips cleanly
  in the editor since each boundary stays a real x/y series). `toself` only for NaN-gapped series.
- **D5 — Reuse the deterministic `_jitter`** (no RNG → golden-stable). Same for all point overlays.
- **D6 — The `_tracegrid` overlay hook is shared with M3 (A).** Build it once.

## Dependencies / sequencing
- **Trace `central=mean` + spread is most meaningful with multi-file ingest (C6 / M4):** one Diagnosys `.TXT`
  = one animal = 2 eyes (n=2). Cross-animal means (n = many, like the reference figures) need C6's
  multi-file → one multi-condition table. So land **C6 before (or with)** the trace-mean feature for real n;
  the bar's SEM/SD toggle + the primitives can land independently.
- **Shares the `_tracegrid` overlay extension with M3 (A).** Suggest: build the overlay hook in M3, then this
  feature consumes it.

## Invariants
- FE-rendered spec stays pure `{data, layout}`; `spec["table"]` popped before theming.
- Determinism: no RNG (jitter is deterministic); goldens stable.
- n<2 never yields a NaN/zero error bar — degrade to points + a table note.
- One legend entry per series (legendgroup + showlegend:false on helper traces).
- Every figure captions the spread (SEM/SD/CI/range) + states n.

## Testing
- `spread_stats` units: SEM=SD/√n, CI95 uses t-quantile, minmax asymmetric, n<2 guard.
- `_band` 3-trace order + `rgba` alpha; `error_every` nulls skipped points.
- erg_traces `central=mean` on a synthetic multi-eye fixture → mean + band shape; `representative` byte-identical.
- erg_bwave_bar `error=sd` vs `sem` differ correctly; `error=sem,bar_fill=filled` byte-identical to today.
- Live-verify on the real Diagnosys export (mean trace grid with band; bar with SD).

## Out of scope (first cut)
- Significance brackets / p-value stars (#7) — phase 2 (a stats input + bracket layout engine).
- Grouped/multi-series bars (#7) — phase 2 (needs explicit numeric x positions for point alignment).
- Curve fitting beyond the existing Naka-Rushton.

## Build plan (next session)
1. `_erg.spread_stats` + `_erg.rgba` (+ unit tests).
2. `_tracegrid` per-panel overlay hook (band / error / markers / extra_lines) — shared with M3 (A).
3. `_band` builder; wire `erg_traces` `central`/`spread`/`error`/`error_every`/styling.
4. `erg_bwave_bar` `error` (sem|sd|…) + `bar_fill`.
5. FE params overlay (params.ts) for the new knobs on both cards; seed summaries.
6. Live-verify on the real export (pairs with C6 for real n on the trace means).
