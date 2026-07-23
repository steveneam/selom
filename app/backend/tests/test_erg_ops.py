"""Oscillatory potentials (OPs) as an ERG metric — `_erg.oscillatory_potentials`.

OPs are the small high-frequency wavelets riding on the b-wave; the ISCEV method extracts them with
a ~75–300 Hz band-pass and measures each wavelet peak-to-preceding-trough (+ ΣOP + an integrated
RMS). These tests are CI-safe (pure numpy/scipy, no pandas): a synthetic b-wave carrying a 120 Hz
ripple yields real OPs, while the same b-wave with NO ripple reads ≈ 0 (the band-pass rejects the
slow wave) — the discriminator that proves the metric measures OPs, not the b-wave.
"""

import math

from skills import _erg


def _bwave(tm, amp=200.0):
    return amp * math.exp(-((tm - 60.0) / 18.0) ** 2)


def _trace(fs, with_op, op_amp=15.0, op_hz=120.0):
    step = 1000.0 / fs
    t = [i * step for i in range(int(round(200.0 / step)))]  # 0..~200 ms
    if with_op:
        y = [_bwave(tm) + op_amp * math.sin(2 * math.pi * op_hz * tm / 1000.0)
             * math.exp(-((tm - 45.0) / 25.0) ** 2) for tm in t]
    else:
        y = [_bwave(tm) for tm in t]
    return t, y


def test_oscillatory_potentials_recovers_wavelets():
    t, y = _trace(2000.0, with_op=True)
    ops = _erg.oscillatory_potentials(t, y, fs=2000.0)
    assert ops["n_ops"] >= 3                                    # 3–4 OP wavelets found
    assert ops["n_ops"] == len(ops["op_amplitudes_uv"]) == len(ops["op_times_ms"])
    assert all(a > 0 for a in ops["op_amplitudes_uv"])          # peak-to-preceding-trough > 0
    assert ops["op_times_ms"] == sorted(ops["op_times_ms"])     # OP1…OPk ordered in time
    assert ops["op_sum_uv"] == _approx(sum(ops["op_amplitudes_uv"]), rel=1e-3)
    assert ops["op_sum_uv"] > 30.0 and ops["op_rms_uv"] > 1.0   # real OP energy


def test_pure_bwave_has_no_ops():
    """The 75–300 Hz band-pass rejects a slow b-wave with no wavelets → the OP metric reads ≈ 0."""
    t, y = _trace(2000.0, with_op=True)
    ops_on = _erg.oscillatory_potentials(t, y, fs=2000.0)
    t0, y0 = _trace(2000.0, with_op=False)
    ops_off = _erg.oscillatory_potentials(t0, y0, fs=2000.0)
    assert ops_off["op_sum_uv"] < 0.1 * ops_on["op_sum_uv"]     # OPs collapse without the ripple
    assert ops_off["op_rms_uv"] < 0.2 * ops_on["op_rms_uv"]


def test_oscillatory_potentials_window_and_n_ops():
    t, y = _trace(2000.0, with_op=True)
    two = _erg.oscillatory_potentials(t, y, fs=2000.0, n_ops=2)
    assert two["n_ops"] == 2                                    # cap honoured
    windowed = _erg.oscillatory_potentials(t, y, fs=2000.0, window=(30.0, 70.0))
    assert windowed["n_ops"] >= 1
    assert all(30.0 <= tm <= 70.0 for tm in windowed["op_times_ms"])  # peaks inside the window


def test_oscillatory_potentials_low_fs_clamps_and_short_is_empty():
    # Nyquist (200 Hz) below the 300 Hz upper edge → clamped, still returns a dict, no raise.
    t, y = _trace(400.0, with_op=True, op_hz=90.0)
    ops = _erg.oscillatory_potentials(t, y, fs=400.0)
    assert isinstance(ops, dict) and "op_sum_uv" in ops
    # Too few samples to filter → honest empty result (never raises).
    empty = _erg.oscillatory_potentials([0.0, 1.0, 2.0], [0.0, 1.0, 0.0], fs=2000.0)
    assert empty == {"op_amplitudes_uv": [], "op_times_ms": [], "op_sum_uv": 0.0,
                     "op_rms_uv": 0.0, "n_ops": 0}


def _approx(v, rel=1e-3):
    import pytest

    return pytest.approx(v, rel=rel, abs=1e-9)
