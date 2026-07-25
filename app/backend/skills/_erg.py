"""Shared ERG helpers — the analysis bits behind the ERG figure skills (see
docs/records/erg-module/spec.md). Domain constants are import-time cheap (no numpy); the
signal-processing helpers lazy-import numpy so the dependency-free stubs never pull it.
"""
from __future__ import annotations

# Generic chart-styling primitives now live in skills._charts (owner steer 2026-06-24: the styling
# vocabulary is for ALL bar/line graphs, not ERG-only). Re-exported here so existing
# _erg.spread_stats / compare_groups / sig_stars / rgba / ERR_LABEL callers keep working.
from skills._charts import (  # noqa: F401  (re-export)
    ERR_LABEL,
    LINE_PALETTE,
    aggregate_replicates,
    band_traces,
    compare_groups,
    rgba,
    sig_stars,
    spread_stats,
)

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

# Landmark-dot role styling (docs/figure-data-capabilities/spec.md §6). Each landmark role gets a
# distinct colour (separate from the condition palette above) so a/b (and N1/P1) read apart at a
# glance, and a label position that clears the trace: a/N1 are troughs → label below the dot;
# b/P1 are peaks → label above. KEEP IN SYNC with app/frontend/lib/erg/marks.ts (ROLE_COLORS).
ROLE_COLORS = {"a": "#2563eb", "b": "#d97706", "n1": "#0d9488", "p1": "#7c3aed"}
ROLE_TEXTPOS = {"a": "bottom center", "b": "top center", "n1": "bottom center", "p1": "top center"}

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


def _savgol(arr, win_ms, fs, polyorder: int = 2):
    """Savitzky-Golay smooth (window from ``win_ms``, forced odd + clamped to the signal length).

    Used only by the opt-in robust a/b detector (:func:`_robust_auto_ab`). Falls back to the raw
    array when there are too few samples to fit the polynomial, so the robust path degrades to the
    unsmoothed trace on a very short recording instead of raising."""
    import numpy as np
    from scipy.signal import savgol_filter

    a = np.asarray(arr, dtype=float)
    n = a.size
    win = int(round(float(win_ms) / 1000.0 * float(fs)))
    if win % 2 == 0:
        win += 1
    win = max(5, win)
    if win > n:
        win = n if n % 2 == 1 else n - 1
    if win < 5 or win <= polyorder:
        return a
    return savgol_filter(a, win, polyorder)


# Validated landmark windows (mouse scotopic ERG) — match iwx_parse.Eye.landmarks,
# the metric reconciled to the Fig 1E ordering. Measure on the RAW baseline-corrected
# trace (NOT the display-cleaned one); the dual smooth is internal to the metric.
_PRESTIM_MS = 10.0
_AWAVE_WIN_MS = (0.0, 40.0)
_BWAVE_WIN_MS = (40.0, 120.0)
_AWAVE_SMOOTH_MS = 3.0   # light: preserves the sharp a-wave trough
_BWAVE_SMOOTH_MS = 16.0  # heavy: real broad b-wave survives, high-freq noise averages out

# Photopic / cone-driven (light-adapted) landmark windows — anchored to the published mouse cone-ERG
# timing (Bush 2019 IOVS: WT cone b-wave ~44 ms; Lyubarsky 1999: cone a-wave ~14 ms; Saszik 2002:
# the ~110 ms peak is the dim-flash ROD b-wave, NOT cone), corroborated against the real CMRI mouse
# UV-photopic .iwxdata. Two cone facts drive the windows:
#   • the cone a-wave is small and EARLY (~8–20 ms) — a TIGHT early a-window (0–25 ms) isolates it;
#     the scotopic a-window (0–40 ms) under heavy smoothing wrongly latched a ~27 ms noise dip.
#   • the mouse cone b-wave peaks ~40–45 ms (range ~40–75 ms), FASTER than the rod b-wave — so the
#     b-window is (12–80 ms), centred on the cone range. We deliberately do NOT extend past ~80 ms:
#     a "photopic b-wave" near 100 ms is the literature signature of rod contamination / incomplete
#     light-adaptation / 50 Hz hum, so a wider window would chase that artifact instead of the cone
#     b-wave. (An early real-data tuning widened this to 130 ms to capture a 104 ms C57 peak — the
#     timing literature then showed that peak is NOT a cone b-wave; window narrowed back to the cone
#     range. On hum-heavy single-eye recordings the auto-metric is only a SEED — the manual a/b
#     override is the rigorous path; see docs/records/erg-module/spec.md T15.)
# Smoothing stays HEAVY (same as scotopic): these recordings carry strong ~50 Hz mains hum (20 ms
# period) and the 16 ms b-smooth nulls it — a lighter kernel rides the hum and over-reads the b-wave.
# Selected by the `mode` argument to landmarks() — driven off `stimulus_type`/`adaptation` upstream.
_PHOTOPIC_AWAVE_WIN_MS = (0.0, 25.0)
_PHOTOPIC_BWAVE_WIN_MS = (12.0, 80.0)
_PHOTOPIC_AWAVE_SMOOTH_MS = 3.0    # same light a-smooth as scotopic (sharp trough preserved)
_PHOTOPIC_BWAVE_SMOOTH_MS = 16.0   # heavy: rejects the ~50 Hz hum on the raw photopic recordings

