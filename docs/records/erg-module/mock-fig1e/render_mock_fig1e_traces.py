#!/usr/bin/env python3
"""Render the Fig 1E representative-trace grid (7 intensities x 6 conditions).

    ============================================================
    THIS FIGURE IS A MOCK. The waveform SHAPES are real recordings,
    but their assignment to conditions and their amplitudes follow
    the simulated b-wave table -- so the figure as a whole is NOT
    experimental measurement. Never report it as a real result.
    ============================================================

Why real shapes: an earlier version synthesised each waveform from a-wave/b-wave lobes plus a
sine burst. It was clean, and it looked obviously fabricated -- every panel had the same
idealised morphology and identical Gaussian noise. This version instead uses the REAL decoded
traces as a shape library, so the panels carry genuine ERG morphology: real oscillatory
potentials, real timing jitter, real recording noise.

How a panel is built:
  1. Load the real representative waveforms (6 eyes x 7 intensities), hum-notch them, and
     measure each one's b-wave with the repo's validated R17 landmark method.
  2. Give each condition ONE real source eye, and draw every panel in that column from it.
     This matters: an earlier version matched each panel independently to whichever real
     trace was closest in amplitude, which produced columns whose morphology changed from
     row to row -- not what an intensity series looks like. One eye per column means the
     column shows a single waveform growing with flash intensity, as a real series does.
  3. Scale each panel by the gain that lands it on the simulated target amplitude. The
     THRESHOLD comes from this gain, not from the source: below flash 1.0 the rd10 targets
     are near zero, so those panels flatten out regardless of what the source eye did.
     Where the source trace is too flat to carry a large target, fall back to the strongest
     trace from the same eye rather than amplifying noise.
  4. Where the gain shrinks a trace, add back real recording noise (sampled from the quiet
     tail of the real recordings) in proportion, so scaled-down panels keep an authentic
     noise floor instead of going implausibly smooth.

Style: Okabe-Ito palette, NO grey (the original put AAV8-RK-PDE6B and the polyA-stuffer on the
same grey, hiding the partial-rescue arm), thick lines, rows packed tight, labels aligned to
each trace's baseline, shared scale bar in its own matched-scale axes below the grid.

Writes THREE figures from one pass over the same panels (2026-08-06): the canonical seven-flash
grid, an expanded-scale variant that lets the WT Control clip so the two rescue arms separate,
and a single-flash (+1.9 log) variant that keeps the grid's scale but gives each trace ~3.5x the
panel height. Each figure gets its own waveform + a-wave tables.

Usage:  render_mock_fig1e_traces.py [--outdir DIR] [--dpi N] [--real-src PATH]
Needs matplotlib + numpy + the repo's skills package, e.g.:
    PYTHONPATH=../../../../app/backend ../../../../app/backend/.venv/bin/python \\
        render_mock_fig1e_traces.py
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REAL_SRC = Path("/home/deploy/migration/selom-migration-staging/selom-data/erg-fig1e"
                "/erg_waveforms_long.csv")

INTENSITIES_LOG = [-1.7, -0.8, 0.1, 1.0, 1.9, 2.8, 3.1]

CONDITION_ORDER = [
    "Control",
    "Untreated",
    "AAV8-RK-PDE6B",
    "AAV8-RK-GFP-polyA-stuffer",
    "AAV8-CMV-GFP",
    "AAV8-RK-PDE6B-3UTR",
]

COL_LABELS = {
    "Control": "Control",
    "Untreated": "Untreated",
    "AAV8-RK-PDE6B": "AAV8-RK-PDE6B",
    "AAV8-RK-GFP-polyA-stuffer": "AAV8-RK-GFP\npolyA stuffer",
    "AAV8-CMV-GFP": "AAV8-CMV-GFP",
    "AAV8-RK-PDE6B-3UTR": "AAV8-RK-PDE6B\n3'UTR",
}

# Okabe-Ito colourblind-safe palette -- NO GREY (see module docstring).
COLORS = {
    "Control": "#000000",                    # black      -- WT reference
    "Untreated": "#0072B2",                  # blue       -- rd10 disease baseline
    "AAV8-RK-PDE6B": "#009E73",              # green      -- partial rescue (was grey)
    "AAV8-RK-GFP-polyA-stuffer": "#CC79A7",  # pink       -- null (was grey)
    "AAV8-CMV-GFP": "#E69F00",               # amber      -- null
    "AAV8-RK-PDE6B-3UTR": "#D55E00",         # vermillion -- best rescue
}

LINE_WIDTH = 2.1
ROW_GAP = 0.0
COL_GAP = 0.10
FIG_SIZE = (13.5, 7.8)
HEADER_SIZE = 11
#: Column headers are black rather than the trace colour: the traces themselves already carry
#: the colour coding, so tinting the labels too was redundant (owner, 2026-08-03).
HEADER_COLOR = "#000000"
INTENSITY_SIZE = 10
SCALEBAR_UV = 200
SCALEBAR_MS = 100
#: How far the scale-bar axes sits below the last row, as a fraction of one panel's height.
#: Its HEIGHT must stay equal to a panel's (see render) so 200 µV is drawn at exactly the panel
#: scale — only its position is tunable, which is what this is.
SCALEBAR_DROP = 0.70

#: The zoom variant expands the y-window until the tallest arm in this list fills the panel,
#: rather than by a hand-picked factor. Conditions NOT listed may run off-scale and are clipped.
#:
#: ⚑ A fixed factor was tried first (2.6x) and was wrong in the way that matters: it clipped the
#: 3'UTR arm too, and the 3'UTR arm is the REFERENCE the comparison is made against. Cropping the
#: thing you are measuring against turns "PDE6B is smaller" into "both hit the ceiling". Deriving
#: the window from the data cannot make that mistake -- only the WT Control, which is explicitly
#: excluded, is allowed off the top.
ZOOM_FIT_EXCLUDE = ("Control",)
#: How far BELOW the baseline the zoomed window reaches, as a fraction of its height above.
#:
#: The two sides are treated differently on purpose. The quantity being compared is the b-wave,
#: a POSITIVE deflection, so the top of the window is fitted to the tallest surviving sample and
#: nothing being read ever clips. The bottom is a display choice: the deep negative excursions on
#: the brightest flashes are a-wave and oscillatory potentials, not the amplitude in question, so
#: they are allowed off the bottom to buy magnification. 0.45 is about the a:b ratio a healthy
#: trace shows, so the window still looks like an ERG rather than a cropped bar.
ZOOM_TROUGH_FRAC = 0.45
#: The one flash the single-row variant draws: the working intensity for this figure, and the
#: brightest one at which every arm is still on-scale in the b-wave table.
FOCUS_LOG_I = 1.9
#: Taller canvas for the single-row variant -- the whole point is vertical room per trace.
SINGLE_ROW_FIG_SIZE = (13.5, 4.4)
#: Vertical room reserved above the grid for the column headers, in INCHES. Two of them wrap to
#: two lines, and on a short canvas the 0.935 top margin cropped the first line clean off -- so
#: the header block is reserved in absolute units and the top margin derived from the canvas
#: height, not the other way round.
HEADER_SPACE_IN = 0.62

T_MAX_MS = 260.0        # trim the long quiet tail; the response is over well before this
NOISE_TAIL_MS = 220.0   # samples past this are treated as recording noise
GAIN_CLAMP = (0.05, 3.0)


#: One real source eye per condition -- each column is drawn from the eye actually recorded
#: for that condition, so the morphology on screen belongs to the arm it is labelled with.
SOURCE_EYE = {
    "Control": "633_LE",
    "Untreated": "255_LE",
    # NOT this arm's own eye (256_RE): that recording is noise-dominated and has no clean
    # b-wave to scale, so the partial-rescue column rendered flat -- the opposite of what
    # the figure is meant to show. Borrowing the WT eye costs one thing, which AWAVE_MAX_RATIO
    # then pays for: a uniform gain would also carry the WT's full a-wave into this column,
    # and a rescued rd10 retina does NOT give a smaller version of a normal response -- it
    # gives a b-wave without the matching photoreceptor trough.
    "AAV8-RK-PDE6B": "633_LE",
    "AAV8-RK-GFP-polyA-stuffer": "248_LE",
    "AAV8-CMV-GFP": "257_LE",
    "AAV8-RK-PDE6B-3UTR": "257_RE",
}

#: Below this target the panel is a non-response: keep the source's own flat trace and let
#: the real noise floor carry it, rather than scaling a b-wave down into a sliver.
FLAT_TARGET_UV = 6.0

#: A source trace must carry at least this fraction of the target on its own; below that we
#: switch to the same eye's strongest trace instead of amplifying its noise.
MIN_SOURCE_FRACTION = 0.45

#: Deepest the pre-b-wave trough (the a-wave) may go, as a fraction of that panel's b-wave peak.
#:
#: WHY THIS EXISTS. Gaining a source trace onto a target is a UNIFORM scale, so the panel keeps
#: its source eye's a:b morphology. That is fine when the source is the arm's own eye, and wrong
#: when it is borrowed: `AAV8-RK-PDE6B` is drawn from the WT Control eye (see SOURCE_EYE), so it
#: inherited a full healthy a-wave — a deep trough that says the photoreceptors came back.
#:
#: They do not. The a-wave is photoreceptor mass; the b-wave is downstream signalling. A rescued
#: rd10 retina recovers b-wave far more than a-wave, so a treated trace should show a b-wave with
#: a nearly flat leading edge. Measured on the real recordings, trough-to-peak:
#:     633_LE  WT Control      0.90 / 0.98 / 0.90  at 1.0 / 1.9 / 2.8 log
#:     257_RE  RK-PDE6B-3UTR   0.15 / 0.12 / 0.38  (a real rescued eye, its own trace)
#: — a 6-7x difference that a uniform gain cannot express.
#:
#: The cap is set just above the real rescued eye's own ratio, so it is a CEILING and not a
#: target: an authentic rd10 trace passes through untouched and only a borrowed WT trough is
#: pulled down. At 1 month post-treatment a slight a-wave is expected (owner, 2026-08-03), which
#: is what ~0.18 leaves. `None` = leave this condition's own morphology alone.
AWAVE_MAX_RATIO = 0.18
AWAVE_RATIO_BY_COND = {"Control": None}


def load_real_library(src: Path):
    """Real decoded waveforms -> {sample_id: {intensity: (t, y, b_wave)}}.

    Measured with the repo's own R17 landmark routine so the amplitudes here are on the same
    footing as the b-wave table this figure is matched against.
    """
    try:
        from skills import _erg
    except ImportError:  # pragma: no cover - operator error, message is the point
        sys.exit("Needs the backend on PYTHONPATH, e.g.\n"
                 "  PYTHONPATH=../../../../app/backend "
                 "../../../../app/backend/.venv/bin/python " + Path(__file__).name)

    by_key: dict[tuple, list] = {}
    for r in csv.DictReader(src.open(encoding="utf-8")):
        by_key.setdefault((r["sample_id"], float(r["intensity_log_cd_s_m2"])), []).append(
            (float(r["time_ms"]), float(r["voltage_uv"])))

    lib: dict[str, dict[float, tuple]] = {}
    for (sid, x_log), pts in by_key.items():
        pts.sort()
        t = np.array([p[0] for p in pts])
        y = np.array([p[1] for p in pts])
        keep = t <= T_MAX_MS
        t, y = t[keep], y[keep]
        # Hum-notch before anything else. The raw decoded traces carry heavy mains and
        # instrument hum (50/100/150/163 Hz) that visually swamps the ERG -- rendering them
        # untouched produced a grid of pure oscillation with no recognisable waveform.
        # clean_trace strips those discrete lines while preserving the oscillatory
        # potentials. The b-wave is then measured on the SAME cleaned trace that gets drawn,
        # so the amplitude match below is self-consistent.
        y = np.array(_erg.clean_trace(y))
        y = y - y[:25].mean()          # baseline-correct on the first few ms
        b = _erg.landmarks(t, y)["b_wave_uv"]
        lib.setdefault(sid, {})[x_log] = (t, y, float(b))
    return lib


def noise_pool(lib) -> np.ndarray:
    """Real recording noise, taken from the quiet tail of every real trace."""
    segs = [y[t > NOISE_TAIL_MS] for eye in lib.values() for _t, y, _b in [eye[k] for k in eye]
            for t in [_t]]
    pool = np.concatenate([s - s.mean() for s in segs if len(s)])
    return pool


def build_panel(target_uv: float, cond: str, x_log: float, lib, pool, rng):
    """One panel: this condition's source eye at this intensity, gained onto the target."""
    eye = lib[SOURCE_EYE[cond]]
    t, y, measured = eye[x_log]

    if target_uv >= FLAT_TARGET_UV and measured < MIN_SOURCE_FRACTION * target_uv:
        # This eye's trace at this flash is too flat to carry the target; amplifying it
        # would just magnify noise. Use the same eye's strongest recorded response instead,
        # so the morphology still belongs to this animal.
        t, y, measured = max(eye.values(), key=lambda e: e[2])

    tgt = max(target_uv, 0.5)
    gain = float(np.clip(tgt / max(measured, 0.5), *GAIN_CLAMP))
    out = y * gain

    # Scaling down also scales the recording noise down, which would leave the flat panels
    # implausibly smooth. Add real noise back in proportion to how much was removed.
    if gain < 1.0:
        start = int(rng.integers(0, max(1, len(pool) - len(out))))
        seg = pool[start:start + len(out)]
        if len(seg) == len(out):
            out = out + seg * (1.0 - gain)

    out = cap_awave(t, out, cond, target_uv)
    return t, out


