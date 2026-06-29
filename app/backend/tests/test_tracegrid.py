"""Unit tests for the generic small-multiples trace-grid primitive (skills/_tracegrid.py).

Structural guarantees the ERG skill (and any future trace-grid skill) relies on: one line
trace per panel on its own hidden axis pair, exactly one shared scale bar, shared ranges,
and the right label counts. See docs/records/erg-module/spec.md (R1–R7).
"""
import pytest

from skills._tracegrid import _rgba, grid_spec


def _panels(nrows, ncols):
    return [
        {"row": r, "col": c, "x": [0, 1, 2, 3], "y": [0.0, float(r + c), -(r + 1.0), 0.5],
         "color": "#000", "name": f"r{r}c{c}"}
        for r in range(nrows) for c in range(ncols)
    ]


def _axis_keys(layout):
    return [k for k in layout if k.startswith(("xaxis", "yaxis"))]


def test_one_trace_per_panel_on_its_own_axes():
    spec = grid_spec(_panels(7, 6), nrows=7, ncols=6,
                     row_labels=[f"i{r}" for r in range(7)],
                     col_labels=[f"c{c}" for c in range(6)])
    assert len(spec["data"]) == 42
    refs = {(t["xaxis"], t["yaxis"]) for t in spec["data"]}
    assert len(refs) == 42  # each panel addressed by a unique xaxisN/yaxisN pair


def test_all_per_panel_axes_hidden():
    spec = grid_spec(_panels(2, 3), nrows=2, ncols=3)
    axes = _axis_keys(spec["layout"])
    assert axes, "no axes emitted"
    assert all(spec["layout"][k]["visible"] is False for k in axes)


def test_single_scalebar_and_label_counts():
    spec = grid_spec(_panels(2, 3), nrows=2, ncols=3,
                     row_labels=["a", "b"], col_labels=["x", "y", "z"])
    paper_shapes = [s for s in spec["layout"]["shapes"] if s.get("xref") == "paper"]
    assert len(paper_shapes) == 2  # L-shaped scale bar = two segments, drawn once
    # 2 row labels + 3 col labels + 2 scale-bar unit labels
    assert len(spec["layout"]["annotations"]) == 2 + 3 + 2


def test_ranges_shared_across_panels():
    spec = grid_spec(_panels(2, 2), nrows=2, ncols=2)
    yranges = [spec["layout"][k]["range"] for k in spec["layout"] if k.startswith("yaxis")]
    xranges = [spec["layout"][k]["range"] for k in spec["layout"] if k.startswith("xaxis")]
    assert yranges and all(r == yranges[0] for r in yranges)
    assert xranges and all(r == xranges[0] for r in xranges)


def test_baseline_adds_panel_zero_lines():
    spec = grid_spec(_panels(2, 2), nrows=2, ncols=2, baseline=True)
    zero_lines = [s for s in spec["layout"]["shapes"] if s.get("xref", "").startswith("x") and s.get("xref") != "paper"]
    assert len(zero_lines) == 4  # one per panel (y range spans 0)


def test_custom_scalebar_units_render():
    spec = grid_spec(_panels(1, 1), nrows=1, ncols=1,
                     scalebar={"x_len": 50, "x_unit": "ms", "y_len": 100, "y_unit": "µV"})
    texts = {a["text"] for a in spec["layout"]["annotations"]}
    assert "100 µV" in texts and "50 ms" in texts


def test_panel_out_of_bounds_raises():
    with pytest.raises(ValueError):
        grid_spec([{"row": 5, "col": 0, "x": [0, 1], "y": [0, 1]}], nrows=2, ncols=2)


def test_empty_panels_raises():
    with pytest.raises(ValueError):
        grid_spec([], nrows=2, ncols=2)


# ---- per-panel overlays (shared hook: M3 markers + the styling band/error/replicates) --

