# Mock Fig 1E — scotopic ERG b-wave data + trace grid

> ## ⚠️ THIS IS MOCK DATA
> The b-wave numbers are **simulated**. The trace figure uses **real waveform shapes**, but
> their assignment to conditions and their amplitudes follow the simulated table — so the
> figure as a whole is **not experimental measurement** either. None of this may appear in a
> manuscript, figure, or analysis that reports real results.

Generated 2026-08-02. Shape is faithful to the printed Fig 1E — condition set, the 7-point
scotopic intensity ladder, per-group n, realistic eye-to-eye spread.

## What differs from the printed Fig 1E

1. **AAV8-CMV-GFP is pulled down to a clean null.** In the real extraction it reads ~42 µV at
   1.0 log — level with Untreated, more residual signal than a GFP-only control should show.
   Here it is the lowest of the six.
2. **AAV8-RK-PDE6B shows partial rescue**, significantly above every null arm.
3. **The two rescue arms are separated only *slightly*** (p ≈ 0.002–0.004, `**`), so they read
   as a graded effect rather than two unrelated results. The gap was widened on 2026-08-06 so
   the difference is legible in the trace grid, not only in the summary table.
4. **Every rd10 arm is silent until flash 1.0.** Only the WT Control responds to the dim
   flashes; the treated and null arms sit at the noise floor below 1.0 and climb sharply
   through it, matching the real recordings. This is enforced, not hoped for — see the
   threshold check below.

## b-wave at 1.0 log cd·s/m²

| Condition | n (eyes) | mean (µV) | SEM (µV) |
|---|---:|---:|---:|
| Control | 8 | 234.51 | 8.48 |
| Untreated | 4 | 12.32 | 1.39 |
| AAV8-RK-PDE6B | 7 | 45.56 | 7.28 |
| AAV8-RK-GFP-polyA-stuffer | 3 | 10.64 | 2.24 |
| AAV8-CMV-GFP | 4 | 8.12 | 1.48 |
| AAV8-RK-PDE6B-3UTR | 4 | 126.81 | 12.18 |

## b-wave at 1.9 log cd·s/m²

| Condition | n (eyes) | mean (µV) | SEM (µV) |
|---|---:|---:|---:|
| Control | 8 | 234.65 | 7.47 |
| Untreated | 4 | 30.56 | 3.24 |
| AAV8-RK-PDE6B | 7 | 59.36 | 6.33 |
| AAV8-RK-GFP-polyA-stuffer | 3 | 26.41 | 3.52 |
| AAV8-CMV-GFP | 4 | 22.94 | 1.9 |
| AAV8-RK-PDE6B-3UTR | 4 | 165.99 | 16.06 |

30 eyes × 7 intensities = **210 individual data points**. Every eye has all 7 intensities —
no gaps — so mean and SEM are fully recomputable from the raw points.

### Significance (Welch's t-test)

Checked and reported at **both** 1.0 and 1.9 log. Both rescue arms clear every null arm; the
3'UTR-vs-RK-PDE6B gap is `**` at both. Full numbers in `mock_fig1e_bwave_stats.csv`.

The Welch implementation is pure stdlib (`statistics` has no t-distribution) and was validated
against `scipy.stats.ttest_ind(equal_var=False)` — agreement to 1.5e-15 relative.

## The n = 3 variant — `n3/`

Same six conditions with **every group at n = 3** and one uniform spread (CV 0.14). Same file
names, plus its own trace figure.

| Condition | n | mean @1.0 (µV) | SEM |
|---|---:|---:|---:|
| Control | 3 | 230.69 | 17.27 |
| Untreated | 3 | 12.75 | 1.4 |
| AAV8-RK-PDE6B | 3 | 44.05 | 1.04 |
| AAV8-RK-GFP-polyA-stuffer | 3 | 10.65 | 2.26 |
| AAV8-CMV-GFP | 3 | 8.75 | 2.55 |
| AAV8-RK-PDE6B-3UTR | 3 | 127.13 | 8.06 |

| Condition | n | mean @1.9 (µV) | SEM |
|---|---:|---:|---:|
| Control | 3 | 238.79 | 17.69 |
| Untreated | 3 | 30.32 | 2.29 |
| AAV8-RK-PDE6B | 3 | 61.82 | 5.48 |
| AAV8-RK-GFP-polyA-stuffer | 3 | 27.19 | 2.82 |
| AAV8-CMV-GFP | 3 | 23.44 | 2.4 |
| AAV8-RK-PDE6B-3UTR | 3 | 159.13 | 12.27 |
## Files

