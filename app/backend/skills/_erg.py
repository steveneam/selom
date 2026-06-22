"""Shared ERG helpers — the analysis bits behind the ERG figure skills (see
docs/erg-module/spec.md). Domain constants are import-time cheap (no numpy); the
signal-processing helpers lazy-import numpy so the dependency-free stubs never pull it.
"""
from __future__ import annotations

# Scotopic flash-intensity ladder (log cd·s/m²) — Group1 (dim) … Group7 (bright).
INTENSITIES_LOG = [-1.7, -0.8, 0.1, 1.0, 1.9, 2.8, 3.1]

# Fig 1E condition order (canonical labels = those in the manifest / waveforms table).
CONDITION_ORDER = [
    "Control",
    "Untreated",
    "AAV8-RK-PDE6B",
    "AAV8-RK-GFP-polyA-stuffer",
    "AAV8-CMV-GFP",
    "AAV8-RK-PDE6B-3UTR",
]

# Column header shown above each condition (editable in the figure).
COL_LABELS = {
    "Control": "Control",
    "Untreated": "Untreated",
    "AAV8-RK-PDE6B": "AAV8-Rk-PDE6B",
    "AAV8-RK-GFP-polyA-stuffer": "AAV8-RK-GFP-<br>PolyA stuffer",
    "AAV8-CMV-GFP": "AAV8-CMV-GFP",
    "AAV8-RK-PDE6B-3UTR": "AAV8-RK-PDE6B-3UTR",
}

# Per-condition trace colour (owner-set 2026-06-22). The three-way story is highlighted:
# WT Control black (healthy reference) · Untreated rd10 blue (disease baseline) ·
# AAV8-RK-PDE6B-3'UTR red (the rescue). The remaining arms are muted so they don't compete:
# PDE6B (no 3'UTR) + GFP-polyA-stuffer grey, CMV-GFP amber. All editable in the figure.
COLORS = {
    "Control": "#111111",
    "Untreated": "#0072B2",
    "AAV8-RK-PDE6B": "#9aa3ad",
    "AAV8-RK-GFP-polyA-stuffer": "#9aa3ad",
    "AAV8-CMV-GFP": "#E69F00",
    "AAV8-RK-PDE6B-3UTR": "#c0392b",
}

# Mains + instrument hum lines to notch (Hz). 50/100/150 = AU mains harmonics;
# 163 = the discrete instrument line seen on flat .iwxdata traces.
HUM_LINES = (50.0, 100.0, 150.0, 163.0)


def clean_trace(y, fs: float = 5000.0, hum=HUM_LINES, notch_bw: float = 3.0,
                lowpass: float = 300.0):
    """"Clean flats, keep OPs": FFT-notch the discrete hum lines + low-pass above the
    oscillatory-potential band. Removes mains/instrument hum (which dominates flat
    traces) while preserving the broadband OPs (~75–300 Hz) riding on real b-waves —
    a plain low-pass would kill those. Returns a plain Python list (JSON-safe)."""
    import numpy as np

    arr = np.asarray(y, dtype=float)
    n = arr.size
    if n < 8:
        return [float(v) for v in arr]
    spec = np.fft.rfft(arr)
    freq = np.fft.rfftfreq(n, d=1.0 / fs)
    keep = np.ones(freq.shape, dtype=bool)
    for line in hum:
        keep &= ~((freq > line - notch_bw) & (freq < line + notch_bw))
    if lowpass:
        keep &= freq <= lowpass
    spec = spec * keep
    out = np.fft.irfft(spec, n=n)
    return [round(float(v), 4) for v in out]


def _movavg(arr, win: int):
    import numpy as np

    a = np.asarray(arr, dtype=float)
    if win <= 1:
        return a
    k = np.ones(win) / win
    return np.convolve(a, k, mode="same")


# Validated landmark windows (mouse scotopic ERG) — match iwx_parse.Eye.landmarks,
# the metric reconciled to the Fig 1E ordering. Measure on the RAW baseline-corrected
# trace (NOT the display-cleaned one); the dual smooth is internal to the metric.
_PRESTIM_MS = 10.0
_AWAVE_WIN_MS = (0.0, 40.0)
_BWAVE_WIN_MS = (40.0, 120.0)
_AWAVE_SMOOTH_MS = 3.0   # light: preserves the sharp a-wave trough
_BWAVE_SMOOTH_MS = 16.0  # heavy: real broad b-wave survives, high-freq noise averages out


def landmarks(time_ms, y, fs: float = 5000.0) -> dict:
    """a/b-wave amplitudes (µV) + implicit times (ms), noise-rejecting dual smooth.

    a-wave = baseline − min(0–40 ms) on a LIGHT ~3 ms trace (sharp trough preserved).
    b-wave = max(40–120 ms) − min(0–40 ms), BOTH on a HEAVY ~16 ms trace — peak-to-trough,
    so a flat (noise-only) eye reads near the noise floor instead of mistaking a noise
    excursion for a b-wave. baseline = mean of the pre-stimulus window. This mirrors the
    validated ``iwx_parse.Eye.landmarks`` that reproduced the Fig 1E ordering."""
    import numpy as np

    t = np.asarray(time_ms, dtype=float)
    arr = np.asarray(y, dtype=float)
    base = float(arr[t < _PRESTIM_MS].mean()) if (t < _PRESTIM_MS).any() else 0.0
    sm_a = _movavg(arr, max(1, int(round(_AWAVE_SMOOTH_MS / 1000.0 * fs))))
    sm_b = _movavg(arr, max(1, int(round(_BWAVE_SMOOTH_MS / 1000.0 * fs))))

    am = (t >= _AWAVE_WIN_MS[0]) & (t <= _AWAVE_WIN_MS[1])
    if not am.any():
        am = t >= 0
    ai = int(np.argmin(sm_a[am]))
    a_t = float(t[am][ai])
    a_wave = base - float(sm_a[am][ai])

    b_trough = float(np.min(sm_b[am]))
    bm = (t >= _BWAVE_WIN_MS[0]) & (t <= _BWAVE_WIN_MS[1])
    if not bm.any():
        bm = t >= _BWAVE_WIN_MS[0]
    bi = int(np.argmax(sm_b[bm]))
    b_t = float(t[bm][bi])
    b_wave = float(sm_b[bm][bi]) - b_trough

    return {
        "a_wave_uv": round(a_wave, 2),
        "b_wave_uv": round(b_wave, 2),
        "a_t_ms": round(a_t, 1),
        "b_t_ms": round(b_t, 1),
    }


