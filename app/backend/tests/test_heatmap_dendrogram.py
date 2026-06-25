"""heatmap ``cluster`` option — draws the row and/or column clustering trees alongside the map.

Real engine on a small bulk CSV: ``cluster='row'`` adds a left-gutter dendrogram-line trace,
moves the row labels to the right, and tucks a horizontal colour key at the bottom; ``'column'``
adds a top-gutter tree and reorders the samples; ``'both'`` does both; ``'none'`` (default) stays
the single-trace heatmap — the conventional clustermap layout (paper Fig 1c / Fig 5). Also guards
that the publication theme preserves ``yaxis.side`` (a recurring axis keep-whitelist gotcha).
Skipped without pandas/scipy.
"""

import os
import tempfile

import pytest

from skills.contract import run_skill

pytest.importorskip("pandas")
pytest.importorskip("scipy")


@pytest.fixture(autouse=True)
def _real(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "real")


def _csv(path: str) -> None:
    import numpy as np
    import pandas as pd

    rng = np.random.RandomState(0)
    df = pd.DataFrame(rng.normal(size=(12, 8)), columns=[f"S{i}" for i in range(8)])
    df.insert(0, "gene", [f"G{i}" for i in range(12)])
    df.to_csv(path, index=False)


def _run(params: dict) -> dict:
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        _csv(path)
        return run_skill("heatmap", path, params)
    finally:
        os.unlink(path)


def _design(path: str) -> None:
    """A sample sheet for the 8 samples S0..S7 — two factors (condition + batch)."""
    import pandas as pd

    pd.DataFrame(
        {
            "sample": [f"S{i}" for i in range(8)],
            "condition": ["wt"] * 4 + ["ko"] * 4,
            "batch": (["b1", "b2"] * 4),
        }
    ).to_csv(path, index=False)


def _run_with_design(params: dict) -> dict:
    fd, path = tempfile.mkstemp(suffix=".csv")
    dfd, dpath = tempfile.mkstemp(suffix="_design.csv")
    os.close(fd)
    os.close(dfd)
    try:
        _csv(path)
        _design(dpath)
        return run_skill("heatmap", path, {**params, "_design_path": dpath})
    finally:
        os.unlink(path)
        os.unlink(dpath)


def test_cluster_none_is_single_trace():
    fig = _run({"n_genes": 12})
    assert [t["type"] for t in fig["data"]] == ["heatmap"]
    assert "xaxis2" not in fig["layout"]
    assert "xaxis3" not in fig["layout"]


def test_cluster_row_adds_tree_and_moves_labels():
    fig = _run({"n_genes": 12, "cluster": "row"})
    assert [t["type"] for t in fig["data"]] == ["heatmap", "scatter"]
    # dendrogram lines live on the left gutter axis
    assert fig["data"][1]["xaxis"] == "x2"
    assert "xaxis2" in fig["layout"] and "yaxis2" in fig["layout"]
    assert "xaxis3" not in fig["layout"]
    # tree on the left -> row labels on the right (theme must preserve yaxis.side)
    assert fig["layout"]["yaxis"]["side"] == "right"
    # small horizontal colour key tucked at the bottom
    assert fig["data"][0]["colorbar"]["orientation"] == "h"


def test_cluster_column_adds_top_tree_only():
    fig = _run({"n_genes": 12, "cluster": "column"})
    assert [t["type"] for t in fig["data"]] == ["heatmap", "scatter"]
    # column tree lives on the top gutter axis (x3/y3), NOT the left gutter
    assert fig["data"][1]["xaxis"] == "x3" and fig["data"][1]["yaxis"] == "y3"
    assert "xaxis3" in fig["layout"] and "yaxis3" in fig["layout"]
    assert "xaxis2" not in fig["layout"]
    # column-only keeps the default vertical right-hand colour bar + left-hand row labels
    assert fig["data"][0]["colorbar"].get("orientation") != "h"
    assert fig["layout"]["yaxis"].get("side") != "right"
    # heatmap cedes the top 16% for the column tree
    assert fig["layout"]["yaxis"]["domain"] == [0.0, 0.84]
    assert fig["layout"]["yaxis3"]["domain"] == [0.86, 1.0]