| File | What it is |
|---|---|
| `mock_fig1e_bwave_long.csv` | **Every individual data point.** One row per eye × intensity (210 rows). Tidy — the canonical file, and the one to compute your own mean/SEM from. |
| `mock_fig1e_bwave_points_wide.csv` | The same raw points as replicates-in-columns (rows = intensity, one column per eye, grouped by condition). Pastes straight into GraphPad/Excel so the tool computes mean + SEM itself. Two header rows — for pasting, not for parsing. |
| `mock_fig1e_bwave_summary.csv` | Pre-computed n / mean / SD / SEM per condition × intensity, if you want it done already. |
| `mock_fig1e_bwave_wide.csv` | Summary as intensity-per-row with mean/SEM/n columns per condition. |
| `mock_fig1e_bwave_stats.csv` | Welch t-tests at the reference intensity: rescue arms vs each null arm, and the two rescue arms against each other. |
| `mock_fig1e_waveforms_long.csv` | **The trace data, plottable.** Every sample behind the trace figure: 6 conditions × 7 intensities × 0…260 ms. Columns: `condition`, `intensity_log_cd_s_m2`, `time_ms`, `voltage_uv`. |
| `mock_fig1e_traces.jpg` | The rendered trace grid. |
| `mock_fig1e_awave_summary.csv` | **a-wave per condition x intensity**, measured off the drawn traces: `a_wave_uv` (positive magnitude, baseline to trough), `b_peak_uv_trace`, `a_over_b`, and which of the two the value came from. Added 2026-08-03 — see the caveats below before plotting it. |
| `generate_mock_fig1e.py` | Generates the b-wave + stats CSVs, and self-checks before writing. Pure standard library. |
| `render_mock_fig1e_traces.py` | Renders the trace grid + waveform CSV from the real waveform library. Needs matplotlib + numpy + the backend on `PYTHONPATH`. |

## The a-wave table — read this before plotting it

`mock_fig1e_awave_summary.csv` exists so the a-wave the figure now shows is available as numbers.
It is **not** a second sample, and it is not interchangeable with the b-wave tables:

- **Different granularity.** The b-wave tables are simulated **per eye** (30 eyes x 7 intensities)
  and carry n / mean / SEM. This one is measured from the **one representative trace per
  condition** that the figure draws, so it has no n and no SEM. That is why it is a separate file
  rather than extra columns — merging them would imply per-eye a-wave measurements that do not
  exist.
- **`b_peak_uv_trace` is not the group mean.** It is the raw maximum of that representative trace,
  so it rides on oscillatory potentials and noise and sits a little off the b-wave table's mean.
  It is there to make `a_over_b` self-contained. **The b-wave tables remain the amplitude source
  of record** — use them for anything quantitative.
- **The rd10 values are a designed ceiling, not a simulation.** Every non-Control arm is capped at
  `a/b <= 0.18` (see above), so those rows express a constraint the figure imposes. The Control
  column is its source eye untouched. The `a_wave_source` column states which, per row.

Everything here is **scotopic** — the whole Fig 1E series is the dark-adapted rod-driven intensity
ladder (-1.7 to +3.1 log cd·s/m2). There is no photopic/light-adapted data in this set.

If a per-eye a-wave with n and SEM is ever wanted, the real source (`erg_metrics_long.csv`) does
carry `a_wave_uv` per eye, so the generator could simulate one the same way it does the b-wave.
Not built — nobody has asked for it.

## Plotting intensity vs b-wave amplitude

x = `intensity_log_cd_s_m2`, y = `b_wave_uv`, one series per `condition`.

From the raw points (`mock_fig1e_bwave_long.csv`), grouping by condition × intensity and
taking mean ± SEM reproduces `mock_fig1e_bwave_summary.csv` exactly — verified, max deviation
0.005 µV (rounding only).

## Regenerating

