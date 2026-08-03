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
INTENSITY_SIZE = 10
SCALEBAR_UV = 200
SCALEBAR_MS = 100
#: How far the scale-bar axes sits below the last row, as a fraction of one panel's height.
#: Its HEIGHT must stay equal to a panel's (see render) so 200 µV is drawn at exactly the panel
#: scale — only its position is tunable, which is what this is.
SCALEBAR_DROP = 0.70

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


def awave_ratio(t, y):
    """``(trough_depth / b_wave_peak, peak_index)`` for one trace — the a-wave as the EYE reads it.

    Deliberately not ``_erg.landmarks``: that routine's ``a_wave_uv`` measures a specific landmark
    and on these filtered traces it returns ~18 µV where the visible trough is ~180 µV, so it is
    the wrong instrument for "how prominent does the dip LOOK". This takes the b-wave peak in the
    20-140 ms window and the deepest point before it, which is what a reader sees.
    """
    win = (t >= 20.0) & (t <= 140.0)
    if not win.any():
        return 0.0, 0
    pk_i = int(np.argmax(np.where(win, y, -np.inf)))
    peak = float(y[pk_i])
    trough = float(y[:pk_i + 1].min()) if pk_i else 0.0
    if peak <= 0:
        return 0.0, pk_i
    return abs(min(trough, 0.0)) / peak, pk_i


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


def render(panels, out_path: Path, dpi: int) -> None:
    lo = min(y.min() for _t, y in panels.values())
    hi = max(y.max() for _t, y in panels.values())
    pad = 0.06 * (hi - lo)
    ylim = (lo - pad, hi + pad)
    t_ref = next(iter(panels.values()))[0]
    xlim = (float(t_ref.min()), float(t_ref.max()))
    baseline_frac = (0.0 - ylim[0]) / (ylim[1] - ylim[0])

    nrows, ncols = len(INTENSITIES_LOG), len(CONDITION_ORDER)
    fig, axes = plt.subplots(nrows, ncols, figsize=FIG_SIZE, dpi=dpi,
                             sharex=True, sharey=True)
    fig.subplots_adjust(left=0.035, right=0.87, top=0.885, bottom=0.20,
                        hspace=ROW_GAP, wspace=COL_GAP)

    for ri, x_log in enumerate(INTENSITIES_LOG):
        for ci, cond in enumerate(CONDITION_ORDER):
            ax = axes[ri][ci]
            t, y = panels[(cond, x_log)]
            ax.plot(t, y, color=COLORS[cond], linewidth=LINE_WIDTH,
                    solid_capstyle="round", clip_on=False)
            ax.set_ylim(*ylim)
            ax.set_xlim(*xlim)
            ax.axis("off")

            if ri == 0:
                ax.set_title(COL_LABELS[cond], fontsize=HEADER_SIZE, fontweight="bold",
                             color=COLORS[cond], pad=14, linespacing=1.25)
            if ci == ncols - 1:
                ax.text(1.07, baseline_frac, f"{x_log:+.1f}", transform=ax.transAxes,
                        fontsize=INTENSITY_SIZE, fontweight="bold", va="center",
                        ha="left", color="#222222")

    fig.text(0.945, 0.545, "flash intensity (log cd·s/m²)", rotation=270,
             va="center", ha="center", fontsize=INTENSITY_SIZE, color="#222222")

    # Shared scale bar in its own axes below the grid, given the same width, height and
    # limits as a grid panel so 200 µV and 100 ms are drawn at exactly the panel scale.
    pos = axes[nrows - 1][0].get_position()
    sb = fig.add_axes([pos.x0, pos.y0 - pos.height * SCALEBAR_DROP - 0.005,
                       pos.width, pos.height])
    sb.set_xlim(*xlim)
    sb.set_ylim(*ylim)
    sb.axis("off")
    x0 = xlim[0] + 0.04 * (xlim[1] - xlim[0])
    y0 = ylim[0] + 0.05 * (ylim[1] - ylim[0])
    sb.plot([x0, x0], [y0, y0 + SCALEBAR_UV], color="#000000", lw=2.6,
            solid_capstyle="butt", clip_on=False)
    sb.plot([x0, x0 + SCALEBAR_MS], [y0, y0], color="#000000", lw=2.6,
            solid_capstyle="butt", clip_on=False)
    sb.text(x0 - 0.035 * (xlim[1] - xlim[0]), y0 + SCALEBAR_UV / 2, f"{SCALEBAR_UV} µV",
            rotation=90, va="center", ha="right", fontsize=INTENSITY_SIZE,
            fontweight="bold")
    sb.text(x0 + SCALEBAR_MS / 2, y0 - 0.05 * (ylim[1] - ylim[0]), f"{SCALEBAR_MS} ms",
            va="top", ha="center", fontsize=INTENSITY_SIZE, fontweight="bold")

    fig.suptitle("Representative scotopic ERG traces — MOCK FIGURE",
                 fontsize=14, fontweight="bold", y=0.975)
    fig.text(0.5, 0.022,
             "Waveform shapes are real recordings; condition assignment and amplitudes follow "
             "the simulated b-wave table. Shared vertical scale across all panels.",
             ha="center", fontsize=9, color="#555555")

    fig.savefig(out_path, format="jpg", dpi=dpi,
                pil_kwargs={"quality": 95}, facecolor="white")
    plt.close(fig)
    print(f"  wrote {out_path.name}  ({nrows}x{ncols} panels, {dpi} dpi)")


def write_waveform_csv(panels, out_path: Path) -> None:
    """Tidy waveform table so the traces can be re-plotted in any tool."""
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["condition", "condition_order", "intensity_group",
                    "intensity_log_cd_s_m2", "time_ms", "voltage_uv"])
        n = 0
        for order, cond in enumerate(CONDITION_ORDER, start=1):
            for group, x_log in enumerate(INTENSITIES_LOG, start=1):
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


if __name__ == "__main__":
    main()