# mode → (a-window, b-window, a-smooth ms, b-smooth ms). Unknown/"" → scotopic (back-compatible
# default; the µV figures stay byte-identical when no adaptation signal is present).
_LANDMARK_MODES = {
    "scotopic": (_AWAVE_WIN_MS, _BWAVE_WIN_MS, _AWAVE_SMOOTH_MS, _BWAVE_SMOOTH_MS),
    "photopic": (_PHOTOPIC_AWAVE_WIN_MS, _PHOTOPIC_BWAVE_WIN_MS,
                 _PHOTOPIC_AWAVE_SMOOTH_MS, _PHOTOPIC_BWAVE_SMOOTH_MS),
}


def _value_at(t, sm, t_ms: float) -> tuple[float, float]:
    """Value of a (smoothed) trace AT a supplied time → ``(snapped_time_ms, value)``.

    Snaps to the nearest sample and reads a ±1-sample-window mean there (so a single-sample
    noise spike at the operator's chosen point doesn't drive the amplitude). Clamps an
    out-of-range time to the nearest sample (the editor also constrains the drag)."""
    import numpy as np

    i = int(np.argmin(np.abs(t - float(t_ms))))
    lo, hi = max(0, i - 1), min(sm.size, i + 2)
    return float(t[i]), float(np.mean(sm[lo:hi]))


# Whether the robust detector's pre-stimulus noise gate was cleared, or the windowed fallback fired
# (A18). A fallback measurement is a real number that sat BELOW the noise gate — a reader must be
# able to tell those apart from gate-clearing ones.
GATE_CLEARED = "cleared"
GATE_FALLBACK = "fallback"


def _robust_auto_ab(t, arr, awin, bwin, fs, a_sm_ms, b_sm_ms):
    """Robust auto a-/b-wave seeds — the opt-in ``detector="robust"`` path for :func:`landmarks`.

    Savitzky-Golay smoothing + prominence-gated peak/trough picking with a noise gate at ~2× the
    pre-stimulus baseline's 95% band (``2 · 1.96 · SD_pre``): the b-wave is the tallest SavGol maximum
    inside the b-window that both clears the gate above baseline AND is a prominence-gated local peak
    (so a lone super-threshold sample or a sub-noise ripple can't masquerade as the b-wave); the
    a-wave is the deepest gated SavGol minimum inside the a-window, constrained to precede the b-peak.
    Each falls back to the windowed argmax/argmin when nothing clears the gate (a flat/noise eye), so
    the peak-to-trough construction still reads near the noise floor. Returns the SAME five quantities
    the windowed path computes — ``(auto_a_t, auto_a_val, auto_b_trough, auto_b_t, auto_b_peak)`` — so
    the caller's manual-override + return logic is shared verbatim between the two detectors, plus a
    sixth: ``gate`` = ``{"a": "cleared"|"fallback", "b": …, "threshold_uv": …}``, so a reader can tell
    which measurements cleared the noise gate and which came from the near-floor fallback (A18)."""
    import numpy as np
    from scipy.signal import find_peaks

    base_mask = t < _PRESTIM_MS
    if base_mask.any() and int(base_mask.sum()) > 1:
        pre = arr[base_mask]
        base, sd = float(pre.mean()), float(pre.std(ddof=1))
    else:
        base = float(arr[base_mask].mean()) if base_mask.any() else 0.0
        sd = 0.0
    gate = 2.0 * 1.96 * sd  # a real deflection must clear ~2× the 95% baseline-noise band

    sm_a = _savgol(arr, a_sm_ms, fs)
    sm_b = _savgol(arr, b_sm_ms, fs)

    # b-wave: the tallest prominence-gated SavGol maximum in the b-window clearing the noise gate.
    bm = (t >= bwin[0]) & (t <= bwin[1])
    if not bm.any():
        bm = t >= bwin[0]
    b_pos = np.where(bm)[0]
    seg_b = sm_b[b_pos]
    peaks, _ = find_peaks(seg_b, prominence=max(gate, 1e-9))
    gated = [p for p in peaks if seg_b[p] - base >= gate]
    if gated:
        bi = int(b_pos[max(gated, key=lambda p: seg_b[p])])
        b_gate = GATE_CLEARED
    else:
        bi = int(b_pos[int(np.argmax(seg_b))])  # fallback: windowed-style argmax
        b_gate = GATE_FALLBACK
    auto_b_t = float(t[bi])
    auto_b_peak = float(sm_b[bi])

    # a-wave: the deepest gated SavGol minimum in the a-window, constrained to precede the b-peak.
    am = (t >= awin[0]) & (t <= awin[1])
    if not am.any():
        am = t >= 0
    a_ref = am & (t <= auto_b_t)
    if not a_ref.any():
        a_ref = am
    a_pos = np.where(a_ref)[0]
    seg_a = sm_a[a_pos]
    troughs, _ = find_peaks(-seg_a, prominence=max(gate, 1e-9))
    gated_t = [q for q in troughs if base - seg_a[q] >= gate]
    if gated_t:
        ai = int(a_pos[min(gated_t, key=lambda q: seg_a[q])])
        a_gate = GATE_CLEARED
    else:
        ai = int(a_pos[int(np.argmin(seg_a))])  # fallback: windowed-style argmin
        a_gate = GATE_FALLBACK
    auto_a_t = float(t[ai])
    auto_a_val = float(sm_a[ai])
    # b subtracts from the a-window trough (ISCEV peak-to-trough), on the b-smoothed trace.
    auto_b_trough = float(np.min(sm_b[am]))
    return (auto_a_t, auto_a_val, auto_b_trough, auto_b_t, auto_b_peak,
            {"a": a_gate, "b": b_gate, "threshold_uv": round(gate, 3)})