```bash
# b-wave tables (stdlib only)
python3 generate_mock_fig1e.py

# trace grid + waveform table (needs matplotlib/numpy + the real waveform source)
PYTHONPATH=../../../../app/backend ../../../../app/backend/.venv/bin/python \
    render_mock_fig1e_traces.py

# the balanced n=3 variant
python3 generate_mock_fig1e.py --n-eyes 3 --cv 0.14 --outdir n3
PYTHONPATH=../../../../app/backend ../../../../app/backend/.venv/bin/python \
    render_mock_fig1e_traces.py --outdir n3
```

The traces are derived from the b-wave CSV, so regenerating the numbers and re-running the
renderer keeps the trace figure and the intensity-response table telling the same story —
they cannot drift apart.

Deterministic: the same `--seed` (default 20260802) reproduces the CSVs byte-for-byte.

**To retune a condition,** edit the `CONDITIONS` table at the top of
`generate_mock_fig1e.py` — it is the single source of truth for the group means. The
`target_at_log1` comment on each row is the b-wave that curve yields at the reference
intensity, so a group can be dialled by eye without re-deriving Naka-Rushton parameters.
Re-run the renderer afterwards so the traces follow the new numbers.

### The generator self-checks before it writes

`generate_mock_fig1e.py` asserts the biology the figure claims and **exits non-zero without
writing** if a retune breaks it:

- Control above the 3'UTR arm at every intensity
- 3'UTR above AAV8-RK-PDE6B **from flash 1.0 up** (below the threshold both arms sit at the
  noise floor, where noise decides the order — so nothing is asserted there)
- AAV8-RK-PDE6B clearly above every null arm, also **from flash 1.0 up**; below that all
  groups sit at the noise floor and none separate
- AAV8-CMV-GFP at or below Untreated at the reference intensity — the requested change
- every condition rising across the intensity ladder
- both rescue arms beating every null arm **significantly** (Welch, p < 0.05), at 1.0 **and** 1.9
- every rd10 arm below 8 µV at all flashes dimmer than 1.0 — the threshold; only the WT
  Control is exempt
- 3'UTR beating RK-PDE6B significantly but only **slightly** — p inside a band
  (0.0005, 0.05). The lower bound is deliberate: too small a p means the two rescue arms have
  been drawn too far apart to read as a graded effect.

Differences smaller than a 3 µV noise band are not treated as failures: the three null groups
are *designed* to be indistinguishable, and the top two flashes sit only 0.3 log apart on a
saturated curve, so a strict ordering there would assert something the biology does not
support.

## Model

Per condition, a Naka-Rushton saturating intensity-response curve

```
V(I) = Vmax / (1 + 10^(n · (logK − I)))
```

Each eye draws its own Vmax scale factor (lognormal, per-condition CV) and a logK jitter,
then per-measurement recording noise is added as `0.5 µV + 2% of amplitude`.

Two modelling choices worth knowing, both made to keep the plot honest:

- **Per-eye draws are centred within each group.** At n=3–8, raw sampling error moved a group
  mean by tens of µV — enough to swamp the between-condition differences the figure is about.
  Centring pins each group mean to its target while leaving eye-to-eye spread intact.
- **Noise is signal-proportional, not flat.** A flat term large enough to look realistic on a
  210 µV Control trace completely swamped the sub-µV dim end of a null curve, which made
  group-mean series *fall* with increasing intensity. Scaling with amplitude keeps the dim end
  quiet while still giving the bright end believable scatter.

## Trace figure

`mock_fig1e_traces.jpg` — 7 intensities (rows, dimmest at top) × 6 conditions (columns), each
panel axis-less with one shared 200 µV × 100 ms scale bar, per the ERG module spec (R21/R3).

### The traces use real waveforms

An earlier version synthesised each waveform from a-wave/b-wave lobes plus a sine burst. It
was clean, and it looked obviously fabricated — every panel had the same idealised morphology
and identical Gaussian noise. This version uses the **real decoded recordings** as the shape
source, so panels carry genuine ERG morphology: real oscillatory potentials, real timing
jitter, real recording noise.

How a panel is built:

1. Load the real representative waveforms, **hum-notch** them (`skills/_erg.clean_trace`), and
   measure each with the validated R17 landmark method. The notch is not optional: the raw
   decoded traces carry heavy 50/100/150/163 Hz mains and instrument hum that renders as pure
   oscillation with no recognisable waveform.
2. Give each condition **one real source eye**, and draw that whole column from it — so the
   column shows a single waveform growing with flash intensity, as a real series does. (Matching
   each panel independently to the closest-amplitude trace was tried first; it produced columns
   whose morphology changed row to row, which is not what an intensity series looks like.)
