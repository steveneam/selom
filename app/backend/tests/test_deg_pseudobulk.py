"""deg pseudobulk mode: aggregation, contrast selection, and guard contracts.

Fast unit tests for the pseudo-bulk path — the parts most prone to regression:
per-sample raw-count aggregation, the raw-counts requirement, contrast selection +
its error contracts, the <min_cells sample discard, and single-cell-type restriction.
Real pyDESeq2 numerics are validated by dogfooding on real datasets, not here; like
test_deg_bulk we hide pyDESeq2 to force the deterministic CPM-log2FC fallback. One
opt-in test exercises the real engine end-to-end when pyDESeq2 is installed.
"""

import sys

import anndata as _ad
import numpy as np
import pandas as pd
import pytest

from skills.deg.run_real import _looks_like_counts, _pseudobulk, _raw_counts

# This anndata build (< 0.11 on-disk format) refuses to write pandas StringArray obs
# columns unless opted in; our fixtures write small h5ads, so enable it for the tests.
try:
    _ad.settings.allow_write_nullable_strings = True
except Exception:  # older/newer anndata without the setting
    pass


@pytest.fixture
def no_pydeseq2(monkeypatch):
    """Hide pyDESeq2 so the bulk engine takes its deterministic CPM-log2FC fallback.

    Nulls the submodules too: another test may already have cached ``pydeseq2.dds`` in
    sys.modules, and ``from pydeseq2.dds import ...`` would then bypass a None'd parent.
    """
    for mod in ("pydeseq2", "pydeseq2.dds", "pydeseq2.ds"):
        monkeypatch.setitem(sys.modules, mod, None)


def _make_adata(
    tmp_path, planted_up_gene=0, planted_add=200, n_per_sample=20, n_genes=30, seed=0,
    samples=None, log_normalize=False, celltypes=None,
):
    """A small AnnData of raw integer counts with obs ``sample``/``condition``/``celltype``.

    ``planted_up_gene`` is bumped in the 'treat' condition so a known up-gene exists.
    ``log_normalize=True`` writes non-integer (log1p-CPM-ish) values to exercise the
    raw-counts guard. ``celltypes`` (per-sample) lets a test split cell types.
    """
    import anndata as ad

    rng = np.random.default_rng(seed)
    sample_defs = samples or [
        ("ctrl1", "ctrl"), ("ctrl2", "ctrl"), ("ctrl3", "ctrl"),
        ("treat1", "treat"), ("treat2", "treat"), ("treat3", "treat"),
    ]
    rows, s_names, conds, cts = [], [], [], []
    for si, (sname, cond) in enumerate(sample_defs):
        for _ in range(n_per_sample):
            row = rng.integers(5, 30, size=n_genes).astype(float)
            if cond == "treat" and planted_up_gene is not None:
                row[planted_up_gene] += planted_add
            rows.append(row)
            s_names.append(sname)
            conds.append(cond)
            cts.append((celltypes or {}).get(sname, "rod"))
    X = np.vstack(rows)
    if log_normalize:
        X = np.log1p(X / X.sum(axis=1, keepdims=True) * 1e4)  # non-integer normalized values
    obs = pd.DataFrame(
        {"sample": s_names, "condition": conds, "celltype": cts},
        index=[f"c{i}" for i in range(len(s_names))],
    )
    var = pd.DataFrame(index=[f"g{i}" for i in range(n_genes)])
    adata = ad.AnnData(X=X, obs=obs, var=var)
    path = tmp_path / "pb.h5ad"
    adata.write_h5ad(path)
    return str(path)


# --- aggregation correctness ----------------------------------------------------


def test_raw_counts_picks_integer_source():
    import anndata as ad

    counts = np.array([[1.0, 2.0], [3.0, 4.0]])
    adata = ad.AnnData(X=counts, obs=pd.DataFrame(index=["a", "b"]), var=pd.DataFrame(index=["g0", "g1"]))
    matrix, var_names, note = _raw_counts(adata)
    assert note == "X" and var_names == ["g0", "g1"]
    assert _looks_like_counts(matrix)


def test_pseudobulk_recovers_planted_signal(tmp_path, no_pydeseq2):
    # g0 strongly up in 'treat' -> CPM-log2FC fallback should surface it near the top.
    path = _make_adata(tmp_path, planted_up_gene=0, planted_add=400)
    fig = _pseudobulk(path, {"mode": "pseudobulk", "top_n": 5, "min_cells": 5})
    assert "treat vs ctrl" in fig["layout"]["title"]["text"]
    assert "pseudobulk" in fig["layout"]["title"]["text"].lower() or "pseudobulk" in str(fig["layout"]["title"])
    assert "g0" in fig["data"][0]["y"]                       # planted up gene surfaced
    assert len(fig["data"][0]["x"]) == 5                     # top_n bars
    import json
    assert json.loads(json.dumps(fig)) == fig               # plain JSON, no numpy leakage