def test_cluster_both_adds_both_trees():
    fig = _run({"n_genes": 12, "cluster": "both"})
    assert [t["type"] for t in fig["data"]] == ["heatmap", "scatter", "scatter"]
    # left (row, x2) + top (column, x3) gutters both present
    assert {fig["data"][1]["xaxis"], fig["data"][2]["xaxis"]} == {"x2", "x3"}
    assert all(k in fig["layout"] for k in ("xaxis2", "yaxis2", "xaxis3", "yaxis3"))
    # both gutters reserved: left 16% + top 16%
    assert fig["layout"]["xaxis"]["domain"] == [0.16, 1.0]
    assert fig["layout"]["yaxis"]["domain"] == [0.0, 0.84]
    assert fig["layout"]["yaxis"]["side"] == "right"


def test_annotation_tracks_paint_aligned_strips():
    fig = _run_with_design({"n_genes": 12, "cluster": "column", "annotations": "condition, batch"})
    heatmaps = [t for t in fig["data"] if t["type"] == "heatmap"]
    # main map + one strip per requested column
    assert len(heatmaps) == 3
    strips = [t for t in heatmaps if t.get("yaxis") in ("y4", "y5")]
    assert len(strips) == 2
    # first-requested track is adjacent to the heatmap (lower band) — condition on x4/y4
    cond = next(t for t in strips if t["y"] == ["condition"])
    assert cond["xaxis"] == "x4" and cond["yaxis"] == "y4"
    # strips share the heatmap's column axis (matches:x) so they stay aligned under reorder
    assert fig["layout"]["xaxis4"]["matches"] == "x"
    # one z row, discrete scale, no colour bar of its own
    assert len(cond["z"]) == 1 and cond["showscale"] is False
    assert cond["zmin"] == -0.5 and cond["zmax"] == 1.5  # 2 categories (wt/ko)
    # a per-category legend proxy exists for each category, grouped by track
    proxies = [t for t in fig["data"] if t["type"] == "scatter" and t.get("showlegend")]
    names = {(t["legendgroup"], t["name"]) for t in proxies}
    assert ("condition", "wt") in names and ("condition", "ko") in names
    assert ("batch", "b1") in names and ("batch", "b2") in names
    # the heatmap cedes vertical room for the two strips (0.84 − 2·0.04 − 0.01)
    assert fig["layout"]["yaxis"]["domain"] == [0.0, 0.75]


def test_annotation_tracks_need_a_sample_sheet():
    # annotations requested but NO design sheet → no strips, just the plain clustered map (honest)
    fig = _run({"n_genes": 12, "cluster": "column", "annotations": "condition"})
    assert [t["type"] for t in fig["data"]] == ["heatmap", "scatter"]
    assert "xaxis4" not in fig["layout"]


def test_annotation_unknown_column_is_skipped():
    fig = _run_with_design({"n_genes": 12, "cluster": "none", "annotations": "condition, nonsense"})
    strips = [t for t in fig["data"] if t["type"] == "heatmap" and t.get("yaxis") == "y4"]
    assert len(strips) == 1 and strips[0]["y"] == ["condition"]
    # no second strip for the bogus column
    assert "yaxis5" not in fig["layout"]


