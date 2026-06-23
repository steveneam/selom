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


def fs_from(time_ms) -> float:
    """Sampling rate (Hz) inferred from a time axis (ms). 5000 Hz default for a degenerate axis."""
    if len(time_ms) < 2:
        return 5000.0
    dt = float(time_ms[1]) - float(time_ms[0])
    return 1000.0 / dt if dt else 5000.0


def metrics_from_waveforms(df):
    """``erg_waveforms_long`` → a per-eye a/b metrics frame measured FROM the traces.

    One trace per (sample × condition × intensity × eye) → one :func:`landmarks` measurement →
    one row carrying ``a_wave_uv`` + ``b_wave_uv`` (and the intensity/stimulus columns passed
    through). This is the fan-out path the owner asked for — the bar and intensity-response run
    straight off the dropped recording at the chosen intensity, using the same a/b metric the
    trace grid reports, instead of needing a separate device-metrics CSV. Device markers stay
    preferred when a metrics table IS supplied (the caller checks for the marker column first)."""
    import pandas as pd

    keys = [k for k in ("sample_id", "condition", "intensity_group", "eye") if k in df.columns]
    if "condition" not in keys or "intensity_group" not in keys:
        return df  # not a recognizable waveform grouping → let the caller's column check fail honestly
    carry = [c for c in ("intensity_log_cd_s_m2", "stimulus_type", "condition_order") if c in df.columns]
    rows = []
    for kv, seg in df.groupby(keys, dropna=False):
        seg = seg.sort_values("time_ms")
        t = seg["time_ms"].astype(float).tolist()
        y = seg["voltage_uv"].astype(float).tolist()
        if len(t) < 4:
            continue
        lm = landmarks(t, y, fs=fs_from(t))
        rec = dict(zip(keys, kv if isinstance(kv, tuple) else (kv,)))
        rec["a_wave_uv"] = lm["a_wave_uv"]
        rec["b_wave_uv"] = lm["b_wave_uv"]
        for c in carry:
            vals = seg[c].dropna()
            rec[c] = vals.iloc[0] if not vals.empty else None
        rows.append(rec)
    return pd.DataFrame(rows)


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


# --- Display units (voltage) -------------------------------------------------
# The parser + device markers are canonical in µV. A display unit only RESCALES for
# presentation (no recomputation): `factor` multiplies a µV value to reach the chosen unit.
# "auto" picks the unit that puts the peak |amplitude| into a readable 1–1000 range. Default
# µV (factor 1.0) leaves every figure byte-identical — the legacy path is untouched.
_VOLT_FACTOR = {"nv": 1000.0, "uv": 1.0, "µv": 1.0, "mv": 0.001, "v": 1e-6}
_VOLT_LABEL = {"nv": "nV", "uv": "µV", "µv": "µV", "mv": "mV", "v": "V"}
_AUTO_ORDER = ("V", "mV", "µV", "nV")  # largest unit first → first that reads in [1, 1000)


def unit_factor(unit: str) -> float:
    """µV → `unit` multiplier (e.g. 'mV' → 0.001, 'nV' → 1000). Unknown → 1.0 (µV)."""
    return _VOLT_FACTOR.get(str(unit).strip().lower(), 1.0)


def unit_label(unit: str) -> str:
    """Canonical display label for a unit token ('uv'/'µV' → 'µV'). Unknown → 'µV'."""
    return _VOLT_LABEL.get(str(unit).strip().lower(), "µV")


def resolve_display_unit(token, peak_uv: float = 0.0) -> str:
    """Resolve a `display_unit` token to a concrete label ('nV'|'µV'|'mV'|'V').

    An explicit unit is honoured verbatim. '' / 'auto' / unknown → pick the unit that puts
    the peak |amplitude (µV)| into a readable [1, 1000) range (defaulting to µV), so tiny
    flicker/c-wave traces can read in nV and large bright-flash b-waves in mV without the user
    hand-picking. Default µV when the peak is unknown/zero."""
    t = str(token or "").strip().lower()
    if t in _VOLT_FACTOR:
        return _VOLT_LABEL[t]
    if t and t != "auto":
        return "µV"
    p = abs(float(peak_uv or 0.0))
    if p <= 0.0:
        return "µV"
    for label in _AUTO_ORDER:
        scaled = p * _VOLT_FACTOR[label.lower()]
        if 1.0 <= scaled < 1000.0:
            return label
    return "µV"


def disp_round(value, factor: float = 1.0):
    """Rescale a µV `value` to a display unit (× `factor`) and round for presentation.

    `factor` == 1.0 (µV) → legacy 2-dp rounding, so the default path is byte-identical.
    Otherwise keep ~5 significant figures so small units (mV/V) aren't crushed to zero and
    large units (nV) stay clean."""
    import math

    x = float(value) * float(factor)
    if factor == 1.0:
        return round(x, 2)
    if x == 0.0 or not math.isfinite(x):
        return 0.0 if x == 0.0 else x
    decimals = min(9, max(0, 4 - math.floor(math.log10(abs(x)))))
    return round(x, decimals)


