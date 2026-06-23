"""ERG display-unit rescaling (the `display_unit` Figure-data param).

A unit switch (nV / µV / mV / V) is a pure *presentation* rescale — no re-measurement: the
figure amplitudes, the scale bar (erg_traces), the visible y-axis (intensity-response / bar),
and the attached table all rescale together by the same factor, and the µV default is
byte-identical to the legacy output (asserted by the goldens). Helper tests are CI-safe (no
pandas); the end-to-end tests exercise the real run paths on synthetic tables.
"""

import csv
import math

from skills import _erg


# --- helpers (CI-safe) -------------------------------------------------------

def test_unit_factor_and_label():
    assert _erg.unit_factor("nV") == 1000.0
    assert _erg.unit_factor("uV") == 1.0
    assert _erg.unit_factor("µV") == 1.0
    assert _erg.unit_factor("mV") == 0.001
    assert _erg.unit_factor("V") == 1e-6
    assert _erg.unit_factor("nonsense") == 1.0  # unknown → µV
    assert _erg.unit_label("uv") == "µV"
    assert _erg.unit_label("nV") == "nV"


def test_resolve_display_unit_explicit_and_auto():
    # Explicit unit is honoured verbatim (peak ignored).
    assert _erg.resolve_display_unit("mV", 200.0) == "mV"
    assert _erg.resolve_display_unit("uV", 999999.0) == "µV"
    # Auto picks the unit that reads in [1, 1000): rodent b-wave µV, big flash mV, tiny nV.
    assert _erg.resolve_display_unit("auto", 200.0) == "µV"
    assert _erg.resolve_display_unit("auto", 5000.0) == "mV"
    assert _erg.resolve_display_unit("auto", 0.5) == "nV"
    # Unknown / empty / zero-peak → µV.
    assert _erg.resolve_display_unit("", 0.0) == "µV"
    assert _erg.resolve_display_unit("auto", 0.0) == "µV"


def test_resolve_flash_mode():
    present = ["scotopic_flash", "photopic_flash", "flicker"]
    # auto → scotopic (the canonical dark-adapted ERG) when present.
    assert _erg.resolve_flash_mode(present, "auto", "") == ("scotopic_flash", "scotopic")
    # the friendly adaptation hint maps to the stimulus_type.
    assert _erg.resolve_flash_mode(present, "photopic", "") == ("photopic_flash", "photopic")
    assert _erg.resolve_flash_mode(present, "scotopic", "") == ("scotopic_flash", "scotopic")
    # explicit stimulus_type wins over the hint.
    assert _erg.resolve_flash_mode(present, "scotopic", "photopic_flash") == ("photopic_flash", "photopic")
    # no stimulus column (iWorx path): nothing present → no pick, no filter, no label.
    assert _erg.resolve_flash_mode([], "auto", "") == ("", "")
    # auto falls back to photopic when only photopic is present.
    assert _erg.resolve_flash_mode(["photopic_flash"], "auto", "") == ("photopic_flash", "photopic")


def test_flicker_landmarks_on_a_synthetic_cycle():
    # A clean 10 Hz sinusoid (corneal-negative first): N1→P1 = peak-to-trough = 2×amplitude.
    hz, amp = 10.0, 8.0
    t = [i * 0.5 for i in range(0, 601)]  # 0..300 ms @ 0.5 ms (3 cycles)
    y = [-amp * math.sin(2.0 * math.pi * hz * tm / 1000.0) for tm in t]
    lm = _erg.flicker_landmarks(t, y, hz)
    assert lm is not None
    assert lm["n1p1_uv"] == _approx(2.0 * amp, rel=2e-2)
    assert lm["n1_uv"] < 0 < lm["p1_uv"]
    # P1 (the positive peak) follows N1 within one ~100 ms cycle.
    assert 0.0 < lm["p1_implicit_ms"] <= 100.0
    # Too few points to fold → None (honest, not a fabricated metric).
    assert _erg.flicker_landmarks([0.0, 1.0], [0.0, 1.0], hz) is None


def test_disp_round_legacy_and_rescale():
    # factor 1.0 → legacy 2-dp rounding (keeps the default byte-identical).
    assert _erg.disp_round(210.34, 1.0) == 210.34
    # mV (÷1000): small values survive (not crushed to zero).
    assert _erg.disp_round(200.0, 0.001) == 0.2
    assert _erg.disp_round(5.0, 0.001) == 0.005
    # nV (×1000): large values stay clean.
    assert _erg.disp_round(200.0, 1000.0) == 200000.0
    assert _erg.disp_round(0.0, 0.001) == 0.0