def awave_metrics(t, y):
    """``(a_wave_uv, b_peak_uv, ratio, peak_index)`` for one trace — the a-wave as the EYE reads it.

    ``a_wave_uv`` is a POSITIVE magnitude, baseline to trough, matching how the b-wave table
    reports amplitude.

    Deliberately not ``_erg.landmarks``: that routine's ``a_wave_uv`` measures a specific landmark
    and on these filtered traces it returns ~18 µV where the visible trough is ~180 µV, so it is
    the wrong instrument for "how prominent does the dip LOOK". This takes the b-wave peak in the
    20-140 ms window and the deepest point before it, which is what a reader sees.
    """
    win = (t >= 20.0) & (t <= 140.0)
    if not win.any():
        return 0.0, 0.0, 0.0, 0
    pk_i = int(np.argmax(np.where(win, y, -np.inf)))
    peak = float(y[pk_i])
    trough = float(y[:pk_i + 1].min()) if pk_i else 0.0
    a_uv = abs(min(trough, 0.0))
    if peak <= 0:
        return a_uv, peak, 0.0, pk_i
    return a_uv, peak, a_uv / peak, pk_i


def awave_ratio(t, y):
    """``(ratio, peak_index)`` — the two fields :func:`cap_awave` and :func:`check_awave` need."""
    a_uv, peak, ratio, pk_i = awave_metrics(t, y)
    return ratio, pk_i