# --- Intensity-response (Naka-Rushton) ---------------------------------------
# The scotopic b-wave saturates with flash energy. Naka-Rushton (1966) models that
# saturating rise: V/Vmax = I^n / (I^n + K^n), with I the linear flash energy. We fit
# in LOG-intensity space (x = log10 I, the ladder the data already carries) for numerical
# stability across the ~5-decade range, where the equivalent form is
#     V = Vmax / (1 + 10^(n·(logK − x))).
# Vmax = saturated amplitude (µV), logK = semi-saturation intensity (log cd·s/m²),
# n = slope. Pure-Python forward (no numpy) so the dependency-free stub can use it too.

def naka_rushton(x_log, vmax: float, log_k: float, n: float):
    """Naka-Rushton b-wave amplitude at flash intensity ``x_log`` (log cd·s/m²).

    Works on a Python float (stub) or a numpy array (fit), since ``**`` is overloaded."""
    return vmax / (1.0 + 10.0 ** (n * (log_k - x_log)))


def naka_rushton_fit(x_log, y, *, fixed_n: float | None = None,
                     n_max: float = 5.0, min_r2: float = 0.3) -> dict | None:
    """Least-squares Naka-Rushton fit → ``{vmax, log_k, n, r2}`` (None if not supportable).

    Bounded, seeded fit (scipy). Two modes:

    * **fixed slope** (``fixed_n`` > 0) — lock n to a chosen value and fit only Vmax + the
      semi-saturation logK. This is the standard, comparable way to fit an intensity-response
      *series of conditions* (compare sensitivity logK / saturation Vmax at one common slope),
      and the knob the scientist adjusts to shape the curve. Needs ≥ 3 points.
    * **free slope** (``fixed_n`` falsy) — also fit n within ``[0.1, n_max]``. Needs ≥ 4 points.

    Honesty gate (both modes): return None when the model isn't actually supported — R² below
    ``min_r2``, or a parameter pinned at its bound (a flat/null condition, or a free slope that
    ran away). The caller then plots the data alone and the table shows "—" rather than a
    bound-artifact curve."""
    import numpy as np
    from scipy.optimize import curve_fit

    x = np.asarray(x_log, dtype=float)
    yv = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(yv)
    x, yv = x[ok], yv[ok]
    if float(yv.max() if yv.size else 0.0) <= 0.0:
        return None
    vmax0 = max(float(yv.max()), 1.0)
    lo_k, hi_k = float(x.min()) - 3.0, float(x.max()) + 3.0
    hi_v = vmax0 * 5.0 + 1.0

    if fixed_n and float(fixed_n) > 0:
        if x.size < 3:
            return None
        n = float(fixed_n)

        def _model(xx, vmax, log_k):
            return naka_rushton(xx, vmax, log_k, n)

        bounds = ([0.0, lo_k], [hi_v, hi_k])
        p0 = [vmax0, float(np.median(x))]
        try:
            popt, _ = curve_fit(_model, x, yv, p0=p0, bounds=bounds, maxfev=10000)
        except Exception:
            return None
        vmax, log_k = float(popt[0]), float(popt[1])
        pinned = vmax >= hi_v - 1e-3 or log_k <= lo_k + 1e-3 or log_k >= hi_k - 1e-3
    else:
        if x.size < 4:
            return None
        bounds = ([0.0, lo_k, 0.1], [hi_v, hi_k, float(n_max)])
        p0 = [vmax0, float(np.median(x)), 1.0]
        try:
            popt, _ = curve_fit(naka_rushton, x, yv, p0=p0, bounds=bounds, maxfev=10000)
        except Exception:
            return None
        vmax, log_k, n = float(popt[0]), float(popt[1]), float(popt[2])
        pinned = (n <= 0.1 + 1e-3 or n >= float(n_max) - 1e-3 or vmax >= hi_v - 1e-3
                  or log_k <= lo_k + 1e-3 or log_k >= hi_k - 1e-3)

    pred = naka_rushton(x, vmax, log_k, n)
    ss_res = float(np.sum((yv - pred) ** 2))
    ss_tot = float(np.sum((yv - yv.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    if r2 < float(min_r2) or pinned:
        return None
    return {"vmax": round(vmax, 2), "log_k": round(log_k, 3),
            "n": round(n, 3), "r2": round(r2, 3)}


def summary_stats(values) -> dict:
    """Mean, SEM (sd/√n, ddof=1), and n for a list of amplitudes — the bar-graph summary.

    Pure Python (no numpy) so the dependency-free stub reuses it; non-finite values dropped."""
    import math

    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    n = len(vals)
    if n == 0:
        return {"mean": 0.0, "sem": 0.0, "n": 0}
    mean = sum(vals) / n
    if n > 1:
        var = sum((v - mean) ** 2 for v in vals) / (n - 1)
        sem = math.sqrt(var) / math.sqrt(n)
    else:
        sem = 0.0
    return {"mean": round(mean, 2), "sem": round(sem, 2), "n": n}
