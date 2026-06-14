"""heatmap ``dendrogram`` option — draws the row clustering tree alongside the map.

Real engine on a small bulk CSV: ``dendrogram='row'`` adds a second (dendrogram-line) trace
on a left gutter axis, moves the row labels to the right, and tucks a horizontal colour key
at the bottom — the conventional clustermap layout (paper Fig 1c / Fig 5). ``dendrogram='none'``
(default) stays the single-trace heatmap. Also guards that the publication theme preserves
``yaxis.side`` (a recurring axis keep-whitelist gotcha). Skipped without pandas/scipy.
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


def test_dendrogram_none_is_single_trace():
    fig = _run({"n_genes": 12})
    assert [t["type"] for t in fig["data"]] == ["heatmap"]
    assert "xaxis2" not in fig["layout"]


def test_dendrogram_row_adds_tree_and_moves_labels():
    fig = _run({"n_genes": 12, "dendrogram": "row"})
    assert [t["type"] for t in fig["data"]] == ["heatmap", "scatter"]
    # dendrogram lines live on the left gutter axis
    assert fig["data"][1]["xaxis"] == "x2"
    assert "xaxis2" in fig["layout"] and "yaxis2" in fig["layout"]
    # tree on the left -> row labels on the right (theme must preserve yaxis.side)
    assert fig["layout"]["yaxis"]["side"] == "right"
    # small horizontal colour key tucked at the bottom
    assert fig["data"][0]["colorbar"]["orientation"] == "h"