def landmarks(time_ms, y, fs: float = 5000.0, *, mode: str = "scotopic",
              manual: dict | None = None, detector: str = "windowed") -> dict:
    """a/b-wave amplitudes (µV) + implicit times (ms), noise-rejecting dual smooth.

    a-wave = baseline − min(a-window) on a LIGHT trace (sharp trough preserved).
    b-wave = max(b-window) − min(a-window), BOTH on a HEAVIER trace — peak-to-trough, so a flat
    (noise-only) eye reads near the noise floor instead of mistaking a noise excursion for a
    b-wave. baseline = mean of the pre-stimulus window.

    ``mode`` selects the timing preset (``scotopic`` default — the validated rod windows that
    reproduced the Fig 1E ordering; ``photopic`` = the cone windows anchored to the published mouse
    cone-ERG timing). The cone a-wave is EARLY, so the photopic a-window is tight (0–25 ms); the cone
    b-wave peaks ~40–45 ms, so the b-window is (12–80 ms), centred on the cone range and deliberately
    NOT extended past ~80 ms (a ~100 ms "photopic b-wave" is rod/hum contamination, not cone — see
    the ``_PHOTOPIC_*`` constants). Unknown mode → scotopic (byte-identical legacy path).

    ``manual`` (docs/records/erg-manual-marks/spec.md) optionally overrides the a-wave and/or b-wave TIME:
    ``{"a_ms": …, "b_ms": …}`` (either or both). The amplitude is re-measured from the trace AT
    that time per ISCEV — a = baseline − value(a_ms); the manual a-trough also becomes the b-wave's
    reference, so b = value(b_ms) − value(a_ms). Each value is tagged ``a_source``/``b_source`` ∈
    {auto, manual}, and the auto seed times are always returned as ``a_auto_t_ms``/``b_auto_t_ms``
    (for the R6 provenance log). No ``manual`` → the measured a/b values and times are the pure-auto
    path (the override never runs) and the auto seeds equal ``a_t_ms``/``b_t_ms``.

    ``detector`` selects the AUTO seed algorithm. ``windowed`` (default) is the validated dual-smooth
    windowed argmin/argmax that produced the Fig 1E ordering — the byte-identical legacy path.
    ``robust`` is the opt-in SavGol + prominence peak-picking detector with a pre-stimulus noise gate
    (:func:`_robust_auto_ab`); it only changes the auto seeds, so the manual override, provenance, and
    return shape are unchanged. Unknown/absent → ``windowed``."""
    import numpy as np

    awin, bwin, a_sm, b_sm = _LANDMARK_MODES.get(str(mode or "scotopic").lower(), _LANDMARK_MODES["scotopic"])
    t = np.asarray(time_ms, dtype=float)
    arr = np.asarray(y, dtype=float)
    base = float(arr[t < _PRESTIM_MS].mean()) if (t < _PRESTIM_MS).any() else 0.0
    sm_a = _movavg(arr, max(1, int(round(a_sm / 1000.0 * fs))))
    sm_b = _movavg(arr, max(1, int(round(b_sm / 1000.0 * fs))))

    man = manual or {}
    a_ms = _num_or_none(man.get("a_ms"))
    b_ms = _num_or_none(man.get("b_ms"))

    # Auto a-wave (and the trough the b-wave subtracts from) + auto b-wave — computed even under a
    # manual override so the provenance log (erg-manual-marks R6) can report where the auto detector
    # WOULD have placed each mark (`a_auto_t_ms`/`b_auto_t_ms`) alongside the operator's set time. The
    # `robust` detector (opt-in) swaps only these seeds for SavGol + prominence peak-picking with a
    # noise gate; the default `windowed` branch is the byte-identical legacy computation.
    detector_name = "robust" if str(detector or "windowed").lower() == "robust" else "windowed"
    gate = None
    if detector_name == "robust":
        auto_a_t, auto_a_val, auto_b_trough, auto_b_t, auto_b_peak, gate = _robust_auto_ab(
            t, arr, awin, bwin, fs, a_sm, b_sm)
    else:
        am = (t >= awin[0]) & (t <= awin[1])
        if not am.any():
            am = t >= 0
        ai = int(np.argmin(sm_a[am]))
        auto_a_t = float(t[am][ai])
        auto_a_val = float(sm_a[am][ai])
        auto_b_trough = float(np.min(sm_b[am]))
        bm = (t >= bwin[0]) & (t <= bwin[1])
        if not bm.any():
            bm = t >= bwin[0]
        bi = int(np.argmax(sm_b[bm]))
        auto_b_t = float(t[bm][bi])
        auto_b_peak = float(sm_b[bm][bi])

    # a-wave + the trough the b-wave subtracts from. Manual a → measure at the set time and use that
    # as the b-trough (ISCEV: b = a-trough → b-peak); auto a → the windowed min.
    if a_ms is not None:
        a_t, a_val = _value_at(t, sm_a, a_ms)
        _, b_trough = _value_at(t, sm_b, a_ms)
        a_source = "manual"
    else:
        a_t, a_val, b_trough = auto_a_t, auto_a_val, auto_b_trough
        a_source = "auto"
    a_wave = base - a_val

    if b_ms is not None:
        b_t, b_peak = _value_at(t, sm_b, b_ms)
        b_source = "manual"
    else:
        b_t, b_peak = auto_b_t, auto_b_peak
        b_source = "auto"
    b_wave = b_peak - b_trough

    return {
        "a_wave_uv": round(a_wave, 2),
        "b_wave_uv": round(b_wave, 2),
        "a_t_ms": round(a_t, 1),
        "b_t_ms": round(b_t, 1),
        "a_source": a_source,
        "b_source": b_source,
        # Auto seed times (erg-manual-marks R6 provenance): where the auto detector placed each mark,
        # regardless of any manual override — equal to a_t_ms/b_t_ms on the pure-auto path.
        "a_auto_t_ms": round(auto_a_t, 1),
        "b_auto_t_ms": round(auto_b_t, 1),
        # WHICH detector produced those seeds, and (robust only) whether each mark cleared the
        # pre-stimulus noise gate or came from the near-floor fallback. The robust path measures
        # different amplitudes from the windowed one, so a published recipe that does not name it is
        # not reproducible (A18); a `robust` figure's methods paragraph reads this.
        "detector": detector_name,
        **({"detector_gate": gate} if gate is not None else {}),
    }