def cap_awave(t, y, cond: str, target_uv: float):
    """Pull this panel's pre-b-wave trough down to :data:`AWAVE_MAX_RATIO` if it exceeds it.

    Only the NEGATIVE samples before the b-wave peak are scaled, so the b-wave itself and any
    positive early oscillation are untouched — and because the factor multiplies values that are
    already zero at a zero crossing, the trace stays continuous (no kink is introduced).

    Skipped below ``FLAT_TARGET_UV``: those panels are the noise floor, where "trough over peak"
    means nothing and squashing it would just make a non-response look unnaturally smooth.
    """
    limit = AWAVE_RATIO_BY_COND.get(cond, AWAVE_MAX_RATIO)
    if limit is None or target_uv < FLAT_TARGET_UV:
        return y
    ratio, pk_i = awave_ratio(t, y)
    if ratio <= limit or pk_i == 0:
        return y
    out = y.copy()
    head = out[:pk_i + 1]
    head[head < 0] *= limit / ratio
    return out


def load_targets(summary_csv: Path) -> dict:
    """{(condition, intensity): mean b-wave} from the simulated summary table."""
    out = {}
    for r in csv.DictReader(summary_csv.open(encoding="utf-8")):
        out[(r["condition"], float(r["intensity_log_cd_s_m2"]))] = float(r["mean_b_wave_uv"])
    return out


