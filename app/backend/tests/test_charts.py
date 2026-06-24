"""Generic figure-styling vocabulary (skills/_charts.py) — proves the mean ± spread / points /
patterns / significance / reference-line bar builder is NOT ERG-specific: it works for any
categorical comparison (dose groups, cell types, …). The ERG bar is one consumer; these tests use
plain non-ERG categories. See docs/erg-module/mean-spread-styling-spec.md.
"""
from skills import _charts


def test_spread_stats_metrics():
    vals = [2.0, 4.0, 6.0, 8.0]  # mean 5, sd = √(20/3) ≈ 2.582, sem = sd/2 ≈ 1.291
    sem = _charts.spread_stats(vals, "sem")
    sd = _charts.spread_stats(vals, "sd")
    assert sem["mean"] == 5.0 and round(sem["err"], 3) == 1.291
    assert round(sd["err"], 3) == 2.582
    assert sd["err"] > sem["err"]
    mm = _charts.spread_stats(vals, "minmax")
    assert mm["lo"] == 3.0 and mm["hi"] == 3.0           # mean−min, max−mean
    assert _charts.spread_stats([5.0], "sem")["err"] == 0.0  # n<2 guard, no NaN


def test_band_traces_for_a_standard_line_plot():
    """The flat-line band builder (non-grid line skills): 2 tonexty fill traces, the upper bound
    filled down to the lower; boundary off by default; rgba fill from the hex colour."""
    tr = _charts.band_traces([0, 1, 2], [-1, -1, -1], [1, 1, 1], color="#0072B2",
                             alpha=0.3, legendgroup="A")
    assert len(tr) == 2
    lo, hi = tr
    assert hi["fill"] == "tonexty" and "fill" not in lo
    assert hi["fillcolor"] == "rgba(0,114,178,0.3)"
    assert lo["line"]["width"] == 0 and hi["line"]["width"] == 0  # no boundary by default
    assert lo["legendgroup"] == hi["legendgroup"] == "A"
    # boundary=dashed draws the edges; xaxis/yaxis target a subplot
    dashed = _charts.band_traces([0, 1], [0, 0], [2, 2], boundary="dashed", xaxis="x2", yaxis="y2")
    assert dashed[0]["line"]["dash"] == "dash" and dashed[0]["xaxis"] == "x2"


def test_aggregate_replicates_mean_and_band():
    """The shared replicate-averaging math (used by the line builder AND the ERG grid)."""
    reps = [([0, 1, 2], [10, 20, 30]), ([0, 1, 2], [12, 18, 34]), ([0, 1, 2], [8, 22, 26])]
    x, mean, lower, upper, errs, n = _charts.aggregate_replicates(reps, "sem")
    assert n == 3 and x == [0.0, 1.0, 2.0]
    assert mean == [10.0, 20.0, 30.0]  # column means
    assert all(lo < m < up for lo, m, up in zip(lower, mean, upper))  # band straddles the mean
    # missing point in one replicate still contributes from the others (graceful)
    x2, mean2, *_ = _charts.aggregate_replicates([([0, 1], [4, 6]), ([0], [8])], "sem")
    assert mean2[0] == 6.0 and mean2[1] == 6.0  # t=0 averages 4&8; t=1 only the first rep


def test_line_figure_is_generic_mean_spread_line():
    """A non-ERG line graph (two dose-response series) → mean lines + ± bands + a numbers table."""
    series = [
        {"label": "Drug A", "x": [1, 2, 3],
         "replicates": [([1, 2, 3], [10, 20, 28]), ([1, 2, 3], [12, 22, 30])]},
        {"label": "Drug B", "x": [1, 2, 3],
         "replicates": [([1, 2, 3], [5, 9, 14]), ([1, 2, 3], [7, 11, 16])]},
    ]
    spec, rows = _charts.line_figure(series, x_title="dose", y_title="response", spread="band",
                                     error="sem", log_x=True)
    fills = [t for t in spec["data"] if t.get("fill") == "tonexty"]
    lines = [t for t in spec["data"] if t.get("mode") == "lines" and t.get("hoverinfo") == "x+y"]
    assert len(fills) == 2 and len(lines) == 2  # one band + one mean line per series
    assert spec["layout"]["xaxis"]["type"] == "log"
    assert spec["layout"]["showlegend"] is True
    assert len(rows) == 6  # 2 series × 3 x-points: [label, x, mean, err]
    assert rows[0][0] == "Drug A" and rows[0][2] == 11.0  # mean of 10 & 12


def test_spread_line_traces_modes():
    reps = [([0, 1], [10, 20]), ([0, 1], [14, 24]), ([0, 1], [12, 22])]
    eb = _charts.spread_line_traces([0, 1], replicates=reps, spread="error_bars", error="sd")
    assert any(t.get("error_y") for t in eb)
    indiv = _charts.spread_line_traces([0, 1], replicates=reps, spread="individual")
    assert len([t for t in indiv if t.get("opacity") == 0.18]) == 3
    rep = _charts.spread_line_traces([0, 1], replicates=reps, central="representative")
    assert len(rep) == 1 and rep[0]["y"] == [10.0, 20.0]  # the first replicate, no spread