# --- Adaptation mode (scotopic vs photopic flash) ----------------------------
# A multi-mode Diagnosys export carries scotopic + photopic flash steps (each with its own
# per-mode intensity groups) and flicker steps in one file. A flash skill renders ONE mode or
# the intensity rows collide, so it resolves which `stimulus_type` to keep. The friendly knob is
# `adaptation` (scotopic|photopic|auto); the low-level `stimulus_type` wins when set explicitly.
_ADAPT_STIM = {"scotopic": "scotopic_flash", "photopic": "photopic_flash"}
_STIM_ADAPT = {"scotopic_flash": "scotopic", "photopic_flash": "photopic"}


def resolve_flash_mode(present, adaptation: str = "auto", stimulus_type: str = "") -> tuple[str, str]:
    """Resolve ``(pick_stimulus_type, adaptation_label)`` for a flash skill.

    Explicit ``stimulus_type`` wins; else map the ``adaptation`` hint
    (``scotopic``/``photopic``); else ``auto`` = the first of scotopic→photopic present in the
    data. ``present`` = the ``stimulus_type`` values present (may be empty — the iWorx path has no
    such column, so ``pick`` is "" and the caller does not filter, leaving that path unchanged)."""
    present = [str(p) for p in present if p]
    pick = str(stimulus_type or "").strip()
    if not pick:
        a = str(adaptation or "auto").strip().lower()
        if a in _ADAPT_STIM:
            pick = _ADAPT_STIM[a]
        else:
            pick = next((p for p in ("scotopic_flash", "photopic_flash") if p in present), "")
    return pick, _STIM_ADAPT.get(pick, "")


# --- Flicker (steady-state periodic response) --------------------------------
# Flicker ERG is a periodic response, not a flash transient — measured as N1→P1 (the first
# cornea-negative trough to the following cornea-positive peak). The robust, noise-rejecting
# measure phase-folds the whole steady-state sweep into ONE representative cycle (averaging every
# cycle at each phase), then takes the trough-to-peak amplitude + the P1 implicit time. This
# matches the device's own N1/P1 markers well at 10 Hz and tracks them at the noisier 30 Hz; the
# device markers stay authoritative when the fed table carries them (R-flicker-3).

def flicker_cycle(time_ms, voltage, hz: float, *, n_bins: int = 120, start_ms: float = 0.0):
    """Phase-fold the steady-state flicker response (samples at ``time_ms >= start_ms``) into one
    averaged cycle of period ``1000/hz`` ms. Returns ``(phase_ms, mean_uv)`` plain-float lists
    (empty if there is no usable post-onset signal)."""
    import numpy as np

    t = np.asarray(time_ms, dtype=float)
    y = np.asarray(voltage, dtype=float)
    if hz <= 0 or t.size == 0:
        return [], []
    period = 1000.0 / float(hz)
    m = (t >= start_ms) & np.isfinite(t) & np.isfinite(y)
    t, y = t[m], y[m]
    if t.size == 0:
        return [], []
    phase = np.mod(t, period)
    edges = np.linspace(0.0, period, n_bins + 1)
    idx = np.clip(np.digitize(phase, edges) - 1, 0, n_bins - 1)
    centers, means = [], []
    for b in range(n_bins):
        sel = idx == b
        if sel.any():
            centers.append(round(float((edges[b] + edges[b + 1]) / 2.0), 3))
            means.append(round(float(y[sel].mean()), 4))
    return centers, means


def flicker_landmarks(time_ms, voltage, hz: float, *, n_bins: int = 120,
                      start_ms: float = 0.0) -> dict | None:
    """N1→P1 on the phase-folded steady-state cycle: N1 = the trough, P1 = the following peak.

    Returns ``{n1p1_uv, p1_implicit_ms, n1_implicit_ms, n1_uv, p1_uv}`` (µV / ms), or None when no
    cycle could be formed. ``n1p1_uv`` is the peak-to-trough amplitude (the ISCEV flicker measure);
    ``p1_implicit_ms`` is the P1 phase within the cycle."""
    import numpy as np

    ph, cyc = flicker_cycle(time_ms, voltage, hz, n_bins=n_bins, start_ms=start_ms)
    if len(cyc) < 3:
        return None
    cyc_a = np.asarray(cyc, dtype=float)
    ni = int(np.argmin(cyc_a))
    after = np.arange(ni, cyc_a.size)
    pi = int(after[int(np.argmax(cyc_a[after]))])
    return {
        "n1p1_uv": round(float(cyc_a[pi] - cyc_a[ni]), 3),
        "p1_implicit_ms": round(float(ph[pi]), 1),
        "n1_implicit_ms": round(float(ph[ni]), 1),
        "n1_uv": round(float(cyc_a[ni]), 3),
        "p1_uv": round(float(cyc_a[pi]), 3),
    }


