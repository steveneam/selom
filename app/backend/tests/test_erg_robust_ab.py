"""Robust auto a/b detection as an OPT-IN mode — `_erg.landmarks(detector="robust")`.

The default windowed detector (argmin/argmax on a dual-smoothed trace) stays the byte-identical
legacy path; the opt-in `robust` detector uses SavGol + prominence peak-picking with a pre-stimulus
noise gate. These tests prove (1) robust recovers the a/b on a clean trace, (2) the windowed default
is unchanged, (3) the noise gate keeps a flat eye near the floor, and (4) the opt-in param threads
through `metrics_from_waveforms` + the bar run_real while the default stays byte-identical.
"""

import csv
import math
import random

from skills import _erg


def _ab_trace(amp=300.0):
    t = [float(x) for x in range(0, 121)]
    y = [amp * (math.exp(-((tm - 70.0) / 14.0) ** 2) - 0.35 * math.exp(-((tm - 30.0) / 6.0) ** 2))
         for tm in t]
    return t, y


def test_robust_detector_recovers_a_and_b_on_a_clean_trace():
    t, y = _ab_trace()
    win = _erg.landmarks(t, y, fs=1000.0)
    rob = _erg.landmarks(t, y, fs=1000.0, detector="robust")
    # Both detectors time the a-wave ~30 ms and the b-wave ~70 ms.
    assert abs(rob["a_t_ms"] - 30.0) <= 2.0 and abs(rob["b_t_ms"] - 70.0) <= 2.0
    assert abs(win["a_t_ms"] - rob["a_t_ms"]) <= 2.0
    assert abs(win["b_t_ms"] - rob["b_t_ms"]) <= 2.0
    # Substantial, positive amplitudes in the same ballpark as the windowed detector (±30 %).
    assert rob["a_wave_uv"] > 50.0 and rob["b_wave_uv"] > 200.0
    assert 0.7 * win["b_wave_uv"] <= rob["b_wave_uv"] <= 1.3 * win["b_wave_uv"]


def test_windowed_default_is_byte_identical():
    t, y = _ab_trace()
    win = _erg.landmarks(t, y, fs=1000.0)
    assert _erg.landmarks(t, y, fs=1000.0, detector="windowed") == win
    assert _erg.landmarks(t, y, fs=1000.0) == win                # default arg
    assert _erg.landmarks(t, y, fs=1000.0, detector="nonsense") == win  # unknown → windowed


def test_robust_noise_gate_keeps_a_flat_eye_near_the_floor():
    """A pure-noise eye (no real deflection) reads far below a real b-wave under the robust gate."""
    t, y = _ab_trace()
    real = _erg.landmarks(t, y, fs=1000.0, detector="robust")
    rng = random.Random(1)
    noise = [rng.gauss(0.0, 5.0) for _ in t]
    flat = _erg.landmarks(t, noise, fs=1000.0, detector="robust")
    assert flat["b_wave_uv"] < 0.1 * real["b_wave_uv"]          # noise gate → near-floor b-wave


def test_robust_detector_honours_manual_override():
    t, y = _ab_trace()
    moved = _erg.landmarks(t, y, fs=1000.0, detector="robust", manual={"b_ms": 50.0})
    assert moved["b_source"] == "manual" and abs(moved["b_t_ms"] - 50.0) <= 1.0
    assert moved["a_source"] == "auto"
    # The auto seed (robust) is still reported for the provenance log.
    assert moved["b_auto_t_ms"] == _erg.landmarks(t, y, fs=1000.0, detector="robust")["b_t_ms"]


def test_metrics_from_waveforms_detector_passthrough():
    import pandas as pd

    cols = ["condition", "intensity_group", "time_ms", "voltage_uv"]
    t, y = _ab_trace()
    rows = [("Control", "Group4", tm, round(v, 3)) for tm, v in zip(t, y)]
    df = pd.DataFrame(rows, columns=cols)
    win = _erg.metrics_from_waveforms(df, default_mode="scotopic")
    rob = _erg.metrics_from_waveforms(df, default_mode="scotopic", detector="robust")
    # Default passthrough == windowed; robust is a real measurement (positive b-wave).
    assert float(win["b_wave_uv"].iloc[0]) > 0
    assert float(rob["b_wave_uv"].iloc[0]) > 0
    assert win["a_source"].iloc[0] == "auto" and rob["a_source"].iloc[0] == "auto"


def _write_waveforms(path, amp_a=300.0, amp_b=80.0):
    def _rows(cond, amp):
        out = []
        for t in range(0, 121):
            a = math.exp(-((t - 30.0) / 6.0) ** 2)
            b = math.exp(-((t - 70.0) / 14.0) ** 2)
            out.append((cond, "Group4", t, round(amp * (b - 0.35 * a), 3), 1.0))
        return out
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "intensity_group", "time_ms", "voltage_uv", "intensity_log_cd_s_m2"])
        w.writerows(_rows("Control", amp_a) + _rows("Untreated", amp_b))


def test_erg_bwave_bar_ab_detector_wiring(tmp_path):
    """The bar's `ab_detector` param reaches the measure-from-traces path: default (windowed) is
    byte-identical to omitting it; `robust` still produces a valid bar (opt-in, non-breaking)."""
    from skills.proprietary.erg_bwave_bar.run_real import run as run_bar

    p = tmp_path / "wave.csv"
    _write_waveforms(p)
    base = run_bar(str(p), {"intensity_group": "Group4", "wave": "b"})
    windowed = run_bar(str(p), {"intensity_group": "Group4", "wave": "b", "ab_detector": "windowed"})
    robust = run_bar(str(p), {"intensity_group": "Group4", "wave": "b", "ab_detector": "robust"})
    assert windowed == base                                     # default-off invariant
    b_means = robust["data"][0]["y"]
    assert len(b_means) == 2 and b_means[0] > b_means[1] > 0     # Control > Untreated, both positive


def _approx(v, rel=1e-3):
    import pytest

    return pytest.approx(v, rel=rel, abs=1e-9)