def test_band_color_defaults_to_trace_else_override():
    reps = [([0, 1], [10, 20]), ([0, 1], [14, 24])]
    # default: the band matches the line colour
    tr = _charts.spread_line_traces([0, 1], replicates=reps, spread="band", color="#0072B2")
    fill = next(t["fillcolor"] for t in tr if t.get("fill") == "tonexty")
    assert fill == "rgba(0,114,178,0.25)"
    # override: a different band colour
    tr2 = _charts.spread_line_traces([0, 1], replicates=reps, spread="band", color="#0072B2",
                                     band_color="#c0392b")
    fill2 = next(t["fillcolor"] for t in tr2 if t.get("fill") == "tonexty")
    assert fill2.startswith("rgba(192,57,43")


def test_individual_data_points_with_and_without_the_mean_line():
    reps = [([1, 2], [10, 20]), ([1, 2], [14, 24]), ([1, 2], [12, 22])]
    # points + mean line
    withmean = _charts.spread_line_traces([1, 2], replicates=reps, central="mean", spread="none",
                                          points=True)
    pts = [t for t in withmean if t.get("mode") == "markers" and not t.get("error_y")]
    lines = [t for t in withmean if t.get("mode") == "lines" and t.get("hoverinfo") == "x+y"]
    assert len(pts) == 1 and len(pts[0]["x"]) == 6 and len(lines) == 1  # 3 reps × 2 x = 6 points
    # points WITHOUT a mean line (central=none)
    nomean = _charts.spread_line_traces([1, 2], replicates=reps, central="none", points=True)
    assert not [t for t in nomean if t.get("mode") == "lines" and t.get("hoverinfo") == "x+y"]
    assert any(t.get("mode") == "markers" for t in nomean)
    # central=none still renders the individual replicate lines (more visible than behind a mean)
    assert any(t.get("opacity") == 0.5 for t in nomean)


def test_sig_stars_thresholds():
    assert _charts.sig_stars(0.0005) == "***"
    assert _charts.sig_stars(0.005) == "**"
    assert _charts.sig_stars(0.03) == "*"
    assert _charts.sig_stars(0.2) == "ns"
    assert _charts.sig_stars(None) == "ns"


def test_rgba_and_jitter():
    assert _charts.rgba("#0072B2", 0.25) == "rgba(0,114,178,0.25)"
    assert _charts.jitter(2, 1) == [2.0]                 # single point sits on centre
    j = _charts.jitter(0, 4, 0.3)
    assert len(j) == 4 and j == sorted(j) and abs(j[0] + j[-1]) < 1e-9  # symmetric about centre


def test_bar_figure_generic_categories():
    """A non-ERG bar: dose groups with custom colours + patterns, SEM bars, points, legend."""
    cat_values = [("low", [1.0, 2.0, 3.0]), ("high", [7.0, 8.0, 9.0])]
    spec, rows = _charts.bar_figure(
        cat_values, y_title="response", colors={"low": "#888", "high": "#c0392b"},
        labels={"low": "Low dose", "high": "High dose"}, bar_fill="pattern", legend=True)
    bar = spec["data"][0]
    assert bar["type"] == "bar" and bar["y"] == [2.0, 8.0]      # means
    assert bar["marker"]["pattern"]["shape"][0] == ""           # first cycles to solid
    assert spec["layout"]["xaxis"]["ticktext"] == ["Low dose", "High dose"]
    assert spec["layout"]["showlegend"] is True
    assert [r[0] for r in rows] == ["low", "high"] and rows[0][1] == 3   # n


def test_bar_figure_significance_and_refline():
    cat_values = [("a", [1.0, 1.2, 0.9, 1.1]), ("b", [9.0, 9.2, 8.8, 9.1])]
    spec, _ = _charts.bar_figure(cat_values, comparisons=[("a", "b")], hline=5.0, hline_label="ref")
    stars = [a["text"] for a in spec["layout"]["annotations"] if a.get("text") in ("*", "**", "***", "ns")]
    assert stars and stars[0] in ("*", "**", "***")            # a vs b strongly separated
    dashed = [s for s in spec["layout"]["shapes"] if s.get("line", {}).get("dash") == "dash"]
    assert dashed and dashed[0]["y0"] == 5.0
    # Manual override beats the computed value.
    ov, _ = _charts.bar_figure(cat_values, comparisons=[("a", "b", "ns")])
    ov_stars = [a["text"] for a in ov["layout"]["annotations"] if a.get("text") in ("*", "**", "***", "ns")]
    assert ov_stars == ["ns"]


def test_bar_figure_toggle_error_and_points():
    cat_values = [("a", [1.0, 2.0]), ("b", [3.0, 4.0])]
    full, _ = _charts.bar_figure(cat_values)
    assert "error_y" in full["data"][0] and any(t.get("name") == "points" for t in full["data"])
    bare, _ = _charts.bar_figure(cat_values, show_error=False, points=False)
    assert "error_y" not in bare["data"][0]
    assert not any(t.get("name") == "points" for t in bare["data"])
