"""ERG flicker skill (`erg_flicker`) — the steady-state periodic-response figure.

CI-safe tests cover the dependency-free stub (both views + the native N1/P1 table) and the
contract; the real folded-cycle measure on a staged Diagnosys export is an opt-in test, skipped
when the sample is absent (CI stays green).
"""
from __future__ import annotations

import os
import tempfile

import pytest

from skills.contract import run_skill, run_skill_with_table

_FULL_TXT = "D:/selom-data/diagnosys-erg/full-txt-exp8/453_AAV_C1 - Long RK-PROM1-3’UTR-BPolyA_10+E9.TXT"


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def test_stub_waveform_view_is_a_trace_grid_with_a_native_table():
    figure, table = run_skill_with_table("erg_flicker", "unused", {})
    # 3 conditions × 2 frequencies = 6 floating panels, themed as a trace grid (axes hidden).
    assert len(figure["data"]) == 6
    assert figure["layout"]["meta"]["selom"]["figureKind"] == "trace_grid"
    assert all(figure["layout"][k]["visible"] is False
               for k in figure["layout"] if k.startswith(("xaxis", "yaxis")))
    # Native N1/P1 table: one row per condition × frequency, no a-/b-wave columns.
    assert table is not None and table["rows"]
    assert table["columns"][:2] == ["condition", "frequency (Hz)"]
    assert any("N1" in c for c in table["columns"])
    assert not any("a-wave" in c or "b-wave" in c for c in table["columns"])


def test_stub_summary_view_is_an_axes_bearing_line():
    figure = run_skill("erg_flicker", "unused", {"view": "summary"})
    # The summary is amplitude-vs-frequency: NOT a trace grid (it keeps real, visible axes).
    assert figure["layout"].get("meta", {}).get("selom", {}).get("figureKind") != "trace_grid"
    assert figure["layout"]["xaxis"].get("visible") is not False
    assert "frequency" in figure["layout"]["xaxis"]["title"]["text"].lower()
    # One line+markers trace per condition; no Naka-Rushton "(fit)" trace.
    assert figure["data"] and all("fit" not in str(tr.get("name", "")).lower() for tr in figure["data"])


@pytest.mark.skipif(not os.path.exists(_FULL_TXT), reason="staged full-TXT sample absent")
def test_real_flicker_folded_cycle(monkeypatch):
    """On the real LA 10/30 Hz flicker steps: the folded-cycle N1→P1 is positive and attenuates
    from 10 Hz to 30 Hz (cone temporal roll-off), matching the device markers' ~2× drop."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "real")
    import importlib

    import skills._engine as _eng
    importlib.reload(_eng)
    from skills._celeris import read_celeris

    df = read_celeris(_FULL_TXT)
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    tmp.close()
    df.to_csv(tmp.name, index=False)

    from skills.proprietary.erg_flicker.run_real import run as run_real

    fig = run_real(tmp.name, {"view": "waveform"})
    table = fig.pop("table")
    assert fig["layout"]["meta"]["selom"]["figureKind"] == "trace_grid"
    amp_i = next(i for i, c in enumerate(table["columns"]) if "N1" in c)
    hz_i = table["columns"].index("frequency (Hz)")
    by_hz = {float(r[hz_i]): float(r[amp_i]) for r in table["rows"]}
    assert set(by_hz) == {10.0, 30.0}
    assert by_hz[10.0] > 0 and by_hz[30.0] > 0
    assert by_hz[10.0] > by_hz[30.0]            # 30 Hz attenuates vs 10 Hz
    assert 12.0 < by_hz[10.0] < 25.0            # device ~17-20 µV peak-to-trough at 10 Hz

    summary = run_real(tmp.name, {"view": "summary"})
    assert summary["layout"]["xaxis"]["title"]["text"].startswith("flicker frequency")