def test_quant_track_variance_bar_grows_from_zero():
    fig = _run({"n_genes": 12, "quant_track": "variance"})
    bars = [t for t in fig["data"] if t["type"] == "bar"]
    assert len(bars) == 1
    bar = bars[0]
    # the quant bar takes the next free axis (no col tracks → x4) and shares the heatmap row axis
    assert bar["xaxis"] == "x4" and bar["yaxis"] == "y4"
    assert fig["layout"]["yaxis4"]["matches"] == "y"
    # non-negative stat → axis starts at 0, single colour, no row tree but labels move right
    assert fig["layout"]["xaxis4"]["range"][0] == 0
    assert isinstance(bar["marker"]["color"], str)
    assert fig["layout"]["yaxis"]["side"] == "right"  # the quant band owns the left
    # the heatmap cedes the left 12% to the quant band
    assert fig["layout"]["xaxis"]["domain"] == [0.12, 1.0]


def test_quant_track_logfc_is_diverging_from_design():
    fig = _run_with_design({"n_genes": 12, "cluster": "row", "quant_track": "logfc"})
    bar = next(t for t in fig["data"] if t["type"] == "bar")
    # log2FC between the design's two condition groups → 0-centred axis + per-bar sign colours
    ax = fig["layout"][f"xaxis{bar['xaxis'][1:]}"]
    assert ax["range"][0] == -ax["range"][1] and ax["zeroline"] is True
    assert "log2FC" in ax["title"]["text"]
    assert isinstance(bar["marker"]["color"], list)  # per-bar (sign) colours
    # quant band sits right of the row tree (0.16) → heatmap starts at 0.28
    assert fig["layout"]["xaxis"]["domain"] == [0.28, 1.0]


def test_quant_logfc_without_design_falls_back_to_none():
    # logfc asked but no sample sheet → no bar (honest), just the plain map
    fig = _run({"n_genes": 12, "quant_track": "logfc"})
    assert not [t for t in fig["data"] if t["type"] == "bar"]


def test_split_by_blocks_columns_with_gaps_and_headers():
    fig = _run_with_design({"n_genes": 12, "cluster": "both", "split_by": "condition"})
    main = next(t for t in fig["data"] if t["type"] == "heatmap")
    # columns regrouped into the two condition blocks (sorted: ko, then wt) with a blank spacer between
    assert main["x"] == ["S4", "S5", "S6", "S7", " ", "S0", "S1", "S2", "S3"]
    # the spacer column is a None gap in every row (Plotly draws it blank — never NaN in the JSON,
    # which jsonable doesn't sanitise, so a real NaN would break the FE parse)
    assert all(row[4] is None for row in main["z"])
    assert all(v is None or isinstance(v, float) for row in main["z"] for v in row)
    # a bold header centred over each block
    headers = fig["layout"]["annotations"]
    assert [h["text"] for h in headers] == ["ko", "wt"]
    # column clustering is dropped in split mode (no top tree), the row tree still draws
    assert "xaxis3" not in fig["layout"]
    assert "xaxis2" in fig["layout"]


def test_split_by_needs_a_sample_sheet():
    fig = _run({"n_genes": 12, "cluster": "row", "split_by": "condition"})
    main = next(t for t in fig["data"] if t["type"] == "heatmap")
    assert " " not in main["x"]  # no spacer → no split happened
    assert "annotations" not in fig["layout"]


# --- cut_k: coloured dendrogram branches (heatmap-clustermap-spec §9 / refs 035648/035701) ---------

from skills.heatmap.run import _CLUSTER_PALETTE, _TRUNK_COLOR  # noqa: E402


def _row_tree_traces(fig):
    return [t for t in fig["data"] if t["type"] == "scatter" and t.get("xaxis") == "x2"]


def test_cut_k_zero_is_a_single_grey_tree():
    # cut_k=0 (default) → the dendrogram is one grey polyline trace, exactly as before the feature
    fig = _run({"n_genes": 12, "cluster": "row", "cut_k": 0})
    rows = _row_tree_traces(fig)
    assert len(rows) == 1
    assert rows[0]["line"]["color"] == _TRUNK_COLOR