def detector_summary(landmark_results) -> dict | None:
    """Figure-level a/b-detector disclosure from a set of :func:`landmarks` results, or ``None``.

    ``None`` for the default windowed detector — it is exactly what the methods templates already
    describe, so a windowed figure's ``layout.meta`` (and therefore its methods paragraph and its
    golden) stays byte-identical. For ``robust`` it returns
    ``{"name", "n_segments", "a_fallback", "b_fallback", "threshold_uv_max"}``: how many segments
    were measured by the near-floor windowed fallback rather than by a gate-clearing deflection
    (A18). One aggregator here rather than one per ERG runner.
    """
    robust = [lm for lm in landmark_results if lm and lm.get("detector") == "robust"]
    if not robust:
        return None
    gates = [lm.get("detector_gate") or {} for lm in robust]
    thresholds = [float(g.get("threshold_uv") or 0.0) for g in gates]
    return {
        "name": "robust",
        "n_segments": len(robust),
        "a_fallback": sum(1 for g in gates if g.get("a") == GATE_FALLBACK),
        "b_fallback": sum(1 for g in gates if g.get("b") == GATE_FALLBACK),
        "threshold_uv_max": round(max(thresholds), 3) if thresholds else 0.0,
    }


# --- "could not measure" is not "measured zero" (A17) ------------------------
# Reserved reasons a measurement returns instead of a number. A 0.0 where the computation never ran
# is a scientific claim the data does not back — for OPs specifically, ΣOP = 0 IS the reading that
# indicates inner-retinal dysfunction.
NOT_MEASURABLE_TRACE_TOO_SHORT = "trace_too_short"
NOT_MEASURABLE_FILTER_FAILED = "filter_failed"
NOT_MEASURABLE_WINDOW_TOO_SMALL = "window_too_small"
NOT_MEASURABLE_BAND_UNAVAILABLE = "band_unavailable"


# --- Oscillatory potentials (OPs) --------------------------------------------
# OPs are the small high-frequency wavelets riding on the ascending limb of the b-wave (inner-retinal
# origin). The ISCEV standard extracts them with a band-pass that isolates the OP band (~75–300 Hz)
# from the slow a-/b-wave; the individual wavelets (OP1…OP4) are then measured peak-to-preceding-
# trough, and their SUM (ΣOP) plus an integrated RMS ("TOP") summarize inner-retinal function.
# Clean-room from the public ISCEV / ERGAssist method descriptions — no external code copied.

