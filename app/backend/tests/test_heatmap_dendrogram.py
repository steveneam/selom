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