def test_cut_k_colours_row_branches_by_cluster():
    fig = _run({"n_genes": 12, "cluster": "row", "cut_k": 3})
    rows = _row_tree_traces(fig)
    # the tree splits into the grey trunk + one trace per below-cut cluster colour
    assert len(rows) > 1
    colors = [t["line"]["color"] for t in rows]
    assert colors[0] == _TRUNK_COLOR  # trunk drawn first (under the coloured clusters)
    cluster_colors = [c for c in colors if c != _TRUNK_COLOR]
    assert len(cluster_colors) >= 2  # a real cut, multiple clusters
    assert set(cluster_colors) <= set(_CLUSTER_PALETTE)  # only the cluster palette
    assert len(set(cluster_colors)) == len(cluster_colors)  # one trace per colour
    # every leaf base (distance 0) survives the colour split — the FE leaf-tip projection relies on
    # all leaves still being present across the (now multiple) traces of the axis
    zeros = sum(1 for t in rows for v in t["x"] if v == 0)
    assert zeros == 12


def test_cut_k_colours_both_trees():
    fig = _run({"n_genes": 12, "cluster": "both", "cut_k": 3})
    rows = _row_tree_traces(fig)
    cols = [t for t in fig["data"] if t["type"] == "scatter" and t.get("xaxis") == "x3"]
    # both gutters get the grey trunk + coloured clusters
    assert len(rows) > 1 and len(cols) > 1
    for traces in (rows, cols):
        cluster_colors = {t["line"]["color"] for t in traces} - {_TRUNK_COLOR}
        assert cluster_colors and cluster_colors <= set(_CLUSTER_PALETTE)


def test_cut_k_without_a_tree_is_noop():
    # cut_k asked but no tree drawn (cluster='none') → nothing to colour, the plain single-trace map
    fig = _run({"n_genes": 12, "cluster": "none", "cut_k": 3})
    assert [t["type"] for t in fig["data"]] == ["heatmap"]


def test_split_by_cut_blocks_columns_unsupervised():
    # split_by_cut + cut_k → block-split the columns by the dendrogram cut, NO sample sheet needed
    fig = _run({"n_genes": 12, "cluster": "both", "cut_k": 2, "split_by_cut": True})
    main = next(t for t in fig["data"] if t["type"] == "heatmap")
    # two contiguous blocks with a blank spacer column between them
    assert main["x"].count(" ") == 1
    assert all(row[main["x"].index(" ")] is None for row in main["z"])
    # one "Cluster N" header per block (named by the cut, not a sheet column)
    headers = [h["text"] for h in fig["layout"]["annotations"]]
    assert headers == ["Cluster 1", "Cluster 2"]
    # the column tree is replaced by the blocks; the row tree (+ its cut_k colours) still draws
    assert "xaxis3" not in fig["layout"]
    assert "xaxis2" in fig["layout"]
    row_colors = {t["line"]["color"] for t in _row_tree_traces(fig)}
    assert row_colors & set(_CLUSTER_PALETTE)  # row branches still coloured by cut_k


def test_split_by_cut_needs_cut_k():
    # split_by_cut on but cut_k < 2 → no split (honest), the plain clustered map with the column tree
    fig = _run({"n_genes": 12, "cluster": "both", "cut_k": 0, "split_by_cut": True})
    main = next(t for t in fig["data"] if t["type"] == "heatmap")
    assert " " not in main["x"]
    assert "annotations" not in fig["layout"]
    assert "xaxis3" in fig["layout"]  # column tree kept (no split happened)


def test_categorical_split_takes_precedence_over_cut():
    # both split_by (sheet) and split_by_cut set → the explicit categorical split wins
    fig = _run_with_design(
        {"n_genes": 12, "cluster": "both", "cut_k": 2, "split_by": "condition", "split_by_cut": True}
    )
    headers = [h["text"] for h in fig["layout"]["annotations"]]
    assert headers == ["ko", "wt"]  # the sheet's categories, NOT "Cluster N"