def oscillatory_potentials(time_ms, y, fs: float = 5000.0, *, low_hz: float = 75.0,
                           high_hz: float = 300.0, n_ops: int = 4, order: int = 2,
                           window=None) -> dict:
    """Oscillatory potentials from an ERG trace via a zero-phase 75–300 Hz band-pass.

    Filters ``y`` with a Butterworth band-pass (``scipy.signal.butter`` SOS + ``sosfiltfilt`` — the
    wavelets stay phase-true), keeps up to ``n_ops`` of the most prominent positive peaks
    (``find_peaks``), and measures each as ``peak − preceding trough`` (the ISCEV OP amplitude).
    Returns::

        {"op_amplitudes_uv": [OP1, OP2, …],   # peak-to-preceding-trough, ordered in time
         "op_times_ms":      [t1, t2, …],      # implicit time of each OP peak
         "op_sum_uv":  ΣOP,                     # sum of the wavelet amplitudes
         "op_rms_uv":  RMS,                     # integrated RMS of the band-passed signal (TOP)
         "n_ops":      k,                       # wavelets found (== len(op_amplitudes_uv))
         "measurable": True/False,              # did the band-pass actually run?
         "reason":     None | why not}          # NOT_MEASURABLE_* when measurable is False

    ``window`` optionally restricts the analysis to ``(lo_ms, hi_ms)`` (peaks + RMS measured there);
    default = the whole trace. ``high_hz`` is clamped just under Nyquist for low sample rates.

    **Never-measured is not zero (A17).** This used to return ``op_sum_uv=0.0`` / ``op_rms_uv=0.0``
    for three distinct situations — a trace too short to band-pass, a filter that could not run, and
    a window with too few samples — all of which are "could not measure". A ΣOP of 0 is a scientific
    CLAIM of zero oscillatory activity, the reading that indicates inner-retinal dysfunction, and a
    group mean over eyes would silently absorb unmeasurable traces as zeros. Those cases now return
    ``op_sum_uv``/``op_rms_uv`` of ``None`` with ``measurable=False`` and a ``reason``; ``0.0`` is
    reserved for a trace that filtered successfully and carried no OP-band deflection (a plain slow
    b-wave — a real, measured zero). Still never raises.

    :func:`op_group_mean` is the honest aggregator over a set of these results."""
    import numpy as np
    from scipy.signal import butter, find_peaks, sosfiltfilt

    t = np.asarray(time_ms, dtype=float)
    arr = np.asarray(y, dtype=float)
    n = arr.size

    def _not_measurable(reason):
        return {"op_amplitudes_uv": [], "op_times_ms": [], "op_sum_uv": None,
                "op_rms_uv": None, "n_ops": 0, "measurable": False, "reason": reason}

    nyq = 0.5 * float(fs)
    hi = min(float(high_hz), nyq * 0.99)
    if n < 24 or nyq <= 0 or low_hz <= 0 or hi <= low_hz:
        return _not_measurable(NOT_MEASURABLE_TRACE_TOO_SHORT if n < 24
                               else NOT_MEASURABLE_BAND_UNAVAILABLE)
    sos = butter(int(order), [float(low_hz) / nyq, hi / nyq], btype="band", output="sos")
    try:
        band = sosfiltfilt(sos, arr)
    except ValueError:
        # signal shorter than the filter padding → the band-pass never ran
        return _not_measurable(NOT_MEASURABLE_FILTER_FAILED)
    wm = ((t >= float(window[0])) & (t <= float(window[1]))) if window is not None \
        else np.ones(t.shape, dtype=bool)
    if int(wm.sum()) < 5:
        return _not_measurable(NOT_MEASURABLE_WINDOW_TOO_SMALL)
    tw, bw = t[wm], band[wm]
    rms = float(np.sqrt(np.mean(bw ** 2)))
    peaks, props = find_peaks(bw, prominence=1e-9)
    troughs, _ = find_peaks(-bw)
    if peaks.size == 0:
        # The band-pass RAN and found no wavelet: a real, measured zero (not "unknown").
        return {"op_amplitudes_uv": [], "op_times_ms": [], "op_sum_uv": 0.0,
                "op_rms_uv": round(rms, 3), "n_ops": 0, "measurable": True, "reason": None}
    # Keep the n_ops most prominent wavelets, then order them in time (OP1…OPk).
    keep = np.argsort(props["prominences"])[::-1][: max(1, int(n_ops))]
    sel = np.sort(peaks[keep])
    amps, times = [], []
    for p in sel:
        prior = troughs[troughs < p]
        if prior.size:
            trough_val = float(bw[prior[-1]])
        else:
            trough_val = float(bw[:p].min()) if p > 0 else float(bw[p])
        amps.append(round(float(bw[p]) - trough_val, 3))
        times.append(round(float(tw[p]), 2))
    return {"op_amplitudes_uv": amps, "op_times_ms": times,
            "op_sum_uv": round(float(sum(amps)), 3), "op_rms_uv": round(rms, 3),
            "n_ops": len(amps), "measurable": True, "reason": None}


# Human-readable labels for the not-measurable reasons — what a table cell or a methods sentence
# says instead of a number, so "not measurable" never renders as 0.
NOT_MEASURABLE_LABELS = {
    NOT_MEASURABLE_TRACE_TOO_SHORT: "trace too short to band-pass",
    NOT_MEASURABLE_FILTER_FAILED: "band-pass filter could not run on this trace",
    NOT_MEASURABLE_WINDOW_TOO_SMALL: "analysis window carried too few samples",
    NOT_MEASURABLE_BAND_UNAVAILABLE: "sample rate too low for the OP band",
}


def op_group_mean(results, key: str = "op_sum_uv") -> dict:
    """Mean of an OP metric over a set of :func:`oscillatory_potentials` results — EXCLUDING the
    unmeasurable ones, and saying how many it excluded.

    The aggregation half of A17: a mean that treats "could not measure" as 0.0 silently drags a
    group towards the reading that indicates inner-retinal dysfunction. Returns
    ``{"mean", "n", "n_not_measurable", "reasons"}`` with ``mean=None`` when nothing was measurable
    — an honest blank, never a fabricated zero.
    """
    vals = [r.get(key) for r in results if r and r.get("measurable") and r.get(key) is not None]
    skipped = [r.get("reason") for r in results if r and not r.get("measurable")]
    return {
        "mean": (round(float(sum(vals)) / len(vals), 3) if vals else None),
        "n": len(vals),
        "n_not_measurable": len(skipped),
        "reasons": sorted({r for r in skipped if r}),
    }


# --- Photopic negative response (PhNR) ---------------------------------------
# The PhNR is the slow negative wave that follows the b-wave in the light-adapted (photopic) ERG;
# it reflects retinal-ganglion-cell / inner-retinal function and is reduced in glaucoma and optic-
# nerve disease. Three amplitudes are in common use (Frishman / ISCEV descriptions): BT (baseline →
# PhNR trough), BF (baseline → the value at a FIXED post-flash time ~72 ms, robust when the trough is
# ill-defined), and PT (b-peak → PhNR trough). Clean-room from the public method descriptions.