def test_no_overlay_keys_is_byte_identical():
    """A panel with no band/error/markers/extra_lines keys emits exactly one trace per panel —
    the overlay hook must not perturb the existing output."""
    plain = grid_spec(_panels(2, 3), nrows=2, ncols=3)
    assert len(plain["data"]) == 6
    assert all(t["mode"] == "lines" for t in plain["data"])


def test_marker_overlay_adds_a_dot_trace_on_the_panel_axis():
    panels = _panels(1, 1)
    panels[0]["markers"] = [{"x": 1, "y": 0.5, "label": "N1"}, {"x": 2, "y": -0.5, "label": "P1"}]
    spec = grid_spec(panels, nrows=1, ncols=1)
    line = next(t for t in spec["data"] if t["mode"] == "lines")
    dots = next(t for t in spec["data"] if str(t["mode"]).startswith("markers"))
    assert dots["text"] == ["N1", "P1"]
    assert dots["xaxis"] == line["xaxis"] and dots["yaxis"] == line["yaxis"]  # same panel axis
    assert dots["x"] == [1, 2] and dots["y"] == [0.5, -0.5]


def test_band_overlay_is_two_fill_traces_behind_the_line():
    panels = _panels(1, 1)
    panels[0]["band"] = {"x": [0, 1, 2, 3], "lower": [-1, -1, -1, -1], "upper": [1, 1, 1, 1],
                         "color": "#0072B2", "alpha": 0.3, "group": "cond"}
    spec = grid_spec(panels, nrows=1, ncols=1)
    fills = [t for t in spec["data"] if t.get("fill") == "tonexty"]
    assert len(fills) == 1
    assert fills[0]["fillcolor"] == "rgba(0,114,178,0.3)"
    # the two band traces (hoverinfo "skip") come BEFORE the mean line (hoverinfo "x+y") in draw
    # order, so the line sits on top of the fill.
    assert len(spec["data"]) == 3
    assert [t["hoverinfo"] for t in spec["data"]] == ["skip", "skip", "x+y"]


def test_band_overlay_extends_shared_range():
    panels = _panels(1, 1)  # base y in [-1, 1]
    panels[0]["band"] = {"x": [0, 1, 2, 3], "lower": [-5, -5, -5, -5], "upper": [5, 5, 5, 5]}
    spec = grid_spec(panels, nrows=1, ncols=1)
    yr = next(spec["layout"][k]["range"] for k in spec["layout"] if k.startswith("yaxis"))
    assert yr[0] <= -5 and yr[1] >= 5  # the band is not clipped by the shared range


def test_error_overlay_draws_every_nth():
    panels = _panels(1, 1)
    panels[0]["error"] = {"x": [0, 1, 2, 3], "y": [0, 0, 0, 0], "err": [1, 1, 1, 1], "every": 2}
    spec = grid_spec(panels, nrows=1, ncols=1)
    err = next(t for t in spec["data"] if t.get("error_y"))
    assert err["error_y"]["array"] == [1.0, None, 1.0, None]  # null (not 0) on skipped points


def test_series_grouping_points_at_the_line_under_overlays():
    """With overlays shifting trace indices, the editor series must still address the mean LINE."""
    panels = _panels(1, 2)
    for p in panels:
        p["group"] = "cond"
        p["band"] = {"x": [0, 1, 2, 3], "lower": [-1] * 4, "upper": [1] * 4}
        p["markers"] = [{"x": 1, "y": 0.0}]
    spec = grid_spec(panels, nrows=1, ncols=2)
    series = spec["layout"]["meta"]["selom"]["series"]
    assert len(series) == 1
    for idx in series[0]["traceIndices"]:
        assert spec["data"][idx]["mode"] == "lines"  # never a band/marker helper trace


def test_rgba_helper():
    assert _rgba("#0072B2", 0.25) == "rgba(0,114,178,0.25)"
    assert _rgba("abc", 0.5) == "rgba(170,187,204,0.5)"  # 3-digit shorthand expands
    assert _rgba(None, 0.1) == "rgba(136,136,136,0.1)"   # fallback grey