def flicker_first_cycle_marks(time_ms, voltage, hz: float) -> dict | None:
    """N1 (trough) and the following P1 (peak) located ON the first visible cycle of a flicker
    sweep → ``{"n1": (t_ms, uv), "p1": (t_ms, uv)}``. These are marker-dot coordinates that sit on
    the *drawn* trace (a visual locator); the reported N1→P1 amplitude itself comes from the device
    markers (preferred) or the phase-folded cycle (:func:`flicker_landmarks`), not from here. None
    when no usable first cycle exists."""
    import numpy as np

    t = np.asarray(time_ms, dtype=float)
    y = np.asarray(voltage, dtype=float)
    if hz <= 0 or t.size < 3:
        return None
    period = 1000.0 / float(hz)
    m = (t >= 0.0) & (t <= period * 1.05)
    if int(m.sum()) < 3:
        m = np.ones(t.shape, dtype=bool)
    ti, yi = t[m], y[m]
    ni = int(np.argmin(yi))
    after = np.arange(ni, yi.size)
    pi = int(after[int(np.argmax(yi[after]))])
    return {"n1": (round(float(ti[ni]), 2), round(float(yi[ni]), 4)),
            "p1": (round(float(ti[pi]), 2), round(float(yi[pi]), 4))}


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


def spread_stats(values, kind: str = "sem") -> dict:
    """Mean + an error metric for a group of amplitudes → ``{mean, err, lo, hi, sd, n}`` (raw,
    unrounded — the caller rescales/rounds). ``kind``:

    * ``sem`` (default) — standard error of the mean (sd/√n); the owner's default.
    * ``sd``  — standard deviation (the biological spread).
    * ``ci95`` — 95 % CI half-width via the t-quantile (not a hard-coded 1.96), the most defensible.
    * ``minmax`` — asymmetric range: ``lo = mean − min``, ``hi = max − mean``.

    ``err`` is the symmetric magnitude (= ``max(lo, hi)`` for minmax); ``lo``/``hi`` carry the
    asymmetric arms for ``error_y``. n<2 guard built in (err 0 — never a NaN bar). Non-finite
    values are dropped. SEM/SD/min/max are pure-Python; ci95 lazy-imports scipy for the t-quantile."""
    import math

    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    n = len(vals)
    if n == 0:
        return {"mean": 0.0, "err": 0.0, "lo": 0.0, "hi": 0.0, "sd": 0.0, "n": 0}
    mean = sum(vals) / n
    if n < 2:
        return {"mean": mean, "err": 0.0, "lo": 0.0, "hi": 0.0, "sd": 0.0, "n": n}
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
    sem = sd / math.sqrt(n)
    k = str(kind or "sem").strip().lower()
    if k == "sd":
        err = lo = hi = sd
    elif k == "ci95":
        from scipy.stats import t
        err = lo = hi = float(t.ppf(0.975, n - 1)) * sem
    elif k == "minmax":
        lo, hi = mean - min(vals), max(vals) - mean
        err = max(lo, hi)
    else:  # sem
        err = lo = hi = sem
    return {"mean": mean, "err": err, "lo": lo, "hi": hi, "sd": sd, "n": n}


# Display label for an error metric (caption / table header).
ERR_LABEL = {"sem": "SEM", "sd": "SD", "ci95": "95% CI", "minmax": "range"}


def rgba(hexcolor, alpha) -> str:
    """``'#rrggbb'`` (or 3-digit shorthand) → ``'rgba(r,g,b,a)'`` — for translucent fills / band
    colours Plotly won't derive from a hex line colour. Mirrors ``_tracegrid._rgba``."""
    h = str(hexcolor or "#888888").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        r = g = b = 136
    return f"rgba({r},{g},{b},{round(float(alpha), 3)})"


def sig_stars(p) -> str:
    """p-value → significance stars (GraphPad convention): ``***`` <0.001 · ``**`` <0.01 ·
    ``*`` <0.05 · ``ns`` otherwise. None/non-finite → ``ns``."""
    import math

    if p is None or not math.isfinite(float(p)):
        return "ns"
    p = float(p)
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"


def compare_groups(a, b, test: str = "welch"):
    """Two-group two-sided p-value, or None when either side has n<2. ``test``: ``welch``
    (default, unequal-variance t) · ``student`` (equal-variance t) · ``mannwhitney`` (rank, no
    normality assumption). scipy lazy-imported (already a dep via the Naka-Rushton fit)."""
    import math

    a = [float(x) for x in a if x is not None and math.isfinite(float(x))]
    b = [float(x) for x in b if x is not None and math.isfinite(float(x))]
    if len(a) < 2 or len(b) < 2:
        return None
    from scipy import stats

    t = str(test or "welch").strip().lower()
    try:
        if t in ("mannwhitney", "mwu", "u"):
            return float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue)
        return float(stats.ttest_ind(a, b, equal_var=(t == "student")).pvalue)
    except (ValueError, ZeroDivisionError):
        return None
