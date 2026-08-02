#!/usr/bin/env python3
"""Render the SIMULATED Fig 1E representative-trace grid (7 intensities x 6 conditions).

    ============================================================
    THIS FIGURE IS SIMULATED. It is NOT experimental measurement.
    Never place it in a manuscript or report of real results.
    ============================================================

Reads `mock_fig1e_bwave_long.csv` (written by generate_mock_fig1e.py), picks one
representative eye per condition, synthesises a scotopic ERG waveform for that eye at each
of the 7 flash intensities, and renders the axis-less floating trace grid with a single
shared scale bar -- the Fig 1E / Fig 2B layout.

The waveform is a shape model (a-wave + b-wave lobes + oscillatory potentials), scaled so
each trace's trough-to-peak amplitude equals that eye's b-wave value in the CSV. So the grid
and the b-wave table always tell the same story: change CONDITIONS in the generator and the
traces follow.

Style (reworked 2026-08-02 -- the first pass was hard to read):
  * No grey. The old palette put AAV8-RK-PDE6B *and* the polyA-stuffer on the same grey,
    so the partial-rescue arm -- the one the figure is about -- was the least visible thing
    on it. Palette is now Okabe-Ito, colourblind-safe, one distinct hue per condition.
  * Thicker lines (LINE_WIDTH), so traces hold up when the figure is scaled down.
  * Rows packed tight (ROW_GAP), closing the dead whitespace above and below each trace.
  * Labels enlarged, condition headers bold and tinted to match their trace.

Usage:  python3 render_mock_fig1e_traces.py [--outdir DIR] [--dpi N]
Needs matplotlib + numpy, e.g. the backend venv:
    app/backend/.venv/bin/python render_mock_fig1e_traces.py
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INTENSITIES_LOG = [-1.7, -0.8, 0.1, 1.0, 1.9, 2.8, 3.1]

CONDITION_ORDER = [
    "Control",
    "Untreated",
    "AAV8-RK-PDE6B",
    "AAV8-RK-GFP-polyA-stuffer",
    "AAV8-CMV-GFP",
    "AAV8-RK-PDE6B-3UTR",
]

# Column header above each condition. "\n" wraps the long ones so headers never collide.
COL_LABELS = {
    "Control": "Control",
    "Untreated": "Untreated",
    "AAV8-RK-PDE6B": "AAV8-RK-PDE6B",
    "AAV8-RK-GFP-polyA-stuffer": "AAV8-RK-GFP\npolyA stuffer",
    "AAV8-CMV-GFP": "AAV8-CMV-GFP",
    "AAV8-RK-PDE6B-3UTR": "AAV8-RK-PDE6B\n3'UTR",
}

# Okabe-Ito colourblind-safe palette -- NO GREY (see module docstring).
# Black = healthy reference; the two PDE6B arms get strong, distinct hues (green = partial
# rescue, vermillion = full rescue); the three nulls take the remaining hues.
COLORS = {
    "Control": "#000000",              # black    -- WT reference
    "Untreated": "#0072B2",            # blue     -- rd10 disease baseline
    "AAV8-RK-PDE6B": "#009E73",        # green    -- partial rescue (was grey)
    "AAV8-RK-GFP-polyA-stuffer": "#CC79A7",  # pink -- null (was grey)
    "AAV8-CMV-GFP": "#E69F00",         # amber    -- null
    "AAV8-RK-PDE6B-3UTR": "#D55E00",   # vermillion -- best rescue
}

# --- style knobs (the things the first pass got wrong) -------------------------------
LINE_WIDTH = 1.9      # was ~0.9 -- traces now read at print size
ROW_GAP = 0.0         # panels touch: traces stacked as close as the shared scale allows
COL_GAP = 0.10
# Panel height is what actually controls how close the stacked traces sit. All panels share
# one y-range (so the single scale bar is meaningful), which means a short panel pulls every
# row together. 7 rows in ~7.8in leaves the tall Control traces just clear of the row above.
FIG_SIZE = (13.5, 7.8)
HEADER_SIZE = 11
INTENSITY_SIZE = 10
SCALEBAR_UV = 200     # shared scale bar, matching the spec's 200 uV x 100 ms
SCALEBAR_MS = 100

# --- waveform shape model ------------------------------------------------------------
T_START, T_END, DT = -20.0, 250.0, 0.5   # ms
A_WAVE_PEAK_MS = 14.0                    # a-wave trough time
OP_FREQ_HZ = 110.0                       # oscillatory potentials


def _lobe(t: np.ndarray, peak_ms: float, k: float) -> np.ndarray:
    """Unit-height gamma-shaped lobe peaking at `peak_ms`; zero before t=0.

    Shape `(t/tp)^k * exp(k*(1 - t/tp))` equals exactly 1.0 at t = tp, giving a fast rise
    and a slower decay -- the asymmetry of a real ERG component.
    """
    out = np.zeros_like(t)
    m = t > 0
    r = t[m] / peak_ms
    out[m] = (r ** k) * np.exp(k * (1.0 - r))
    return out


def waveform(t: np.ndarray, b_amp_uv: float, x_log: float, rng: np.random.Generator):
    """One scotopic ERG sweep, scaled so trough-to-peak == `b_amp_uv`.

    Intensity sets the *shape*, not just the size: brighter flashes give a proportionally
    larger a-wave and a shorter b-wave implicit time, as in a real intensity series.
    """
    frac = (x_log - INTENSITIES_LOG[0]) / (INTENSITIES_LOG[-1] - INTENSITIES_LOG[0])
    b_peak_ms = 95.0 - 40.0 * frac        # implicit time shortens with intensity
    a_ratio = 0.34 * max(0.0, frac - 0.15) / 0.85   # a-wave absent at dim flashes

    b = _lobe(t, b_peak_ms, k=2.6)
    a = _lobe(t, A_WAVE_PEAK_MS, k=4.0)
    y = b - a_ratio * a

    # Oscillatory potentials on the b-wave rising limb.
    op_env = np.exp(-((t - 38.0) ** 2) / (2 * 13.0 ** 2)) * (t > 0)
    y = y + 0.09 * op_env * np.sin(2 * np.pi * OP_FREQ_HZ * t / 1000.0)

    # Scale so the measured trough-to-peak matches the b-wave table exactly.
    span = y.max() - y.min()
    y = y * (b_amp_uv / span) if span > 0 else y * 0.0

    # Baseline recording noise, present on every trace including the flat ones.
    y = y + rng.normal(0.0, 1.5, size=t.shape)
    y[t < 0] = rng.normal(0.0, 1.5, size=int((t < 0).sum()))  # pre-flash baseline
    return y


def load_representatives(csv_path: Path):
    """Pick one representative eye per condition: the eye whose full b-wave-vs-intensity
    curve is closest to the group mean by least squares (the spec's R18 rule, so the mock
    mirrors what the real pipeline does). Returns {condition: (sample_id, {x_log: uv})}."""
    curves: dict[str, dict[str, dict[float, float]]] = {}
    for r in csv.DictReader(csv_path.open(encoding="utf-8")):
        curves.setdefault(r["condition"], {}).setdefault(r["sample_id"], {})[
            float(r["intensity_log_cd_s_m2"])] = float(r["b_wave_uv"])

    reps = {}
    for cond, eyes in curves.items():
        mean = {x: sum(e[x] for e in eyes.values()) / len(eyes) for x in INTENSITIES_LOG}
        best = min(eyes.items(),
                   key=lambda kv: sum((kv[1][x] - mean[x]) ** 2 for x in INTENSITIES_LOG))
        reps[cond] = best
    return reps


def render(reps, out_path: Path, dpi: int) -> None:
    t = np.arange(T_START, T_END + DT, DT)
    rng = np.random.default_rng(20260802)

    # Synthesise every trace first so the grid can share one y-range (R4: equal scaling
    # across panels, which is what makes a single shared scale bar meaningful).
    traces = {(c, x): waveform(t, reps[c][1][x], x, rng)
              for c in CONDITION_ORDER for x in INTENSITIES_LOG}
    lo = min(y.min() for y in traces.values())
    hi = max(y.max() for y in traces.values())
    pad = 0.06 * (hi - lo)
    ylim = (lo - pad, hi + pad)

    # Fraction of the panel height at which the pre-flash baseline (0 µV) sits. Every trace
    # rests on this line, so it -- not the panel centre -- is where a row label belongs.
    baseline_frac = (0.0 - ylim[0]) / (ylim[1] - ylim[0])

    nrows, ncols = len(INTENSITIES_LOG), len(CONDITION_ORDER)
    fig, axes = plt.subplots(nrows, ncols, figsize=FIG_SIZE, dpi=dpi,
                             sharex=True, sharey=True)
    fig.subplots_adjust(left=0.035, right=0.87, top=0.885, bottom=0.20,
                        hspace=ROW_GAP, wspace=COL_GAP)

    for ri, x_log in enumerate(INTENSITIES_LOG):
        for ci, cond in enumerate(CONDITION_ORDER):
            ax = axes[ri][ci]
            ax.plot(t, traces[(cond, x_log)], color=COLORS[cond],
                    linewidth=LINE_WIDTH, solid_capstyle="round", clip_on=False)
            ax.set_ylim(*ylim)
            ax.set_xlim(T_START, T_END)
            ax.axis("off")   # R2: no per-panel axes anywhere on the grid

            if ri == 0:      # condition header, tinted to match its trace
                ax.set_title(COL_LABELS[cond], fontsize=HEADER_SIZE, fontweight="bold",
                             color=COLORS[cond], pad=14, linespacing=1.25)
            if ci == ncols - 1:   # intensity label, aligned to that row's trace baseline
                ax.text(1.07, baseline_frac, f"{x_log:+.1f}", transform=ax.transAxes,
                        fontsize=INTENSITY_SIZE, fontweight="bold", va="center",
                        ha="left", color="#222222")

    # Right-hand axis caption for the intensity column.
    fig.text(0.945, 0.545, "flash intensity (log cd·s/m²)", rotation=270,
             va="center", ha="center", fontsize=INTENSITY_SIZE, color="#222222")

    # Shared scale bar (R3), in its own axes below the grid rather than inside the
    # bottom-left panel -- that panel holds the brightest Control trace, whose a-wave ran
    # straight through the bar. The axes is given the same width, height, and limits as a
    # grid panel, so 200 µV and 100 ms are drawn at exactly the panel scale.
    pos = axes[nrows - 1][0].get_position()
    sb = fig.add_axes([pos.x0, pos.y0 - pos.height - 0.015, pos.width, pos.height])
    sb.set_xlim(T_START, T_END)
    sb.set_ylim(*ylim)
    sb.axis("off")
    x0, y0 = T_START + 10, ylim[0] + 0.05 * (ylim[1] - ylim[0])
    sb.plot([x0, x0], [y0, y0 + SCALEBAR_UV], color="#000000", lw=2.6,
            solid_capstyle="butt", clip_on=False)
    sb.plot([x0, x0 + SCALEBAR_MS], [y0, y0], color="#000000", lw=2.6,
            solid_capstyle="butt", clip_on=False)
    sb.text(x0 - 10, y0 + SCALEBAR_UV / 2, f"{SCALEBAR_UV} µV", rotation=90,
            va="center", ha="right", fontsize=INTENSITY_SIZE, fontweight="bold")
    sb.text(x0 + SCALEBAR_MS / 2, y0 - 0.05 * (ylim[1] - ylim[0]), f"{SCALEBAR_MS} ms",
            va="top", ha="center", fontsize=INTENSITY_SIZE, fontweight="bold")

    fig.suptitle("Representative scotopic ERG traces — SIMULATED DATA",
                 fontsize=14, fontweight="bold", y=0.975)
    fig.text(0.5, 0.022,
             "SIMULATED — not experimental measurement. Representative eye per condition "
             "(eye nearest the group mean). Shared vertical scale across all panels.",
             ha="center", fontsize=9, color="#555555")

    fig.savefig(out_path, format="jpg", dpi=dpi,
                pil_kwargs={"quality": 95}, facecolor="white")
    plt.close(fig)
    print(f"  wrote {out_path.name}  ({nrows}x{ncols} panels, {dpi} dpi)")


def write_waveform_csv(reps, out_path: Path) -> None:
    """Tidy waveform table, so the traces can be re-plotted in any tool."""
    t = np.arange(T_START, T_END + DT, DT)
    rng = np.random.default_rng(20260802)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["sample_id", "condition", "condition_order", "intensity_group",
                    "intensity_log_cd_s_m2", "time_ms", "voltage_uv"])
        n = 0
        for order, cond in enumerate(CONDITION_ORDER, start=1):
            sample_id, curve = reps[cond]
            for group, x_log in enumerate(INTENSITIES_LOG, start=1):
                y = waveform(t, curve[x_log], x_log, rng)
                for tv, yv in zip(t, y):
                    w.writerow([sample_id, cond, order, group, x_log,
                                round(float(tv), 1), round(float(yv), 2)])
                    n += 1
    print(f"  wrote {out_path.name}  ({n} rows)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--outdir", type=Path, default=Path(__file__).parent)
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    reps = load_representatives(args.outdir / "mock_fig1e_bwave_long.csv")
    print("  representative eye per condition:")
    for cond in CONDITION_ORDER:
        sid, curve = reps[cond]
        print(f"    {cond:<28} {sid}   b-wave @1.0 = {curve[1.0]:6.1f} uV")

    render(reps, args.outdir / "mock_fig1e_traces.jpg", args.dpi)
    write_waveform_csv(reps, args.outdir / "mock_fig1e_waveforms_long.csv")


if __name__ == "__main__":
    main()
