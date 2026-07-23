"""Photopic negative response (PhNR) — `_erg.photopic_negative_response`.

The PhNR is the slow negative wave after the b-wave in the light-adapted ERG. Three amplitudes:
BT (baseline→trough), BF (baseline→value at a fixed ~72 ms), PT (b-peak→trough). CI-safe (pure
numpy): a synthetic photopic trace with an early cone b-wave (~35 ms) and a PhNR trough (~72 ms)
below baseline exercises all three.
"""

import math

from skills import _erg


def _photopic(tm, b_amp=150.0, phnr_amp=40.0):
    a = -20.0 * math.exp(-((tm - 12.0) / 4.0) ** 2)     # small early cone a-wave
    b = b_amp * math.exp(-((tm - 35.0) / 8.0) ** 2)     # early cone b-wave peak ~35 ms
    phnr = -phnr_amp * math.exp(-((tm - 72.0) / 12.0) ** 2)  # PhNR trough ~72 ms below baseline
    return a + b + phnr


def _trace(**kw):
    t = [float(x) for x in range(0, 121)]
    return t, [_photopic(tm, **kw) for tm in t]


def test_phnr_three_amplitudes():
    t, y = _trace()
    r = _erg.photopic_negative_response(t, y, fs=1000.0)
    assert r is not None
    # b-wave timed ~35 ms; PhNR trough ~72 ms.
    assert abs(r["b_peak_t_ms"] - 35.0) <= 3.0
    assert abs(r["trough_t_ms"] - 72.0) <= 4.0
    # All three amplitudes positive (trough sits below baseline; b-peak above it).
    assert r["phnr_bt_uv"] > 0 and r["phnr_bf_uv"] > 0 and r["phnr_pt_uv"] > 0
    # PT (b-peak → trough) spans the full b-to-trough swing → larger than baseline-to-trough.
    assert r["phnr_pt_uv"] > r["phnr_bt_uv"]
    # BF is measured near the trough's fixed time, so it tracks BT closely here.
    assert r["phnr_bf_uv"] == _approx(r["phnr_bt_uv"], rel=0.15)
    assert r["fixed_ms"] == 72.0


def test_phnr_deeper_trough_grows_bt_and_pt():
    _, y_shallow = _trace(phnr_amp=20.0)
    _, y_deep = _trace(phnr_amp=60.0)
    t = [float(x) for x in range(0, 121)]
    shallow = _erg.photopic_negative_response(t, y_shallow, fs=1000.0)
    deep = _erg.photopic_negative_response(t, y_deep, fs=1000.0)
    assert deep["phnr_bt_uv"] > shallow["phnr_bt_uv"]
    assert deep["phnr_pt_uv"] > shallow["phnr_pt_uv"]


def test_phnr_fixed_time_param_moves_bf():
    t, y = _trace()
    at72 = _erg.photopic_negative_response(t, y, fs=1000.0, fixed_ms=72.0)
    at100 = _erg.photopic_negative_response(t, y, fs=1000.0, fixed_ms=100.0)
    # At 100 ms the trace has recovered toward baseline → BF is smaller than at the 72 ms trough.
    assert at100["fixed_ms"] == 100.0
    assert at100["phnr_bf_uv"] < at72["phnr_bf_uv"]


def test_phnr_none_when_no_post_bwave_segment():
    # b-window covers the whole (tiny) trace → no samples after the b-peak → honest None.
    assert _erg.photopic_negative_response([0.0, 1.0, 2.0, 3.0], [0.0, 1.0, 2.0, 3.0],
                                           fs=1000.0, b_window_ms=(0.0, 3.0)) is None
    assert _erg.photopic_negative_response([0.0], [0.0], fs=1000.0) is None


def _approx(v, rel=1e-3):
    import pytest

    return pytest.approx(v, rel=rel, abs=1e-9)