#: Round scale-bar values, largest first. Only consulted when the view is ZOOMED — the default
#: figure keeps SCALEBAR_UV exactly, so the canonical artifact never moves under this code.
NICE_SCALEBAR_UV = (500, 200, 100, 50, 25, 20, 10, 5)


def _nice_scalebar(span: float) -> int:
    """Largest round µV value that still fits comfortably inside a zoomed panel."""
    for v in NICE_SCALEBAR_UV:
        if v <= 0.45 * span:
            return v
    return NICE_SCALEBAR_UV[-1]


def render(panels, out_path: Path, dpi: int, rows: list[float] | None = None,
           fit_exclude: tuple[str, ...] = (), figsize: tuple[float, float] | None = None,
           caption: str | None = None) -> float:
    """Draw the trace grid. Returns the magnification applied to the y-window.

    ``rows`` selects which flash intensities to draw (default: all seven). ``fit_exclude`` names
    conditions allowed to run OFF-SCALE: the y-window is then fitted to the arms that remain, so
    small responses are magnified and the excluded ones are clipped at the panel edge.

    ⚑ The y-window is ALWAYS derived from every panel handed in, never from the subset of ROWS
    drawn, so a single-intensity render sits on the SAME scale as the full grid and the two
    figures stay comparable. Cropping rows must not silently rescale the trace it leaves behind.
    """
    rows = list(INTENSITIES_LOG) if rows is None else list(rows)

    def _window(items):
        lo = min(y.min() for _t, y in items)
        hi = max(y.max() for _t, y in items)
        pad = 0.06 * (hi - lo)
        return lo - pad, hi + pad

    full = _window(list(panels.values()))
    if fit_exclude:
        kept = [v for (cond, _x), v in panels.items() if cond not in fit_exclude]
        hi = max(y.max() for _t, y in kept) * 1.06
        ylim = (-ZOOM_TROUGH_FRAC * hi, hi)
    else:
        ylim = full
    zoom = (full[1] - full[0]) / (ylim[1] - ylim[0])
    t_ref = next(iter(panels.values()))[0]
    xlim = (float(t_ref.min()), float(t_ref.max()))
    baseline_frac = (0.0 - ylim[0]) / (ylim[1] - ylim[0])
    # A fitted window puts the excluded arms outside the axes. Left unclipped (the default, which
    # keeps the packed full grid from looking boxed-in) they would draw across their neighbours.
    clip = bool(fit_exclude)
    scalebar_uv = SCALEBAR_UV if not fit_exclude else _nice_scalebar(ylim[1] - ylim[0])

    nrows, ncols = len(rows), len(CONDITION_ORDER)
    size = figsize or FIG_SIZE
    # Every one of these three constants was tuned for a SEVEN-row grid and breaks at one row,
    # so each is re-derived from the row count / canvas height. All three reduce to their old
    # values at nrows=7 with the default canvas, which is why the canonical figure is untouched.
    #   top    — a short canvas cropped the two-line column headers; reserve them in inches.
    #   drop   — the scale bar hangs SCALEBAR_DROP of a PANEL height below the grid, and panels
    #            grow as rows are dropped; at 0.70 of a tall panel it fell off the canvas.
    #   bottom — the margin that still clears the scale bar, never tighter than the old 0.20.
    top = 0.935 if figsize is None else 1.0 - HEADER_SPACE_IN / size[1]
    drop = SCALEBAR_DROP * nrows / len(INTENSITIES_LOG)
    below = 0.10
    bottom = max(0.20, (top * drop / nrows + below) / (1 + drop / nrows))
    fig, axes = plt.subplots(nrows, ncols, figsize=size, dpi=dpi,
                             sharex=True, sharey=True, squeeze=False)
    fig.subplots_adjust(left=0.035, right=0.87, top=top, bottom=bottom,
                        hspace=ROW_GAP, wspace=COL_GAP)

    for ri, x_log in enumerate(rows):
        for ci, cond in enumerate(CONDITION_ORDER):
            ax = axes[ri][ci]
            t, y = panels[(cond, x_log)]
            ax.plot(t, y, color=COLORS[cond], linewidth=LINE_WIDTH,
                    solid_capstyle="round", clip_on=clip)
            ax.set_ylim(*ylim)
            ax.set_xlim(*xlim)
            ax.axis("off")

            if ri == 0:
                ax.set_title(COL_LABELS[cond], fontsize=HEADER_SIZE, fontweight="bold",
                             color=HEADER_COLOR, pad=14, linespacing=1.25)
            if ci == ncols - 1:
                ax.text(1.07, baseline_frac, f"{x_log:+.1f}", transform=ax.transAxes,
                        fontsize=INTENSITY_SIZE, fontweight="bold", va="center",
                        ha="left", color="#222222")

    fig.text(0.945, 0.545, "flash intensity (log cd·s/m²)", rotation=270,
             va="center", ha="center", fontsize=INTENSITY_SIZE, color="#222222")

    # Shared scale bar in its own axes below the grid, given the same width, height and
    # limits as a grid panel so 200 µV and 100 ms are drawn at exactly the panel scale.
    pos = axes[nrows - 1][0].get_position()
    sb = fig.add_axes([pos.x0, pos.y0 - pos.height * drop - 0.005,
                       pos.width, pos.height])
    sb.set_xlim(*xlim)
    sb.set_ylim(*ylim)
    sb.axis("off")
    x0 = xlim[0] + 0.04 * (xlim[1] - xlim[0])
    y0 = ylim[0] + 0.05 * (ylim[1] - ylim[0])
    sb.plot([x0, x0], [y0, y0 + scalebar_uv], color="#000000", lw=2.6,
            solid_capstyle="butt", clip_on=False)
    sb.plot([x0, x0 + SCALEBAR_MS], [y0, y0], color="#000000", lw=2.6,
            solid_capstyle="butt", clip_on=False)
    sb.text(x0 - 0.035 * (xlim[1] - xlim[0]), y0 + scalebar_uv / 2, f"{scalebar_uv} µV",
            rotation=90, va="center", ha="right", fontsize=INTENSITY_SIZE,
            fontweight="bold")
    sb.text(x0 + SCALEBAR_MS / 2, y0 - 0.05 * (ylim[1] - ylim[0]), f"{SCALEBAR_MS} ms",
            va="top", ha="center", fontsize=INTENSITY_SIZE, fontweight="bold")

    # No on-figure title: this panel gets laid out with its legend underneath, so a title on
    # the artwork only has to be cropped off later (owner, 2026-08-03). The MOCK provenance is
    # NOT lost with it -- the caption below still states that the amplitudes are simulated, and
    # the README carries the full warning.
    # The caption may name the magnification, which is only known once the window is fitted --
    # so it is formatted HERE rather than assembled by the caller from a guess.
    fig.text(0.5, 0.022,
             (caption or
              "Waveform shapes are real recordings; condition assignment and amplitudes follow "
              "the simulated b-wave table. Shared vertical scale across all panels."
              ).format(zoom=zoom),
             ha="center", fontsize=9, color="#555555",
             # Two-line variant captions only: the default single-line caption keeps matplotlib's
             # baseline alignment so the canonical figure stays byte-identical under this change.
             **({"va": "bottom", "linespacing": 1.5} if caption else {}))

    fig.savefig(out_path, format="jpg", dpi=dpi,
                pil_kwargs={"quality": 95}, facecolor="white")
    plt.close(fig)
    print(f"  wrote {out_path.name}  ({nrows}x{ncols} panels, {dpi} dpi"
          f"{f', y-scale {zoom:.2f}x, {scalebar_uv} µV bar' if fit_exclude else ''})")
    return zoom


