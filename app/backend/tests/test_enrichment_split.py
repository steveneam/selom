"""enrichment ``direction=split`` — up/down ORA as a diverging dotplot (Suppl Fig 6 / 5C).

The up- and down-regulated significant genes are scored separately: up terms land on the
right (positive x), down terms on the left (negative x). Covers the deterministic stub
shape, the real-engine direction assignment (gene sets monkeypatched so the test does not
depend on the bundled corpus), and the honest error when no fold-change column is present.
"""

import os
import tempfile

import pytest

from skills.contract import run_skill

pytest.importorskip("pandas")
pytest.importorskip("scipy")

SETS = {"UP_SET": [f"A{i}" for i in range(1, 7)], "DOWN_SET": [f"B{i}" for i in range(1, 7)]}


def _de_csv(path: str, with_fc: bool = True) -> None:
    import pandas as pd

    rows = []
    for g in SETS["UP_SET"]:
        r = {"gene": g, "padj": 0.001}
        if with_fc:
            r["log2FoldChange"] = 2.0
        rows.append(r)
    for g in SETS["DOWN_SET"]:
        r = {"gene": g, "padj": 0.001}
        if with_fc:
            r["log2FoldChange"] = -2.0
        rows.append(r)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_stub_split_two_directional_traces(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    fig = run_skill("enrichment", "unused", {"direction": "split"})

    up = next(t for t in fig["data"] if t["name"] == "Up-regulated")
    down = next(t for t in fig["data"] if t["name"] == "Down-regulated")
    assert all(x > 0 for x in up["x"]), "up terms must sit on the right"
    assert all(x < 0 for x in down["x"]), "down terms must sit on the left"
    assert fig["layout"]["yaxis"]["categoryorder"] == "array"
    import json

    assert json.loads(json.dumps(fig)) == fig  # plain JSON, no leakage


def test_real_split_assigns_direction(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "real")
    monkeypatch.setattr("skills.enrichment.run_real._load_gene_sets", lambda src=None: SETS)
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        _de_csv(path)
        fig = run_skill("enrichment", path, {"direction": "split", "top_n": 10})
    finally:
        os.unlink(path)

    traces = {t["name"]: t for t in fig["data"]}
    assert traces["Up-regulated"]["y"] == ["UP_SET"]
    assert traces["Up-regulated"]["x"][0] > 0
    assert traces["Down-regulated"]["y"] == ["DOWN_SET"]
    assert traces["Down-regulated"]["x"][0] < 0


def test_real_split_without_fc_errors(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "real")
    monkeypatch.setattr("skills.enrichment.run_real._load_gene_sets", lambda src=None: SETS)
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        _de_csv(path, with_fc=False)
        with pytest.raises(ValueError, match="fold-change"):
            run_skill("enrichment", path, {"direction": "split"})
    finally:
        os.unlink(path)