3. Scale each panel onto its simulated target amplitude. **The threshold comes from this gain**,
   not from the source: below flash 1.0 the rd10 targets are near zero, so those panels flatten
   out regardless of what the source eye did.
4. Where the gain shrinks a trace, add real recording noise back in proportion, so scaled-down
   panels keep an authentic noise floor instead of going implausibly smooth.
5. **Cap the a-wave on every rd10 arm** (see below).

Source eyes are declared in `SOURCE_EYE` in the renderer. Five columns use the eye actually
recorded for that condition. **AAV8-RK-PDE6B is the exception** and uses the WT eye scaled
down: its own recording (256_RE) is noise-dominated with no clean b-wave to scale, so sourcing
from it rendered the partial-rescue column flat — the opposite of what the figure shows. It
stays visually distinct from the 3'UTR column, which keeps its own eye.

### The a-wave is capped on the rd10 arms

Gaining a source trace onto a target is a **uniform** scale, so a panel keeps its source eye's
a:b morphology. Borrowing the WT eye for AAV8-RK-PDE6B therefore also borrowed a full healthy
**a-wave** — a deep trough saying the photoreceptors came back. They do not: the a-wave is
photoreceptor mass, the b-wave is downstream signalling, and a rescued rd10 retina recovers the
b-wave far more than the a-wave. Corrected 2026-08-03 on the owner's observation.

Measured on the real recordings — trough depth over b-wave peak, which is what a reader's eye
actually reads (deliberately **not** `landmarks()['a_wave_uv']`: on these filtered traces that
returns ~18 µV where the visible trough is ~180 µV, so it is the wrong instrument here):

| Eye | Arm | 1.0 | 1.9 | 2.8 |
|---|---|---:|---:|---:|
| `633_LE` | Control (WT) | 0.90 | 0.98 | 0.90 |
| `257_RE` | RK-PDE6B-3UTR — a real rescued eye | 0.15 | 0.12 | 0.38 |

A 6–7× difference that a uniform gain cannot express. `AWAVE_MAX_RATIO = 0.18` is therefore a
**ceiling, not a target**, set just above the real rescued eye's own ratio: an authentic rd10
trace passes through untouched and only a borrowed WT trough is pulled down. Only the negative
samples before the b-wave peak are scaled, so the b-wave is unchanged and the trace stays
continuous. At 1 month post-treatment a *slight* a-wave is expected, which is what 0.18 leaves.

`check_awave()` **refuses to write the figure** if any rd10 arm exceeds the cap, or if the
Control's a-wave ever falls to the treated arms' level — that contrast is the point of the panel.

**The flash threshold is unchanged and was already correct**: only the WT Control responds below
flash 1.0; every rd10 arm sits at the noise floor until +1.0 and climbs through it. That comes
from the gain in step 3, not from the a-wave cap.

### Styling

Reworked because the first pass was hard to read:

- **No grey.** The old palette put AAV8-RK-PDE6B *and* the polyA-stuffer on the same grey
  (`#9aa3ad`), so the partial-rescue arm — the one this figure is about — was the least
  visible thing on it. Palette is now Okabe-Ito, colourblind-safe, one distinct hue per
  condition.
- **Thicker lines** (2.1 pt), so traces hold up when the figure is scaled down.
- **Rows packed tight** — panels touch, and the panel height was cut so the stacked traces sit
  as close as a shared vertical scale allows.
- **Clearer labels** — condition headers bold and **black**; intensity labels aligned to each
  row's trace baseline rather than the panel centre. (The headers were tinted to match their
  trace until 2026-08-03; the traces already carry the colour coding, so tinting the labels too
  was redundant.)
- **No on-figure title.** The panel is laid out with its legend underneath, so a title on the
  artwork only has to be cropped off later (owner, 2026-08-03). The MOCK provenance does not go
  with it: the caption under the figure still states that the amplitudes are simulated, and this
  README carries the full warning.
- **Scale bar moved out of the grid** into its own matched-scale axes below it; inside the
  bottom-left panel the brightest Control a-wave ran straight through it. It sits closer to the
  grid than it first did (`SCALEBAR_DROP`) — its axes HEIGHT must stay equal to a panel's, since
  that equality is what makes 200 µV render at exactly the panel scale, so only its position is
  tunable.