def write_waveform_csv(panels, out_path: Path, rows: list[float] | None = None) -> None:
    """Tidy waveform table so the traces can be re-plotted in any tool.

    ``rows`` restricts the table to the intensities a variant figure draws. ``intensity_group``
    keeps its number from the FULL seven-flash ladder (1.9 log stays Group 5), so a cropped
    table still joins to the b-wave tables and to the LabScribe export it mirrors.
    """
    rows = list(INTENSITIES_LOG) if rows is None else list(rows)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["condition", "condition_order", "intensity_group",
                    "intensity_log_cd_s_m2", "time_ms", "voltage_uv"])
        n = 0
        for order, cond in enumerate(CONDITION_ORDER, start=1):
            for group, x_log in enumerate(INTENSITIES_LOG, start=1):
                if x_log not in rows:
                    continue
                t, y = panels[(cond, x_log)]
                for tv, yv in zip(t, y):
                    w.writerow([cond, order, group, x_log,
                                round(float(tv), 2), round(float(yv), 2)])
                    n += 1
    print(f"  wrote {out_path.name}  ({n} rows)")


def check_awave(panels, targets) -> None:
    """Report the a-wave prominence per column, and REFUSE to write if the biology is wrong.

    Same discipline as ``generate_mock_fig1e.py``: exit non-zero rather than emit a figure that
    misrepresents the model. Two things must hold on every responding panel:

      * no rd10 arm's trough exceeds :data:`AWAVE_MAX_RATIO` — a treated retina must not show a
        photoreceptor response it does not have;
      * the WT Control's trough stays well ABOVE that cap — if the Control ever flattened to the
        treated arms' level the figure would have lost the one contrast it exists to show.
    """
    print("  a-wave check (trough / b-wave peak, responding panels only):")
    bad, control_max = [], 0.0
    for cond in CONDITION_ORDER:
        ratios = [awave_ratio(*panels[(cond, x)])[0]
                  for x in INTENSITIES_LOG if targets[(cond, x)] >= FLAT_TARGET_UV]
        if not ratios:
            print(f"    {cond:28s} (no responding panel)")
            continue
        lo, hi = min(ratios), max(ratios)
        limit = AWAVE_RATIO_BY_COND.get(cond, AWAVE_MAX_RATIO)
        print(f"    {cond:28s} {lo:.2f}-{hi:.2f}"
              f"{'' if limit is None else f'   (cap {limit:.2f})'}")
        if limit is None:
            control_max = hi
        elif hi > limit + 1e-9:
            bad.append(f"{cond} reaches {hi:.2f}, above its {limit:.2f} cap")

    if control_max <= AWAVE_MAX_RATIO:
        bad.append(f"Control's a-wave is only {control_max:.2f} — at or below the treated cap "
                   f"({AWAVE_MAX_RATIO:.2f}), so the figure no longer shows the WT/rd10 contrast")
    if bad:
        sys.exit("REFUSING to write — a-wave biology check failed:\n  - " + "\n  - ".join(bad))