# --- synthetic tables --------------------------------------------------------

def _waveform_rows(condition, amp_uv):
    rows = []
    for t in range(0, 121):  # 0..120 ms @ 1 ms → fs = 1000 Hz
        a = math.exp(-((t - 30.0) / 6.0) ** 2)   # a-wave trough ~30 ms
        b = math.exp(-((t - 70.0) / 14.0) ** 2)  # b-wave peak ~70 ms
        v = amp_uv * (1.0 * b - 0.35 * a)
        rows.append((condition, "Group4", t, round(v, 3), 1.0))
    return rows


def _write_waveforms(path):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "intensity_group", "time_ms", "voltage_uv", "intensity_log_cd_s_m2"])
        w.writerows(_waveform_rows("Control", 300.0) + _waveform_rows("Untreated", 80.0))


def _write_metrics(path):
    """erg_metrics_long: a clean saturating b-wave series, 2 conditions × 5 intensities × 2 eyes."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "intensity_group", "intensity_log_cd_s_m2", "b_wave_uv"])
        for cond, vmax in (("Control", 300.0), ("Untreated", 90.0)):
            for gi, x in enumerate([-1.0, 0.0, 1.0, 2.0, 3.0], start=1):
                base = _erg.naka_rushton(x, vmax, 0.3, 1.0)
                for eye in (-3.0, 3.0):
                    w.writerow([cond, f"Group{gi}", x, round(base + eye, 3)])


def _col_with(columns, prefix):
    return next(i for i, c in enumerate(columns) if str(c).startswith(prefix))


def _maxabs_y(spec):
    return max(abs(float(v)) for tr in spec["data"] for v in tr.get("y", []))


# --- end-to-end: each skill rescales figure + table together ----------------

def test_erg_traces_rescales_figure_scalebar_and_table(tmp_path):
    from skills.proprietary.erg_traces.run_real import run as run_traces

    p = tmp_path / "wave.csv"
    _write_waveforms(p)
    uv = run_traces(str(p), {"display_unit": "uV"})
    mv = run_traces(str(p), {"display_unit": "mV"})

    # Scale-bar label: 200 µV → 0.2 mV (same drawn bar, relabelled).
    uv_annos = [a.get("text") for a in uv["layout"]["annotations"]]
    mv_annos = [a.get("text") for a in mv["layout"]["annotations"]]
    assert "200 µV" in uv_annos
    assert "0.2 mV" in mv_annos

    # Trace amplitudes rescale ×0.001.
    assert _maxabs_y(mv) == _approx(_maxabs_y(uv) / 1000.0)

    # Table headers + values rescale together.
    assert any(c == "b-wave (µV)" for c in uv["table"]["columns"])
    assert any(c == "b-wave (mV)" for c in mv["table"]["columns"])
    bi_uv = _col_with(uv["table"]["columns"], "b-wave (")
    bi_mv = _col_with(mv["table"]["columns"], "b-wave (")
    for ru, rm in zip(uv["table"]["rows"], mv["table"]["rows"]):
        if float(ru[bi_uv]):
            assert float(rm[bi_mv]) == _approx(float(ru[bi_uv]) / 1000.0)


def test_erg_intensity_response_rescales_axis_and_vmax(tmp_path):
    from skills.proprietary.erg_intensity_response.run_real import run as run_ir

    p = tmp_path / "metrics.csv"
    _write_metrics(p)
    uv = run_ir(str(p), {"display_unit": "uV"})
    nv = run_ir(str(p), {"display_unit": "nV"})

    assert uv["layout"]["yaxis"]["title"]["text"] == "b-wave amplitude (µV)"
    assert nv["layout"]["yaxis"]["title"]["text"] == "b-wave amplitude (nV)"

    # Marker amplitudes rescale ×1000 (nV).
    assert _maxabs_y(nv) == _approx(_maxabs_y(uv) * 1000.0)

    # Vmax column relabels + rescales (the fit succeeds on the clean series).
    assert any(c == "Vmax (µV)" for c in uv["table"]["columns"])
    assert any(c == "Vmax (nV)" for c in nv["table"]["columns"])
    vi = _col_with(uv["table"]["columns"], "Vmax (")
    fit_seen = False
    for ru, rn in zip(uv["table"]["rows"], nv["table"]["rows"]):
        if isinstance(ru[vi], (int, float)):
            fit_seen = True
            assert float(rn[vi]) == _approx(float(ru[vi]) * 1000.0)
    assert fit_seen  # at least one condition fit, so the rescale was actually exercised


def test_erg_bwave_bar_rescales_bar_and_table(tmp_path):
    from skills.proprietary.erg_bwave_bar.run_real import run as run_bar

    p = tmp_path / "metrics.csv"
    _write_metrics(p)
    uv = run_bar(str(p), {"intensity_group": "Group4", "display_unit": "uV"})
    mv = run_bar(str(p), {"intensity_group": "Group4", "display_unit": "mV"})

    assert uv["layout"]["yaxis"]["title"]["text"] == "b-wave amplitude (µV)"
    assert mv["layout"]["yaxis"]["title"]["text"] == "b-wave amplitude (mV)"

    # Bar means rescale ×0.001.
    uv_means = uv["data"][0]["y"]
    mv_means = mv["data"][0]["y"]
    for u, m in zip(uv_means, mv_means):
        if float(u):
            assert float(m) == _approx(float(u) / 1000.0)

    assert any(str(c).startswith("mean b-wave (mV)") for c in mv["table"]["columns"])


def test_erg_bwave_bar_measures_a_and_b_from_waveforms(tmp_path):
    """Fan-out path: handed the trace table (no marker column), the bar measures the a/b peak
    from the same waveforms the grid draws (the owner's 'b-wave peak from the traces at a chosen
    intensity'). `wave` selects which peak; the provenance is captioned honestly."""
    from skills.proprietary.erg_bwave_bar.run_real import run as run_bar

    p = tmp_path / "wave.csv"
    _write_waveforms(p)  # Control 300 µV vs Untreated 80 µV, one Group4 trace each

    b = run_bar(str(p), {"intensity_group": "Group4", "wave": "b"})
    assert b["layout"]["yaxis"]["title"]["text"] == "b-wave amplitude (µV)"
    assert "measured from traces" in b["table"]["title"]  # not device markers — honest
    b_means = b["data"][0]["y"]
    assert len(b_means) == 2 and b_means[0] > b_means[1] > 0  # Control > Untreated

    a = run_bar(str(p), {"intensity_group": "Group4", "wave": "a"})
    assert a["layout"]["yaxis"]["title"]["text"] == "a-wave amplitude (µV)"
    a_means = a["data"][0]["y"]
    assert len(a_means) == 2 and a_means[0] > a_means[1] > 0


def _waveform_rows_g(condition, group, amp_uv, log):
    rows = []
    for t in range(0, 121):  # 0..120 ms @ 1 ms
        a = math.exp(-((t - 30.0) / 6.0) ** 2)
        b = math.exp(-((t - 70.0) / 14.0) ** 2)
        v = amp_uv * (1.0 * b - 0.35 * a)
        rows.append((condition, group, log, t, round(v, 3)))
    return rows


def _write_waveform_series(path):
    """erg_waveforms_long across 3 intensities × 2 conditions (b-wave grows with flash energy)."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "intensity_group", "intensity_log_cd_s_m2", "time_ms", "voltage_uv"])
        for cond, base in (("Control", 300.0), ("Untreated", 90.0)):
            for g, log, frac in (("Group2", -0.8, 0.3), ("Group3", 0.1, 0.6), ("Group4", 1.0, 1.0)):
                w.writerows(_waveform_rows_g(cond, g, base * frac, log))


def test_erg_intensity_response_runs_off_waveforms(tmp_path):
    """Fan-out: the intensity-response runs straight off the dropped waveform table (no metrics CSV) —
    it measures the b-wave per (condition × intensity) from the same traces the grid draws. This is
    the other half of the materialize-gap fix (mirrors erg_bwave_bar)."""
    from skills.proprietary.erg_intensity_response.run_real import run as run_ir

    p = tmp_path / "wave_series.csv"
    _write_waveform_series(p)
    fig = run_ir(str(p), {"display_unit": "uV"})
    assert fig["layout"]["yaxis"]["title"]["text"] == "b-wave amplitude (µV)"
    # The 3-intensity data series per condition: b-wave rises monotonically with flash energy.
    data3 = [tr for tr in fig["data"] if tr.get("y") and len(tr["y"]) == 3]
    assert data3, "expected a 3-intensity data series per condition"
    ys = [float(v) for v in data3[0]["y"]]
    assert ys == sorted(ys), "b-wave should rise with intensity"


def test_erg_bwave_bar_patterns_and_legend(tmp_path):
    """`bar_fill=pattern` gives each condition its own hatch (Fig 1E look); `legend=True` adds a
    per-condition legend entry. The default (filled, no legend) stays the original look."""
    from skills.proprietary.erg_bwave_bar.run_real import run as run_bar

    p = tmp_path / "m.csv"
    _write_metrics(p)
    fig = run_bar(str(p), {"intensity_group": "Group4", "legend": True})  # real path defaults to pattern
    pattern = fig["data"][0]["marker"]["pattern"]["shape"]
    assert pattern == ["", "."]                       # Control solid, Untreated dotted
    assert fig["layout"]["showlegend"] is True
    assert sum(1 for t in fig["data"] if t.get("showlegend")) == 2   # one proxy per condition
    # Explicit filled fill has no pattern key (the byte-identical look the golden stub uses).
    plain = run_bar(str(p), {"intensity_group": "Group4", "bar_fill": "filled"})
    assert "pattern" not in plain["data"][0]["marker"]
    assert plain["layout"]["showlegend"] is False


def test_erg_bwave_bar_error_metric(tmp_path):
    """`error` switches the spread (SEM default → SD/CI95/minmax); the table header + error bars
    follow. Two eyes/group at base±3 → SD = √18 ≈ 4.24, SEM = SD/√2 ≈ 3.0."""
    from skills.proprietary.erg_bwave_bar.run_real import run as run_bar

    p = tmp_path / "m.csv"
    _write_metrics(p)
    sem = run_bar(str(p), {"intensity_group": "Group4", "error": "sem"})
    sd = run_bar(str(p), {"intensity_group": "Group4", "error": "sd"})
    assert any("SEM" in c for c in sem["table"]["columns"])
    assert any("SD" in c for c in sd["table"]["columns"])
    assert sd["data"][0]["error_y"]["array"][0] > sem["data"][0]["error_y"]["array"][0]
    mm = run_bar(str(p), {"intensity_group": "Group4", "error": "minmax"})
    assert mm["data"][0]["error_y"]["symmetric"] is False  # asymmetric range arms
    # Error bars are toggleable (owner ask): off → no error_y key at all.
    off = run_bar(str(p), {"intensity_group": "Group4", "show_error": False})
    assert "error_y" not in off["data"][0]
    # Points are toggleable too: off → no eye-points scatter trace.
    no_pts = run_bar(str(p), {"intensity_group": "Group4", "points": False})
    assert not any(t.get("name") == "eyes" for t in no_pts["data"])


def test_erg_bwave_bar_significance_and_refline(tmp_path):
    """Significance brackets (computed or overridden) render as bracket shapes + star annotations;
    `hline` adds a dashed reference line. Control(~saturating) vs Untreated is strongly significant."""
    from skills.proprietary.erg_bwave_bar.run_real import run as run_bar

    p = tmp_path / "m.csv"
    _write_metrics(p)
    fig = run_bar(str(p), {"intensity_group": "Group4", "comparisons": "Control~Untreated",
                           "hline": "100", "hline_label": "ref"})
    stars = [a["text"] for a in fig["layout"]["annotations"] if a.get("text") in ("*", "**", "***", "ns")]
    assert stars and stars[0] in ("*", "**", "***")          # a real difference → significant
    dashed = [s for s in fig["layout"]["shapes"] if s.get("line", {}).get("dash") == "dash"]
    assert dashed and dashed[0]["y0"] == 100                  # the reference line at y=100
    # Manual override wins over the computed value.
    ov = run_bar(str(p), {"intensity_group": "Group4", "comparisons": "Control~Untreated:ns"})
    ov_stars = [a["text"] for a in ov["layout"]["annotations"] if a.get("text") in ("*", "**", "***", "ns")]
    assert ov_stars == ["ns"]


def _approx(v, rel=1e-3):
    import pytest

    return pytest.approx(v, rel=rel, abs=1e-9)