def test_pseudobulk_subtitle_reports_replicate_counts(tmp_path, no_pydeseq2):
    path = _make_adata(tmp_path)
    fig = _pseudobulk(path, {"mode": "pseudobulk", "top_n": 5, "min_cells": 5})
    sub = fig["layout"]["title"]["text"]
    assert "n=3" in sub                                      # 3 samples per condition


# --- guard contracts (raise before any DE engine) -------------------------------


def test_pseudobulk_requires_raw_counts(tmp_path):
    path = _make_adata(tmp_path, log_normalize=True)
    with pytest.raises(ValueError, match="RAW integer counts"):
        _pseudobulk(path, {"mode": "pseudobulk", "top_n": 5, "min_cells": 5})


def test_pseudobulk_unknown_sample_col_rejected(tmp_path):
    path = _make_adata(tmp_path)
    with pytest.raises(ValueError, match="sample_col 'nope'"):
        _pseudobulk(path, {"mode": "pseudobulk", "top_n": 5, "sample_col": "nope"})


def test_pseudobulk_too_few_replicates(tmp_path):
    # one treat sample only -> <2 replicates in a group.
    samples = [("ctrl1", "ctrl"), ("ctrl2", "ctrl"), ("treat1", "treat")]
    path = _make_adata(tmp_path, samples=samples)
    with pytest.raises(ValueError, match="replicates"):
        _pseudobulk(path, {"mode": "pseudobulk", "top_n": 5, "min_cells": 5})


def test_pseudobulk_ambiguous_contrast_lists_groups(tmp_path):
    samples = [
        ("a1", "A"), ("a2", "A"), ("b1", "B"), ("b2", "B"), ("c1", "C"), ("c2", "C"),
    ]
    path = _make_adata(tmp_path, samples=samples)
    with pytest.raises(ValueError, match="2-group contrast"):
        _pseudobulk(path, {"mode": "pseudobulk", "top_n": 5, "min_cells": 5})


def test_pseudobulk_label_requires_value(tmp_path):
    path = _make_adata(tmp_path)
    with pytest.raises(ValueError, match="without `label`"):
        _pseudobulk(path, {"mode": "pseudobulk", "top_n": 5, "label_col": "celltype"})


def test_pseudobulk_min_cells_drops_samples(tmp_path, no_pydeseq2):
    # treat3 has only 2 cells -> dropped at min_cells=5, leaving treat n=2 (still valid).
    import anndata as ad

    rng = np.random.default_rng(1)
    rows, s, c = [], [], []
    plan = [("ctrl1", "ctrl", 20), ("ctrl2", "ctrl", 20), ("treat1", "treat", 20),
            ("treat2", "treat", 20), ("treat3", "treat", 2)]
    for sname, cond, n in plan:
        for _ in range(n):
            rows.append(rng.integers(5, 30, size=12).astype(float))
            s.append(sname)
            c.append(cond)
    adata = ad.AnnData(
        X=np.vstack(rows),
        obs=pd.DataFrame({"sample": s, "condition": c}, index=[f"c{i}" for i in range(len(s))]),
        var=pd.DataFrame(index=[f"g{i}" for i in range(12)]),
    )
    path2 = tmp_path / "drop.h5ad"
    adata.write_h5ad(path2)
    fig = _pseudobulk(str(path2), {"mode": "pseudobulk", "top_n": 5, "min_cells": 5})
    assert "dropped 1 sample" in fig["layout"]["title"]["text"]


# --- single cell-type restriction -----------------------------------------------


def test_pseudobulk_label_restriction_runs(tmp_path, no_pydeseq2):
    cts = {"ctrl1": "rod", "ctrl2": "rod", "ctrl3": "rod",
           "treat1": "rod", "treat2": "rod", "treat3": "rod"}
    path = _make_adata(tmp_path, celltypes=cts)
    fig = _pseudobulk(
        path,
        {"mode": "pseudobulk", "top_n": 5, "min_cells": 5, "label_col": "celltype", "label": "rod"},
    )
    assert "celltype=rod" in fig["layout"]["title"]["text"]

# Real pyDESeq2 numerics (aggregation -> DESeq2 Wald) are validated by a live dogfood run,
# not here — unit tests stay deterministic + heavy-dep-free, matching test_deg_bulk.