def photopic_negative_response(time_ms, y, fs: float = 5000.0, *, fixed_ms: float = 72.0,
                               b_window_ms=(12.0, 80.0), trough_window_ms=None) -> dict | None:
    """PhNR amplitudes (µV) on a light-adapted ERG trace → BT / BF / PT.

    baseline = the pre-stimulus mean; the b-wave peak is the max within ``b_window_ms`` (the cone-ERG
    b-window); the PhNR trough is the minimum AFTER the b-wave peak (within ``trough_window_ms`` when
    given, else from the b-peak to the end of the trace). Returns::

        {"phnr_bt_uv": baseline − trough,           # baseline-to-trough
         "phnr_bf_uv": baseline − value(fixed_ms),  # baseline-to-fixed-time (~72 ms)
         "phnr_pt_uv": b_peak − trough,             # peak-to-trough
         "trough_t_ms": …, "b_peak_t_ms": …, "baseline_uv": …, "fixed_ms": …}

    A positive BT/BF means the trough sits BELOW baseline (the normal PhNR). None when there is no
    post-b-wave segment to measure (never raises)."""
    import numpy as np

    t = np.asarray(time_ms, dtype=float)
    arr = np.asarray(y, dtype=float)
    if t.size < 4:
        return None
    base = float(arr[t < _PRESTIM_MS].mean()) if (t < _PRESTIM_MS).any() else 0.0
    bm = (t >= b_window_ms[0]) & (t <= b_window_ms[1])
    if not bm.any():
        bm = t >= 0
    b_pos = np.where(bm)[0]
    bpk = int(b_pos[int(np.argmax(arr[b_pos]))])
    b_peak_t, b_peak_v = float(t[bpk]), float(arr[bpk])
    if trough_window_ms is not None:
        tm = (t >= float(trough_window_ms[0])) & (t <= float(trough_window_ms[1]))
    else:
        tm = t > b_peak_t
    if not tm.any():
        return None
    tr_pos = np.where(tm)[0]
    tri = int(tr_pos[int(np.argmin(arr[tr_pos]))])
    trough_t, trough_v = float(t[tri]), float(arr[tri])
    fi = int(np.argmin(np.abs(t - float(fixed_ms))))
    lo, hi = max(0, fi - 1), min(arr.size, fi + 2)
    fixed_v = float(np.mean(arr[lo:hi]))
    return {"phnr_bt_uv": round(base - trough_v, 2),
            "phnr_bf_uv": round(base - fixed_v, 2),
            "phnr_pt_uv": round(b_peak_v - trough_v, 2),
            "trough_t_ms": round(trough_t, 1),
            "b_peak_t_ms": round(b_peak_t, 1),
            "baseline_uv": round(base, 2),
            "fixed_ms": round(float(fixed_ms), 1)}


def fs_from(time_ms) -> float:
    """Sampling rate (Hz) inferred from a time axis (ms). 5000 Hz default for a degenerate axis."""
    if len(time_ms) < 2:
        return 5000.0
    dt = float(time_ms[1]) - float(time_ms[0])
    return 1000.0 / dt if dt else 5000.0


# --- Manual landmark marks (operator override) -------------------------------
# docs/records/erg-manual-marks/spec.md: the scientist sets/moves the a/b (or N1/P1) TIME on a trace;
# the metric re-measures AT that time. The marks travel as a JSON param keyed by the segment
# identity "{condition}|{stimulus_type}|{intensity_group}|{eye}" (flicker: "{condition}|{hz}|{eye}").
# Empty key parts are wildcards, so a grid-panel mark (no eye) applies to every eye of that
# condition×intensity in the per-eye bar. Tolerant: a bad entry is skipped, never raised.
_MARK_FIELDS = ("a_ms", "b_ms", "n1_ms", "p1_ms")


def _num_or_none(v):
    """Coerce to a finite float, else None (a non-numeric / NaN mark is ignored, not raised)."""
    import math

    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (ValueError, TypeError):
        return None
    return f if math.isfinite(f) else None


def parse_manual_marks(raw) -> dict:
    """Parse a ``manual_marks`` param → ``{segment_key: {field: ms}}`` (tolerant, never raises).

    Accepts a JSON object string (how the param travels), an already-parsed dict, or ""/None →
    ``{}``. Each value keeps only the numeric :data:`_MARK_FIELDS` (``a_ms``/``b_ms``/``n1_ms``/
    ``p1_ms``); a key with no usable field, or any malformed entry, is dropped."""
    import json

    if not raw:
        return {}
    obj = raw
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
        except (ValueError, TypeError):
            return {}
    if not isinstance(obj, dict):
        return {}
    out: dict = {}
    for key, val in obj.items():
        if not isinstance(val, dict):
            continue
        fields = {f: _num_or_none(val.get(f)) for f in _MARK_FIELDS}
        fields = {f: v for f, v in fields.items() if v is not None}
        if fields:
            out["|".join(p.strip() for p in str(key).split("|"))] = fields
    return out


def segment_key(*parts) -> str:
    """Canonical segment key from ordered identity parts (missing → "")."""
    return "|".join("" if p is None else str(p) for p in parts)


def marks_for(marks: dict | None, *parts) -> dict | None:
    """Look up a segment's manual marks by its ordered identity ``parts``.

    Exact key match first, then a relaxed positional match where an empty stored part is a
    wildcard (a grid mark "cond||group|" matches a per-eye segment "cond|stim|group|RE"). Returns
    the ``{field: ms}`` dict or None."""
    if not marks:
        return None
    want = [("" if p is None else str(p)) for p in parts]
    exact = marks.get("|".join(want))
    if exact is not None:
        return exact
    for key, val in marks.items():
        stored = key.split("|")
        if len(stored) != len(want):
            continue
        if all(s == "" or s == w for s, w in zip(stored, want)):
            return val
    return None


# --- Manual-marks provenance (erg-manual-marks R6) ---------------------------
# The measured a/b (N1/P1) values already carry an `auto`/`manual` source tag; R6 aggregates those
# into a per-run provenance log so a figure is auditable — for each marker: where the auto detector
# placed it, where it was finally measured, and whether the operator moved it. The log rides the
# figure's render-inert `meta.selom.markProvenance` (recorded in the reproducibility config); the
# skills also state the operator-adjusted mix in the attached table caption. Both are emitted ONLY
# when a mark actually moved, so a run with no manual_marks stays byte-identical (goldens unchanged).

