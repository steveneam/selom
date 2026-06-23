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
