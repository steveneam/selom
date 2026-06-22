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