def provenance_entry(segment: str, marker: str, auto_ms, set_ms, source: str) -> dict:
    """One per-marker provenance record → ``{segment, marker, auto_ms, set_ms, moved}``.

    ``segment`` = the segment-identity key; ``marker`` = the role (``a``/``b``/``n1``/``p1``);
    ``auto_ms`` = where the auto detector placed the mark; ``set_ms`` = where it was finally measured
    (the operator's set time when moved, else the auto time); ``moved`` = the operator adjusted it
    (``source == "manual"``)."""
    return {
        "segment": segment,
        "marker": marker,
        "auto_ms": auto_ms,
        "set_ms": set_ms,
        "moved": source == "manual",
    }


def operator_adjusted_note(n_moved: int, n_total: int) -> str:
    """Table-caption fragment stating the operator-adjusted mix (R6), e.g.
    ``", 3 of 12 operator-adjusted"``. Empty when nothing moved → the caption (and the default-path
    golden) stays byte-identical."""
    return f", {int(n_moved)} of {int(n_total)} operator-adjusted" if n_moved else ""


def metrics_from_waveforms(df, *, default_mode: str = "scotopic", marks: dict | None = None,
                           detector: str = "windowed"):
    """``erg_waveforms_long`` → a per-eye a/b metrics frame measured FROM the traces.

    One trace per (sample × condition × stimulus × intensity × eye) → one :func:`landmarks`
    measurement → one row carrying ``a_wave_uv`` + ``b_wave_uv`` (and the intensity/stimulus columns
    passed through). This is the fan-out path the owner asked for — the bar and intensity-response
    run straight off the dropped recording at the chosen intensity, using the same a/b metric the
    trace grid reports, instead of needing a separate device-metrics CSV. Device markers stay
    preferred when a metrics table IS supplied (the caller checks for the marker column first).

    The landmark MODE (scotopic vs photopic/cone windows) is chosen per segment from its own
    ``stimulus_type`` (``photopic_flash`` → cone windows), so a mixed scotopic+photopic cohort
    measures each mode with the right timing; ``default_mode`` applies when there is no
    ``stimulus_type`` column (a plain waveform CSV — the caller passes the user's ``adaptation``).

    ``marks`` (docs/records/erg-manual-marks/spec.md) optionally carries operator-set a/b times keyed by the
    segment identity ``(condition, stimulus_type, intensity_group, eye)``; a matched segment is
    measured AT those times and its row carries ``a_source``/``b_source`` ∈ {auto, manual}. No
    ``marks`` → byte-identical (every row ``auto``).

    ``detector`` picks the a/b AUTO seed algorithm passed to :func:`landmarks` — ``windowed`` (default,
    byte-identical) or the opt-in ``robust`` SavGol/prominence detector."""
    import pandas as pd

    # stimulus_type is a grouping key when present so the two modes' shared GroupN labels never merge.
    keys = [k for k in ("sample_id", "condition", "stimulus_type", "intensity_group", "eye")
            if k in df.columns]
    if "condition" not in keys or "intensity_group" not in keys:
        return df  # not a recognizable waveform grouping → let the caller's column check fail honestly
    carry = [c for c in ("intensity_log_cd_s_m2", "stimulus_type", "condition_order")
             if c in df.columns and c not in keys]
    rows = []
    for kv, seg in df.groupby(keys, dropna=False):
        seg = seg.sort_values("time_ms")
        t = seg["time_ms"].astype(float).tolist()
        y = seg["voltage_uv"].astype(float).tolist()
        if len(t) < 4:
            continue
        mode = default_mode
        if "stimulus_type" in seg.columns:
            svals = seg["stimulus_type"].dropna().astype(str)
            if not svals.empty:
                mode = _STIM_ADAPT.get(svals.iloc[0], default_mode)
        rec = dict(zip(keys, kv if isinstance(kv, tuple) else (kv,)))
        manual = marks_for(marks, rec.get("condition"), rec.get("stimulus_type"),
                           rec.get("intensity_group"), rec.get("eye"))
        lm = landmarks(t, y, fs=fs_from(t), mode=mode, manual=manual, detector=detector)
        rec["a_wave_uv"] = lm["a_wave_uv"]
        rec["b_wave_uv"] = lm["b_wave_uv"]
        rec["a_source"] = lm["a_source"]
        rec["b_source"] = lm["b_source"]
        # A18 — carry the detector + its per-segment noise-gate outcome through to the runner, which
        # aggregates them with `detector_summary` into the figure's disclosure. Written ONLY under
        # the opt-in `robust` detector, so the default frame keeps exactly the columns it had.
        if lm.get("detector") == "robust":
            rec["detector"] = lm["detector"]
            rec["detector_gate"] = lm.get("detector_gate")
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


