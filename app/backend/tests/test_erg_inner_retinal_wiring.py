"""L1-09 — the shipped ERG measurements are REACHABLE: OP · PhNR · flicker Fourier.

``a84636c`` shipped ``_erg.oscillatory_potentials``, ``photopic_negative_response`` and
``flicker_fundamental`` with the figure/table wiring left as a follow-up, so three working
measurements had no surface at all — the shipped-but-not-reachable failure mode. These guard that
a user CAN reach each one (a declared ``param_spec`` key the FE renders), that the numbers land in
the statistics table the figure already carries, that the auto-methods paragraph describes them,
and that all three stay OFF by default so every existing figure, table and golden is unchanged.
"""

from __future__ import annotations

import csv
import math

import pytest

from companions import methods
from skills.registry import load_skill

TRACES = "erg_traces"
FLICKER = "erg_flicker"


def _write_waveforms(path):
    """Two conditions x one intensity, a synthetic a/b trace carrying a 120 Hz OP ripple."""
    def rows(cond, amp):
        out = []
        for i in range(801):
            tm = i * 0.5                      # 0.5 ms steps -> fs = 2000 Hz
            a = math.exp(-((tm - 30.0) / 6.0) ** 2)
            b = math.exp(-((tm - 70.0) / 14.0) ** 2)
            op = 12.0 * math.sin(2 * math.pi * 120.0 * tm / 1000.0) * math.exp(-((tm - 55.0) / 20.0) ** 2)
            out.append((cond, "Group4", tm, round(amp * (b - 0.35 * a) + op, 3), 1.0))
        return out
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "intensity_group", "time_ms", "voltage_uv", "intensity_log_cd_s_m2"])
        w.writerows(rows("Control", 300.0) + rows("Untreated", 80.0))
    return str(path)


def _write_flicker(path):
    def rows(cond, amp, hz):
        return [(cond, hz, i * 0.5, round(-amp * math.sin(2 * math.pi * hz * (i * 0.5) / 1000.0), 3))
                for i in range(801)]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "flicker_hz", "time_ms", "voltage_uv"])
        w.writerows(rows("Control", 30.0, 10.0) + rows("Untreated", 12.0, 10.0))
    return str(path)


