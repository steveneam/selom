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


def _write_multi_eye_waveforms(path, n_per_cond=3):
    """erg_waveforms_long with n replicate recordings per condition (sample_id/eye columns) so the
    central=mean / spread path has a real n. 2 conditions × Group4 × n animals, amplitude jittered
    deterministically per animal so the spread is non-zero."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "intensity_group", "time_ms", "voltage_uv",
                    "intensity_log_cd_s_m2", "sample_id", "eye"])
        for cond, amp in (("Control", 300.0), ("Untreated", 80.0)):
            for k in range(n_per_cond):
                scale = 1.0 + 0.1 * (k - 1)  # 0.9, 1.0, 1.1, … → non-zero spread
                for c, grp, t, v, _ in _waveform_rows(cond, amp * scale):
                    w.writerow([c, grp, t, v, 1.0, f"{cond}_a{k}", "RE"])


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


def _line_traces(spec):
    """The panel mean lines (mode=='lines', hoverinfo 'x+y') — not band/replicate helper traces."""
    return [t for t in spec["data"] if t.get("mode") == "lines" and t.get("hoverinfo") == "x+y"]


def test_erg_traces_representative_picks_one_replicate_per_cell(tmp_path):
    """Default (representative) on a 3-eye-per-condition table draws exactly ONE line per
    condition×intensity cell — not the old 3-eyes-concatenated jagged trace."""
    from skills.proprietary.erg_traces.run_real import run as run_traces

    p = tmp_path / "multi.csv"
    _write_multi_eye_waveforms(p, n_per_cond=3)
    spec = run_traces(str(p), {})  # central defaults to representative
    lines = _line_traces(spec)
    assert len(lines) == 2  # 2 conditions × 1 intensity = 2 cells, one exemplar each
    # the exemplar carries the full time grid (121 samples), not 3× concatenated
    assert all(len(t["x"]) == 121 for t in lines)
    assert "Representative" in spec["layout"]["title"]["text"]


def test_erg_traces_central_mean_band(tmp_path):
    """central=mean + spread=band: one mean line per cell + a tonexty ± band; title states n + SEM."""
    from skills.proprietary.erg_traces.run_real import run as run_traces

    p = tmp_path / "multi.csv"
    _write_multi_eye_waveforms(p, n_per_cond=3)
    spec = run_traces(str(p), {"central": "mean", "spread": "band", "error": "sem"})
    fills = [t for t in spec["data"] if t.get("fill") == "tonexty"]
    assert len(fills) == 2  # one band per cell
    assert len(_line_traces(spec)) == 2
    title = spec["layout"]["title"]["text"]
    assert "Mean" in title and "SEM" in title and "n=3" in title


def test_erg_traces_spread_individual_and_error_bars(tmp_path):
    from skills.proprietary.erg_traces.run_real import run as run_traces

    p = tmp_path / "multi.csv"
    _write_multi_eye_waveforms(p, n_per_cond=3)

    indiv = run_traces(str(p), {"central": "mean", "spread": "individual"})
    faint = [t for t in indiv["data"] if t.get("opacity") == 0.18]
    assert len(faint) == 2 * 3  # 3 replicate lines per cell, 2 cells
    assert not [t for t in indiv["data"] if t.get("fill") == "tonexty"]  # no band in this mode

    eb = run_traces(str(p), {"central": "mean", "spread": "error_bars", "error": "sd"})
    err = [t for t in eb["data"] if t.get("error_y")]
    assert len(err) == 2


def test_erg_traces_band_matches_trace_colour_even_for_unmapped_conditions(tmp_path):
    """The band fill is the TRACE colour, not grey — even for a condition outside the ERG palette
    (e.g. a C57/Rd10 strain cohort gets a stable fallback colour, line + band share it)."""
    from skills.proprietary.erg_traces.run_real import run as run_traces

    p = tmp_path / "strain.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "intensity_group", "time_ms", "voltage_uv",
                    "intensity_log_cd_s_m2", "sample_id", "eye"])
        for cond, amp in (("C57", 300.0), ("Rd10", 60.0)):
            for k in range(3):
                for c, grp, t, v, _ in _waveform_rows(cond, amp * (1.0 + 0.1 * (k - 1))):
                    w.writerow([c, grp, t, v, 1.0, f"{cond}_a{k}", "RE"])
    spec = run_traces(str(p), {"central": "mean", "spread": "band"})
    line = next(t for t in spec["data"] if t.get("mode") == "lines" and t.get("hoverinfo") == "x+y")
    band = next(t for t in spec["data"] if t.get("fill") == "tonexty")
    line_hex = line["line"]["color"]
    assert line_hex and line_hex != "#888888"  # an explicit colour, not the grey fallback
    r, g, b = int(line_hex[1:3], 16), int(line_hex[3:5], 16), int(line_hex[5:7], 16)
    assert band["fillcolor"] == f"rgba({r},{g},{b},0.25)"  # band == the trace colour, translucent


def test_erg_traces_band_color_override(tmp_path):
    from skills.proprietary.erg_traces.run_real import run as run_traces

    p = tmp_path / "multi.csv"
    _write_multi_eye_waveforms(p, n_per_cond=3)
    spec = run_traces(str(p), {"central": "mean", "spread": "band", "band_color": "#abcdef"})
    band = next(t for t in spec["data"] if t.get("fill") == "tonexty")
    assert band["fillcolor"].startswith("rgba(171,205,239")  # 0xab,0xcd,0xef


def test_erg_traces_central_none_individual_only(tmp_path):
    """central=none draws every replicate at equal weight and NO bold mean line."""
    from skills.proprietary.erg_traces.run_real import run as run_traces

    p = tmp_path / "multi.csv"
    _write_multi_eye_waveforms(p, n_per_cond=3)
    spec = run_traces(str(p), {"central": "none"})
    assert not [t for t in spec["data"] if t.get("fill") == "tonexty"]  # no band
    # 2 cells × 3 replicates = 6 traces total (1 main + 2 extra per cell), all faint, no opaque mean
    faint_main = [t for t in spec["data"] if t.get("opacity") == 0.55 and t.get("hoverinfo") == "x+y"]
    faint_extra = [t for t in spec["data"] if t.get("opacity") == 0.55 and t.get("hoverinfo") == "skip"]
    assert len(faint_main) == 2 and len(faint_extra) == 4
    assert "Individual" in spec["layout"]["title"]["text"]


def test_erg_traces_central_mean_single_eye_degrades(tmp_path):
    """n<2 → no band/error artifact; the mean line is just the single recording (graceful)."""
    from skills.proprietary.erg_traces.run_real import run as run_traces

    p = tmp_path / "single.csv"
    _write_waveforms(p)  # no sample_id/eye → one recording per cell
    spec = run_traces(str(p), {"central": "mean", "spread": "band"})
    assert not [t for t in spec["data"] if t.get("fill") == "tonexty"]  # no zero-width band
    assert len(_line_traces(spec)) == 2


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


# --- photopic / cone landmark windows (goal-① T15) ---------------------------

def _cone_waveform_rows(condition, amp_uv, group="Group3"):
    """A CONE (photopic) waveform: an early sharp a-wave trough ~12 ms + an early cone b-wave peak
    ~35 ms — fast enough that the SCOTOPIC b-window (40–120 ms) mis-times it (caps it at the 40 ms
    edge) and the cone window (12–90 ms) catches the true earlier/larger peak. Returns
    (condition, group, time_ms, voltage_uv) tuples @ 1 ms (fs = 1000 Hz)."""
    rows = []
    for t in range(0, 121):
        a = math.exp(-((t - 12.0) / 4.0) ** 2)   # early sharp cone a-wave trough
        b = math.exp(-((t - 35.0) / 10.0) ** 2)  # early narrow cone b-wave peak
        v = amp_uv * (1.0 * b - 0.25 * a)
        rows.append((condition, group, t, round(v, 3)))
    return rows


def test_landmarks_photopic_windows_catch_the_early_cone_peak():
    """Cone b-wave at ~35 ms: the photopic windows time it correctly and recover a larger amplitude;
    the scotopic windows (b starts at 40 ms) miss it. Default/unknown mode → scotopic (legacy path)."""
    t = [float(x) for x in range(0, 121)]
    y = [200.0 * (math.exp(-((tm - 35.0) / 10.0) ** 2) - 0.25 * math.exp(-((tm - 12.0) / 4.0) ** 2))
         for tm in t]
    photopic = _erg.landmarks(t, y, fs=1000.0, mode="photopic")
    scotopic = _erg.landmarks(t, y, fs=1000.0, mode="scotopic")
    assert 25.0 <= photopic["b_t_ms"] <= 45.0       # cone b-wave timed near its true 35 ms peak
    assert scotopic["b_t_ms"] >= 40.0               # scotopic window can't see before 40 ms
    assert photopic["b_wave_uv"] > scotopic["b_wave_uv"] > 0
    # Default + unknown mode fall back to scotopic → byte-identical to the legacy single-arg call.
    assert _erg.landmarks(t, y, fs=1000.0) == scotopic
    assert _erg.landmarks(t, y, fs=1000.0, mode="nonsense") == scotopic


def test_adaptation_mode():
    assert _erg.adaptation_mode("auto", "") == "scotopic"          # default / dark-adapted
    assert _erg.adaptation_mode("photopic", "") == "photopic"
    assert _erg.adaptation_mode("scotopic", "") == "scotopic"
    assert _erg.adaptation_mode("auto", "photopic_flash") == "photopic"  # explicit stim wins
    assert _erg.adaptation_mode("nonsense", "") == "scotopic"      # unknown → scotopic


def test_metrics_from_waveforms_mode_per_segment_stimulus_type():
    """The cone windows are picked per segment from `stimulus_type`, so a photopic_flash table is
    measured with cone timing even when the default mode is scotopic (no adaptation param)."""
    import pandas as pd

    cols = ["condition", "intensity_group", "time_ms", "voltage_uv"]
    df_photo = pd.DataFrame(_cone_waveform_rows("Control", 200.0), columns=cols)
    df_photo["stimulus_type"] = "photopic_flash"     # per-row signal forces cone windows
    df_scoto = pd.DataFrame(_cone_waveform_rows("Control", 200.0), columns=cols)  # no signal → default

    photo = _erg.metrics_from_waveforms(df_photo, default_mode="scotopic")
    scoto = _erg.metrics_from_waveforms(df_scoto, default_mode="scotopic")
    assert float(photo["b_wave_uv"].iloc[0]) > float(scoto["b_wave_uv"].iloc[0]) > 0
    # The explicit default also reaches the cone windows when there is no stimulus_type column.
    photo_default = _erg.metrics_from_waveforms(df_scoto, default_mode="photopic")
    assert float(photo_default["b_wave_uv"].iloc[0]) == _approx(float(photo["b_wave_uv"].iloc[0]))


def test_erg_bwave_bar_photopic_adaptation_uses_cone_windows(tmp_path):
    """End-to-end: a cone waveform table measured via adaptation='photopic' recovers a larger
    b-wave than the scotopic default, because the cone b-window sees the fast ~35 ms peak."""
    from skills.proprietary.erg_bwave_bar.run_real import run as run_bar

    p = tmp_path / "cone.csv"
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["condition", "intensity_group", "time_ms", "voltage_uv"])
        w.writerows(_cone_waveform_rows("Control", 200.0, "Group3"))
    photo = run_bar(str(p), {"intensity_group": "Group3", "wave": "b", "adaptation": "photopic"})
    scoto = run_bar(str(p), {"intensity_group": "Group3", "wave": "b", "adaptation": "scotopic"})
    assert photo["data"][0]["y"][0] > scoto["data"][0]["y"][0] > 0


# --- manual landmark marks (erg-manual-marks v1) -----------------------------

def test_landmarks_manual_override_measures_at_the_set_time():
    """A supplied a_ms/b_ms re-measures the amplitude AT that time (ISCEV) and tags it manual; a
    partial override leaves the other auto; no manual → byte-identical to the auto call."""
    t = [float(x) for x in range(0, 121)]
    amp = 300.0
    y = [amp * (math.exp(-((tm - 70.0) / 14.0) ** 2) - 0.35 * math.exp(-((tm - 30.0) / 6.0) ** 2))
         for tm in t]
    auto = _erg.landmarks(t, y, fs=1000.0)
    assert auto["a_source"] == "auto" and auto["b_source"] == "auto"
    # Move the b-mark onto the rising edge (50 ms, below the true 70 ms peak) → a smaller b, tagged
    # manual at ~50 ms; the a-wave stays auto.
    moved = _erg.landmarks(t, y, fs=1000.0, manual={"b_ms": 50.0})
    assert moved["b_source"] == "manual" and moved["a_source"] == "auto"
    assert abs(moved["b_t_ms"] - 50.0) <= 1.0
    assert 0.0 < moved["b_wave_uv"] < auto["b_wave_uv"]
    # Partial override of only the a-wave.
    a_moved = _erg.landmarks(t, y, fs=1000.0, manual={"a_ms": 20.0})
    assert a_moved["a_source"] == "manual" and a_moved["b_source"] == "auto"
    assert abs(a_moved["a_t_ms"] - 20.0) <= 1.0
    # No manual (None or {}) → byte-identical to the auto path.
    assert _erg.landmarks(t, y, fs=1000.0, manual=None) == auto
    assert _erg.landmarks(t, y, fs=1000.0, manual={}) == auto


def test_parse_manual_marks_tolerant():
    assert _erg.parse_manual_marks("") == {}
    assert _erg.parse_manual_marks(None) == {}
    assert _erg.parse_manual_marks("not json at all") == {}
    parsed = _erg.parse_manual_marks(
        '{"Control||Group4|": {"a_ms": 12.4, "b_ms": 58, "junk": 9}, '
        '"bad": 5, "empty": {"x": 1}}')
    assert parsed == {"Control||Group4|": {"a_ms": 12.4, "b_ms": 58.0}}  # junk/bad/empty dropped
    # An already-parsed dict passes through (canonicalized).
    assert _erg.parse_manual_marks({"A|B|C|D": {"n1_ms": 10.0}}) == {"A|B|C|D": {"n1_ms": 10.0}}


def test_marks_for_exact_and_wildcard_match():
    marks = {"Control||Group4|": {"a_ms": 12.0}}  # empty stimulus + eye
    assert _erg.marks_for(marks, "Control", "", "Group4", "") == {"a_ms": 12.0}      # exact
    # A grid mark (empty stim/eye) applies to a per-eye bar segment via the wildcard.
    assert _erg.marks_for(marks, "Control", "scotopic_flash", "Group4", "RE") == {"a_ms": 12.0}
    assert _erg.marks_for(marks, "Untreated", "", "Group4", "") is None             # other condition
    assert _erg.marks_for(None, "Control", "", "Group4", "") is None                # no marks


def test_flicker_landmarks_manual_override():
    """Override N1/P1 by phase on the folded cycle; tagged manual; no manual → byte-identical."""
    hz, amp = 10.0, 8.0
    t = [i * 0.5 for i in range(0, 601)]
    y = [-amp * math.sin(2.0 * math.pi * hz * tm / 1000.0) for tm in t]  # trough@25 ms, peak@75 ms
    auto = _erg.flicker_landmarks(t, y, hz)
    assert auto["n1_source"] == "auto" and auto["p1_source"] == "auto"
    moved = _erg.flicker_landmarks(t, y, hz, manual={"n1_ms": 25.0, "p1_ms": 75.0})
    assert moved["n1_source"] == "manual" and moved["p1_source"] == "manual"
    assert moved["n1p1_uv"] == _approx(2.0 * amp, rel=5e-2)
    assert _erg.flicker_landmarks(t, y, hz, manual=None) == auto


def test_metrics_from_waveforms_applies_marks(tmp_path):
    import pandas as pd

    cols = ["condition", "intensity_group", "time_ms", "voltage_uv", "intensity_log_cd_s_m2"]
    df = pd.DataFrame(_waveform_rows("Control", 300.0), columns=cols)
    base = _erg.metrics_from_waveforms(df, default_mode="scotopic")
    assert base["a_source"].iloc[0] == "auto" and base["b_source"].iloc[0] == "auto"
    marks = {"Control||Group4|": {"b_ms": 50.0}}
    moved = _erg.metrics_from_waveforms(df, default_mode="scotopic", marks=marks)
    assert moved["b_source"].iloc[0] == "manual"
    assert float(moved["b_wave_uv"].iloc[0]) != float(base["b_wave_uv"].iloc[0])
    # No marks → the source stays auto and the value matches the default measurement.
    again = _erg.metrics_from_waveforms(df, default_mode="scotopic", marks=None)
    assert float(again["b_wave_uv"].iloc[0]) == float(base["b_wave_uv"].iloc[0])


def test_erg_bwave_bar_manual_marks_move_value_and_caption(tmp_path):
    """End-to-end: a manual_marks JSON moves the measured bar value off the auto seed and the table
    caption flags the operator adjustment; no manual_marks → byte-identical to today."""
    from skills.proprietary.erg_bwave_bar.run_real import run as run_bar

    p = tmp_path / "wave.csv"
    _write_waveforms(p)  # Control + Untreated, one Group4 trace each
    base = run_bar(str(p), {"intensity_group": "Group4", "wave": "b"})
    moved = run_bar(str(p), {"intensity_group": "Group4", "wave": "b",
                             "manual_marks": '{"Control||Group4|": {"b_ms": 50.0}}'})
    assert moved["data"][0]["y"][0] != base["data"][0]["y"][0]       # Control's bar followed the mark
    assert "operator-adjusted" in moved["table"]["title"]            # provenance caption (R6)
    assert "operator-adjusted" not in base["table"]["title"]
    # No manual_marks → byte-identical to the bare run (default-off invariant, R8).
    assert run_bar(str(p), {"intensity_group": "Group4", "wave": "b"}) == base


def test_erg_traces_emits_mark_meta_and_optional_dots(tmp_path):
    """erg_traces emits meta.selom.marks (seeded a/b times + source) always — for the Marks panel —
    and draws the visual dots only when `marks` is on (default off → figure visually unchanged)."""
    from skills.proprietary.erg_traces.run_real import run as run_traces

    p = tmp_path / "wave.csv"
    _write_waveforms(p)
    off = run_traces(str(p), {})
    marks_meta = off["layout"]["meta"]["selom"]["marks"]
    assert len(marks_meta) == 4                                      # 2 cells × (a, b)
    assert {m["role"] for m in marks_meta} == {"a", "b"}
    assert all(m["source"] == "auto" for m in marks_meta)
    assert all("uv" in m for m in marks_meta)                        # measured amplitude for the panel
    assert not any("trace" in m for m in marks_meta)                 # no dots → no drag binding
    assert not any(t.get("mode") == "markers+text" for t in off["data"])  # no visual dots
    # marks on → the a/b dot overlay appears and the meta carries trace/point for the editor drag.
    on = run_traces(str(p), {"marks": True})
    on_meta = on["layout"]["meta"]["selom"]["marks"]
    assert all("trace" in m and "point" in m for m in on_meta)
    assert any(t.get("mode") == "markers+text" for t in on["data"])


def _approx(v, rel=1e-3):
    import pytest

    return pytest.approx(v, rel=rel, abs=1e-9)