def adaptation_mode(adaptation: str = "auto", stimulus_type: str = "") -> str:
    """Map the friendly ``adaptation`` hint (or an explicit ``stimulus_type``) to a landmark MODE
    (``scotopic``/``photopic``) for :func:`landmarks` / :func:`metrics_from_waveforms`.

    This is the *default* mode used when the waveform table carries no per-row ``stimulus_type``
    column (a plain CSV); auto/unknown → ``scotopic`` (the back-compatible default). When the data
    DOES carry ``stimulus_type``, :func:`metrics_from_waveforms` reads it per segment and overrides
    this default, so a real photopic iWorx/Diagnosys feed measures with cone windows automatically."""
    _, adapt = resolve_flash_mode([], adaptation, stimulus_type)
    return adapt or "scotopic"


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
                      start_ms: float = 0.0, manual: dict | None = None) -> dict | None:
    """N1→P1 on the phase-folded steady-state cycle: N1 = the trough, P1 = the following peak.

    Returns ``{n1p1_uv, p1_implicit_ms, n1_implicit_ms, n1_uv, p1_uv, n1_source, p1_source,
    n1_auto_ms, p1_auto_ms}`` (µV / ms; the ``*_auto_ms`` are the pure-auto seed phases for the R6
    provenance log), or None when no cycle could be formed. ``n1p1_uv`` is the peak-to-trough amplitude
    (the ISCEV flicker measure); ``p1_implicit_ms`` is the P1 phase within the cycle.

    ``manual`` (docs/records/erg-manual-marks/spec.md) optionally overrides the N1 and/or P1 TIME
    (``{"n1_ms": …, "p1_ms": …}``), interpreted as a phase within the cycle (mod the period); the
    amplitude is re-read at that phase and the value tagged ``n1_source``/``p1_source`` ∈
    {auto, manual}. No ``manual`` → byte-identical to the auto path."""
    import numpy as np

    ph, cyc = flicker_cycle(time_ms, voltage, hz, n_bins=n_bins, start_ms=start_ms)
    if len(cyc) < 3:
        return None
    cyc_a = np.asarray(cyc, dtype=float)
    ph_a = np.asarray(ph, dtype=float)
    period = 1000.0 / float(hz) if hz else 0.0
    man = manual or {}
    n1_ms = _num_or_none(man.get("n1_ms"))
    p1_ms = _num_or_none(man.get("p1_ms"))

    # Pure-auto N1 (trough) + P1 (peak after it) — computed even under a manual override so the
    # provenance log (erg-manual-marks R6) can report the auto seed phases (`n1_auto_ms`/`p1_auto_ms`).
    auto_ni = int(np.argmin(cyc_a))
    auto_after = np.arange(auto_ni, cyc_a.size)
    auto_pi = int(auto_after[int(np.argmax(cyc_a[auto_after]))])

    # N1 first (auto trough, or the bin nearest the operator's phase), then P1 (auto peak AFTER N1,
    # or the operator's phase) — so the "P1 follows N1" relationship holds under a partial override.
    if n1_ms is not None and period > 0:
        ni = int(np.argmin(np.abs(ph_a - (float(n1_ms) % period))))
        n1_source = "manual"
    else:
        ni = auto_ni
        n1_source = "auto"
    if p1_ms is not None and period > 0:
        pi = int(np.argmin(np.abs(ph_a - (float(p1_ms) % period))))
        p1_source = "manual"
    else:
        after = np.arange(ni, cyc_a.size)
        pi = int(after[int(np.argmax(cyc_a[after]))])
        p1_source = "auto"
    return {
        "n1p1_uv": round(float(cyc_a[pi] - cyc_a[ni]), 3),
        "p1_implicit_ms": round(float(ph[pi]), 1),
        "n1_implicit_ms": round(float(ph[ni]), 1),
        "n1_uv": round(float(cyc_a[ni]), 3),
        "p1_uv": round(float(cyc_a[pi]), 3),
        "n1_source": n1_source,
        "p1_source": p1_source,
        # Auto seed phases (R6 provenance) — equal to n1/p1_implicit_ms on the pure-auto path.
        "n1_auto_ms": round(float(ph[auto_ni]), 1),
        "p1_auto_ms": round(float(ph[auto_pi]), 1),
    }


def flicker_fundamental(time_ms, voltage, hz: float, fs: float | None = None, *,
                        start_ms: float = 0.0) -> dict | None:
    """Fundamental Fourier component of a steady-state flicker response at the flicker frequency.

    Complements the phase-fold :func:`flicker_landmarks` N1→P1 (a time-domain trough-to-peak) with
    the frequency-domain measure the flicker ERG is classically quantified by: the ``numpy.fft.rfft``
    magnitude + phase at ``hz`` (the first-harmonic response). Uses samples at ``time_ms >=
    start_ms``; ``fs`` is inferred from the time axis when not given; the DC term is removed so a
    baseline offset does not bias the fundamental. Returns::

        {"fundamental_hz": bin_freq,   # the rfft bin nearest hz (may differ from hz if the record is
                                        #   not an integer number of cycles)
         "magnitude_uv":  A,           # sinusoidal amplitude at hz  = 2·|X[k]| / N
         "phase_deg":     φ,           # phase of that component (degrees, −180…180)
         "phase_rad":     φ,           # …and radians
         "target_hz":     hz}

    None when ``hz`` ≤ 0 or there are too few post-onset samples to transform (never raises)."""
    import numpy as np

    if hz is None or float(hz) <= 0:
        return None
    t = np.asarray(time_ms, dtype=float)
    v = np.asarray(voltage, dtype=float)
    m = (t >= float(start_ms)) & np.isfinite(t) & np.isfinite(v)
    t, v = t[m], v[m]
    if v.size < 4:
        return None
    sr = float(fs) if fs else fs_from(t)
    spec = np.fft.rfft(v - v.mean())  # drop DC so the fundamental isn't biased by a baseline offset
    freqs = np.fft.rfftfreq(v.size, d=1.0 / sr)
    k = int(np.argmin(np.abs(freqs - float(hz))))
    comp = spec[k]
    mag = 2.0 * float(np.abs(comp)) / v.size
    phase = float(np.angle(comp))
    return {"fundamental_hz": round(float(freqs[k]), 3),
            "magnitude_uv": round(mag, 4),
            "phase_deg": round(float(np.degrees(phase)), 2),
            "phase_rad": round(phase, 4),
            "target_hz": round(float(hz), 3)}


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