def _write_low_rate(path):
    """A REAL unmeasurable case: a 50 Hz acquisition. Nyquist (25 Hz) sits below the OP band's
    75 Hz lower edge, so the band-pass cannot run — a long, perfectly valid trace that simply
    cannot carry an OP measurement."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "intensity_group", "time_ms", "voltage_uv"])
        w.writerows([("Control", "Group4", i * 20.0,
                      round(300.0 * math.exp(-((i * 20.0 - 70.0) / 14.0) ** 2), 3))
                     for i in range(60)])
    return str(path)


def _run_traces(path, **params):
    from skills.proprietary.erg_traces.run_real import run

    return run(path, params)


def _run_flicker(path, **params):
    from skills.proprietary.erg_flicker.run_real import run

    return run(path, params)


# --- reachable: a declared param the FE renders ------------------------------------------------

def test_every_shipped_measurement_has_a_declared_param():
    """The reachability half. A measurement with no ``param_spec`` key cannot be asked for."""
    assert {"oscillatory_potentials", "phnr"} <= set(load_skill(TRACES).param_spec)
    assert "fourier" in load_skill(FLICKER).param_spec


def test_all_three_are_off_by_default(tmp_path):
    """Opt-in: the default figure, its table and its golden are untouched."""
    p = _write_waveforms(tmp_path / "w.csv")
    base = _run_traces(p)
    assert base == _run_traces(p, oscillatory_potentials=False, phnr=False)
    assert base["table"]["columns"] == ["condition", "intensity (log cd·s/m²)", "b-wave (µV)",
                                        "a-wave (µV)", "b-wave t (ms)"]
    assert "oscillatory_potentials" not in (base["layout"].get("meta") or {})

    f = _write_flicker(tmp_path / "f.csv")
    fbase = _run_flicker(f)
    assert fbase == _run_flicker(f, fourier=False)
    assert "fundamental (µV)" not in fbase["table"]["columns"]


# --- the numbers reach the table the figure already carries ------------------------------------

def test_oscillatory_potentials_reach_the_statistics_table(tmp_path):
    p = _write_waveforms(tmp_path / "w.csv")
    spec = _run_traces(p, oscillatory_potentials=True)
    cols = spec["table"]["columns"]
    assert cols[-3:] == ["ΣOP (µV)", "OP RMS (µV)", "OPs (n)"]
    for row in spec["table"]["rows"]:
        assert isinstance(row[-3], (int, float)) and row[-3] > 0   # the 120 Hz ripple is recovered
        assert isinstance(row[-1], int) and row[-1] >= 1
    # the group summary rides layout.meta, so a reader knows what the mean covered
    g = spec["layout"]["meta"]["oscillatory_potentials"]
    assert g["n"] == len(spec["table"]["rows"]) and g["n_not_measurable"] == 0


def test_phnr_reaches_the_statistics_table(tmp_path):
    p = _write_waveforms(tmp_path / "w.csv")
    spec = _run_traces(p, phnr=True)
    assert spec["table"]["columns"][-2:] == ["PhNR BT (µV)", "PhNR trough t (ms)"]
    for row in spec["table"]["rows"]:
        assert row[-1] != "—" and isinstance(row[-2], (int, float))


def test_both_metrics_compose(tmp_path):
    p = _write_waveforms(tmp_path / "w.csv")
    cols = _run_traces(p, oscillatory_potentials=True, phnr=True)["table"]["columns"]
    assert cols[-5:] == ["ΣOP (µV)", "OP RMS (µV)", "OPs (n)", "PhNR BT (µV)", "PhNR trough t (ms)"]


def test_flicker_fundamental_reaches_the_table(tmp_path):
    f = _write_flicker(tmp_path / "f.csv")
    spec = _run_flicker(f, fourier=True)
    cols = spec["table"]["columns"]
    assert cols[-3:] == ["fundamental (µV)", "phase (°)", "measured at (Hz)"]
    assert "Fourier fundamental" in spec["table"]["title"]
    for row in spec["table"]["rows"]:
        assert isinstance(row[-3], (int, float)) and row[-3] > 0
        assert row[-1] == pytest.approx(10.0, abs=1.0)   # measured at the stimulus frequency


# --- an unmeasurable segment renders its REASON, never a 0 (A17 at the surface) -----------------

def test_an_unmeasurable_op_renders_the_reason_not_a_zero(tmp_path):
    """The A17 invariant carried into the TABLE: a ΣOP of 0 is the dysfunction reading, so a
    measurement that never ran must not print one."""
    from skills import _erg

    spec = _run_traces(_write_low_rate(tmp_path / "slow.csv"), oscillatory_potentials=True)
    cell = spec["table"]["rows"][0][-3]
    assert cell in _erg.NOT_MEASURABLE_LABELS.values(), cell
    assert cell != 0 and cell != 0.0
    g = spec["layout"]["meta"]["oscillatory_potentials"]
    assert g["mean"] is None and g["n"] == 0 and g["n_not_measurable"] == 1


# --- the methods paragraph describes what was measured -----------------------------------------

def test_methods_describe_the_metrics_only_when_they_ran(tmp_path):
    p = _write_waveforms(tmp_path / "w.csv")
    spec = load_skill(TRACES)

    off, _ = methods.build_body(spec, {}, figure=_run_traces(p))
    assert "Oscillatory potentials" not in off and "photopic negative response" not in off

    params = {"oscillatory_potentials": True, "phnr": True}
    on, _ = methods.build_body(spec, params, figure=_run_traces(p, **params))
    assert "75-300 Hz" in on and "peak to the preceding trough" in on
    assert "not measurable rather than as zero" in on
    assert "photopic negative response" in on


def test_methods_state_how_many_segments_were_excluded(tmp_path):
    figure = _run_traces(_write_low_rate(tmp_path / "slow.csv"), oscillatory_potentials=True)
    text, _ = methods.build_body(load_skill(TRACES), {"oscillatory_potentials": True}, figure=figure)
    assert "1 of 1 segment(s) were not measurable and were excluded." in text


def test_flicker_methods_describe_the_fundamental(tmp_path):
    spec = load_skill(FLICKER)
    off, _ = methods.build_body(spec, {})
    on, _ = methods.build_body(spec, {"fourier": True})
    assert "Fourier" not in off
    assert "fundamental Fourier component" in on and "DC removed" in on
