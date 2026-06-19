"""diff_abundance: count-matrix build, contrast selection, and the light fallback.

Builds a tiny synthetic h5ad (cells with sample / condition / cell_type obs) and runs the
real engine with pyDESeq2 hidden, so the deterministic proportion + Welch-t fallback path
is exercised end-to-end (crosstab -> contrast -> test -> figure + table) on numpy / scipy /
anndata only. Real pyDESeq2 + TMM numerics are validated by live dogfooding, not here —
matching the heavy-dep-free convention of test_deg_bulk.
"""

import sys

import numpy as np
import pytest

from skills.diff_abundance.run_real import _bh, _pick_contrast


@pytest.fixture
def no_pydeseq2(monkeypatch):
    """Hide pyDESeq2 (+ submodules) so the runner takes its light fallback path."""
    for m in ("pydeseq2", "pydeseq2.dds", "pydeseq2.ds"):
        monkeypatch.setitem(sys.modules, m, None)


def _write_h5ad(path, per_sample):
    """per_sample: {sample: (condition, {cell_type: n_cells})} -> a minimal h5ad on disk."""
    import anndata as ad
    import pandas as pd

    ad.settings.allow_write_nullable_strings = True
    samples, conds, types = [], [], []
    for s, (cond, comp) in per_sample.items():
        for ct, n in comp.items():
            samples += [s] * n
            conds += [cond] * n
            types += [ct] * n
    n = len(samples)
    a = ad.AnnData(np.zeros((n, 3), dtype=float))
    a.obs = pd.DataFrame({"sample": samples, "condition": conds, "cell_type": types}, index=[f"c{i}" for i in range(n)])
    a.write_h5ad(path)
    return str(path)


def test_fallback_recovers_expansion_and_shrinkage(tmp_path, no_pydeseq2):
    # Call the real engine directly so the test is independent of SELOM_SKILLS_ENGINE
    # (run_real attaches the table to the figure before the contract pops it).
    from skills.diff_abundance.run_real import run as run_da

    # A expands in MUT (10% -> 40%), B shrinks (40% -> 10%), C unchanged (~50%).
    wt = ("WT", {"A": 10, "B": 40, "C": 50})
    mut = ("MUT", {"A": 40, "B": 10, "C": 50})
    per = {"WT1": wt, "WT2": ("WT", {"A": 11, "B": 39, "C": 50}), "WT3": ("WT", {"A": 9, "B": 41, "C": 50}),
           "MUT1": mut, "MUT2": ("MUT", {"A": 41, "B": 9, "C": 50}), "MUT3": ("MUT", {"A": 39, "B": 11, "C": 50})}
    path = _write_h5ad(tmp_path / "da.h5ad", per)

    fig = run_da(path, {"reference": "WT", "treatment": "MUT", "label_col": "cell_type"})
    tbl = fig["table"]
    by_cluster = {r[0]: r for r in tbl["rows"]}  # [cluster, lfc, padj, cells, direction]
    assert by_cluster["A"][1] > 0.5 and by_cluster["A"][4] == "expanding"
    assert by_cluster["B"][1] < -0.5 and by_cluster["B"][4] == "shrinking"
    assert abs(by_cluster["C"][1]) < 0.3                  # unchanged cluster ~ 0
    assert "pyDESeq2 absent" in fig["layout"]["title"]["text"]  # fallback engine labelled
    # The consistent A/B shifts across 3 replicates should clear FDR; C should not.
    assert by_cluster["A"][2] < 0.05 and by_cluster["B"][2] < 0.05
    assert by_cluster["C"][2] > 0.05


def test_min_cells_drops_sparse_cluster(tmp_path, no_pydeseq2):
    from skills.diff_abundance.run_real import run as run_da

    per = {"WT1": ("WT", {"A": 50, "RARE": 1}), "WT2": ("WT", {"A": 50, "RARE": 0}),
           "MUT1": ("MUT", {"A": 50, "RARE": 1}), "MUT2": ("MUT", {"A": 50, "RARE": 0})}
    path = _write_h5ad(tmp_path / "da2.h5ad", per)
    fig = run_da(path, {"reference": "WT", "treatment": "MUT", "label_col": "cell_type", "min_cells": 10})
    clusters = {r[0] for r in fig["table"]["rows"]}
    assert "A" in clusters and "RARE" not in clusters     # RARE (2 cells) dropped


def test_pick_contrast_contracts():
    assert _pick_contrast({}, ["A", "B"], "condition") == ("A", "B")  # two groups default
    with pytest.raises(ValueError, match="2-group contrast"):
        _pick_contrast({}, ["A", "B", "C"], "condition")            # ambiguous -> must specify
    with pytest.raises(ValueError, match="not among"):
        _pick_contrast({"reference": "A", "treatment": "Z"}, ["A", "B"], "condition")


def test_bh_monotone_capped():
    p = np.array([0.001, 0.5, 0.9, 1.0])
    adj = _bh(p)
    assert adj.max() <= 1.0 and np.argmin(adj) == np.argmin(p)
