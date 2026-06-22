"""Unit tests for the generic small-multiples trace-grid primitive (skills/_tracegrid.py).

Structural guarantees the ERG skill (and any future trace-grid skill) relies on: one line
trace per panel on its own hidden axis pair, exactly one shared scale bar, shared ranges,
and the right label counts. See docs/erg-module/spec.md (R1–R7).
"""
import pytest

from skills._tracegrid import grid_spec


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