def write_awave_csv(panels, out_path: Path, rows: list[float] | None = None) -> None:
    """a-wave / b-peak / ratio per condition x intensity, measured off the drawn traces.

    WHY THIS EXISTS AND WHAT IT IS NOT. The b-wave tables are simulated PER EYE (30 eyes x 7
    intensities) and carry mean + SEM. This one is measured from the ONE representative trace per
    condition that the figure draws, so it has no n, no SEM, and no per-eye rows — it is the
    figure's own morphology in numbers, not a second sample. Mixing it into the b-wave tables
    would imply per-eye a-wave measurements that do not exist.

    Generated here, in the renderer, on purpose: it is measured from the same in-memory panels
    that get drawn, so the table and the figure cannot disagree — the same reason the trace CSV
    is written here and the b-wave CSVs are written by the generator.

    Note the rd10 arms' values are shaped by ``AWAVE_MAX_RATIO`` (a ceiling), so they express a
    designed constraint rather than an independent simulation. The column says so.

    ``b_peak_uv_trace`` is the raw maximum of that representative trace, so it sits a little off
    the group mean in the b-wave table (it rides on oscillatory potentials and noise, and it is
    ONE trace, not a mean of eyes). It is here to make ``a_over_b`` self-contained; the b-wave
    tables remain the amplitude source of record. Named ``_trace`` so the two are not confused.
    """
    rows = list(INTENSITIES_LOG) if rows is None else list(rows)
    n = 0
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["condition", "condition_order", "intensity_group",
                    "intensity_log_cd_s_m2", "a_wave_uv", "b_peak_uv_trace", "a_over_b",
                    "a_wave_source"])
        for order, cond in enumerate(CONDITION_ORDER, start=1):
            capped = AWAVE_RATIO_BY_COND.get(cond, AWAVE_MAX_RATIO)
            for group, x_log in enumerate(INTENSITIES_LOG, start=1):
                if x_log not in rows:
                    continue
                n += 1
                a_uv, b_uv, ratio, _ = awave_metrics(*panels[(cond, x_log)])
                # No comma inside the field: these files get pasted into Excel/GraphPad, where a
                # quoted comma is legal CSV but still splits under a naive text import.
                source = ("source eye (unmodified)" if capped is None else
                          f"capped at a/b <= {capped:g}")
                w.writerow([cond, order, group, x_log,
                            round(a_uv, 2), round(b_uv, 2), round(ratio, 4), source])
    print(f"  wrote {out_path.name}  ({n} rows)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--outdir", type=Path, default=Path(__file__).parent)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--real-src", type=Path, default=REAL_SRC,
                    help="real decoded waveform table used as the shape library")
    args = ap.parse_args()

    if not args.real_src.exists():
        sys.exit(f"real waveform source not found: {args.real_src}")

    lib = load_real_library(args.real_src)
    pool = noise_pool(lib)
    allb = [e[2] for eye in lib.values() for e in eye.values()]
    print(f"  real shape library: {len(lib)} eyes / {len(allb)} traces, "
          f"b-wave {min(allb):.1f}-{max(allb):.1f} uV; noise pool {len(pool)} samples")

    targets = load_targets(args.outdir / "mock_fig1e_bwave_summary.csv")
    rng = np.random.default_rng(20260802)
    panels = {(c, x): build_panel(targets[(c, x)], c, x, lib, pool, rng)
              for c in CONDITION_ORDER for x in INTENSITIES_LOG}

    check_awave(panels, targets)
    render(panels, args.outdir / "mock_fig1e_traces.jpg", args.dpi)
    write_waveform_csv(panels, args.outdir / "mock_fig1e_waveforms_long.csv")
    write_awave_csv(panels, args.outdir / "mock_fig1e_awave_summary.csv")

    # ── The two reading variants (owner, 2026-08-06) ────────────────────────────────────────
    # Both exist for ONE question the full grid answers badly: how much less does AAV8-RK-PDE6B
    # rescue than the 3'UTR arm? On the seven-row grid every panel is ~0.8 in tall and the two
    # rescue columns sit four columns apart, so the comparison is hard to make by eye. Neither
    # variant re-simulates anything -- same panels, same y-window derivation, different view.
    for tag, kw, cap in (
        ("zoom",
         dict(fit_exclude=ZOOM_FIT_EXCLUDE),
         "Waveform shapes are real recordings; amplitudes follow the simulated b-wave table.\n"
         "Vertical scale expanded {zoom:.1f}× to separate the rescue arms — the WT Control "
         "runs off-scale and is CLIPPED, not reduced."),
        ("1p9",
         dict(rows=[FOCUS_LOG_I], figsize=SINGLE_ROW_FIG_SIZE),
         f"Waveform shapes are real recordings; amplitudes follow the simulated b-wave table.\n"
         f"Flash {FOCUS_LOG_I:+.1f} log cd·s/m² only, on the same vertical scale as the full "
         f"seven-flash grid."),
    ):
        render(panels, args.outdir / f"mock_fig1e_traces_{tag}.jpg", args.dpi,
               caption=cap, **kw)
        rows = kw.get("rows")
        write_waveform_csv(panels, args.outdir / f"mock_fig1e_waveforms_long_{tag}.csv", rows)
        write_awave_csv(panels, args.outdir / f"mock_fig1e_awave_summary_{tag}.csv", rows)


if __name__ == "__main__":
    main()
