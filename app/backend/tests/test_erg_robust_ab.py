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


# --- A18: the robust detector must DISCLOSE itself --------------------------------------------
# `robust` selects a materially different measurement (SavGol + prominence-gated peak picking
# behind a 2 x 1.96 x SD pre-stimulus noise gate, falling back to the windowed extremum), so the
# amplitudes and implicit times differ from the default. The methods templates described only the
# windowed construction: a reader given that paragraph could not reproduce a `robust` number.

def test_landmarks_record_which_detector_ran_and_whether_the_gate_cleared():
    t, y = _ab_trace()
    win = _erg.landmarks(t, y, fs=1000.0)
    rob = _erg.landmarks(t, y, fs=1000.0, detector="robust")

    assert win["detector"] == "windowed" and "detector_gate" not in win
    assert rob["detector"] == "robust"
    assert rob["detector_gate"]["a"] == _erg.GATE_CLEARED      # a real deflection clears the gate
    assert rob["detector_gate"]["b"] == _erg.GATE_CLEARED
    assert rob["detector_gate"]["threshold_uv"] >= 0.0

    # a flat, noise-only eye: the gate is NOT cleared and the windowed fallback fires — a real
    # number that sat at the noise floor, and it must be visible as such.
    rng = random.Random(1)
    flat = _erg.landmarks(t, [rng.gauss(0.0, 5.0) for _ in t], fs=1000.0, detector="robust")
    assert flat["detector_gate"]["b"] == _erg.GATE_FALLBACK


def test_detector_summary_is_none_for_the_windowed_default():
    """Nothing is written for `windowed` — the templates already describe it exactly, so every
    existing figure's layout.meta (and its golden) stays byte-identical."""
    t, y = _ab_trace()
    assert _erg.detector_summary([_erg.landmarks(t, y, fs=1000.0)]) is None
    assert _erg.detector_summary([]) is None


def test_detector_summary_counts_the_segments_that_fell_back():
    t, y = _ab_trace()
    rng = random.Random(1)
    real = _erg.landmarks(t, y, fs=1000.0, detector="robust")
    flat = _erg.landmarks(t, [rng.gauss(0.0, 5.0) for _ in t], fs=1000.0, detector="robust")
    s = _erg.detector_summary([real, real, flat])
    assert s["name"] == "robust" and s["n_segments"] == 3
    assert s["b_fallback"] == 1 and s["threshold_uv_max"] > 0.0


def test_the_figure_and_its_methods_paragraph_both_name_the_robust_detector(tmp_path):
    from companions import methods
    from skills.proprietary.erg_bwave_bar.run_real import run as run_bar
    from skills.registry import load_skill

    p = tmp_path / "wave.csv"
    _write_waveforms(p)
    spec = load_skill("erg_bwave_bar")

    windowed_params = {"intensity_group": "Group4", "wave": "b", "ab_detector": "windowed"}
    robust_params = {**windowed_params, "ab_detector": "robust"}
    win_fig = run_bar(str(p), windowed_params)
    rob_fig = run_bar(str(p), robust_params)

    # the figure records it (robust only — the windowed figure is unchanged)
    assert "ab_detector" not in (win_fig["layout"].get("meta") or {})
    assert rob_fig["layout"]["meta"]["ab_detector"]["name"] == "robust"

    win_txt, _ = methods.build_body(spec, windowed_params, figure=win_fig)
    rob_txt, _ = methods.build_body(spec, robust_params, figure=rob_fig)
    assert "Savitzky-Golay" not in win_txt          # the default prose is untouched
    assert "robust detector" in rob_txt and "Savitzky-Golay" in rob_txt
    assert "2 x 1.96 x SD" in rob_txt and "windowed extremum" in rob_txt
    assert "measured segment(s)" in rob_txt         # the gate outcome, from layout.meta


def test_methods_names_the_detector_even_replaying_from_params_only():
    """litsynth replays recorded params with no figure: the construction must still be disclosed —
    the param alone proves a different measurement ran."""
    from companions import methods
    from skills.registry import load_skill

    spec = load_skill("erg_traces")
    txt, _ = methods.build_body(spec, {"ab_detector": "robust"})
    assert "Savitzky-Golay" in txt
    assert "measured segment(s)" not in txt         # ...but no outcome is invented
