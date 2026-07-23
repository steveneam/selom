"""Flicker Fourier fundamental — `_erg.flicker_fundamental`.

The steady-state flicker ERG is classically quantified by the first-harmonic (fundamental) Fourier
component at the flicker frequency. CI-safe (pure numpy): a clean sinusoid of known amplitude at an
exact integer number of cycles recovers that amplitude (2·|X[k]|/N) and its bin frequency.
"""

import math

from skills import _erg


def _sinusoid(hz, amp, fs=2000.0, cycles=3):
    step = 1000.0 / fs
    n = int(round(cycles * (1000.0 / hz) / step))       # exact integer cycles → no spectral leakage
    t = [i * step for i in range(n)]
    y = [-amp * math.sin(2 * math.pi * hz * tm / 1000.0) for tm in t]
    return t, y


def test_flicker_fundamental_recovers_amplitude_and_frequency():
    hz, amp = 10.0, 8.0
    t, y = _sinusoid(hz, amp)
    r = _erg.flicker_fundamental(t, y, hz)
    assert r is not None
    assert r["fundamental_hz"] == _approx(hz, rel=2e-2)
    assert r["magnitude_uv"] == _approx(amp, rel=2e-2)          # = 2·|X[k]|/N
    assert -180.0 <= r["phase_deg"] <= 180.0
    assert r["phase_rad"] == _approx(math.radians(r["phase_deg"]), rel=1e-3)
    assert r["target_hz"] == hz


def test_flicker_fundamental_infers_fs_from_time_axis():
    hz, amp = 10.0, 6.0
    t, y = _sinusoid(hz, amp)
    inferred = _erg.flicker_fundamental(t, y, hz, None)
    explicit = _erg.flicker_fundamental(t, y, hz, 2000.0)
    assert inferred == explicit                                 # fs_from(t) == 2000 Hz here


def test_flicker_fundamental_ignores_baseline_offset():
    """The DC term is removed, so a constant baseline offset does not bias the fundamental."""
    hz, amp = 30.0, 5.0
    t, y = _sinusoid(hz, amp)
    y_shift = [v + 250.0 for v in y]
    base = _erg.flicker_fundamental(t, y, hz)
    shifted = _erg.flicker_fundamental(t, y_shift, hz)
    assert shifted["magnitude_uv"] == _approx(base["magnitude_uv"], rel=1e-3)


def test_flicker_fundamental_attenuates_with_smaller_amplitude():
    t_big, y_big = _sinusoid(10.0, 12.0)
    t_sm, y_sm = _sinusoid(10.0, 4.0)
    assert (_erg.flicker_fundamental(t_big, y_big, 10.0)["magnitude_uv"]
            > _erg.flicker_fundamental(t_sm, y_sm, 10.0)["magnitude_uv"])


def test_flicker_fundamental_guards():
    t, y = _sinusoid(10.0, 8.0)
    assert _erg.flicker_fundamental(t, y, 0.0) is None          # non-positive frequency
    assert _erg.flicker_fundamental(t, y, -5.0) is None
    assert _erg.flicker_fundamental([0.0, 1.0], [0.0, 1.0], 10.0) is None  # too few samples


def _approx(v, rel=1e-3):
    import pytest

    return pytest.approx(v, rel=rel, abs=1e-9)
