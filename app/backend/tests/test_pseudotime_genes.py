"""pseudotime_genes: gene-vs-pseudotime correlation + BH + curve gap-filling.

Deterministic unit tests for the pure helpers (`_spearman_vs_pseudotime`,
`_benjamini_hochberg`, `_fill_gaps`), exercised on a tiny in-memory AnnData so they need
only numpy/scipy/anndata — no scanpy. The full DPT + figure wiring is verified live on
real data (matching the heavy-dep-free convention of test_qc_filter / test_deg_bulk).
"""

import math

import numpy as np

from skills.pseudotime_genes.run_real import (
    _benjamini_hochberg,
    _fill_gaps,
    _spearman_vs_pseudotime,
)


def _adata(X, genes):
    import anndata as ad
    import pandas as pd

    a = ad.AnnData(np.asarray(X, dtype=float))
    a.var_names = pd.Index(genes)
    return a


def test_spearman_signs_and_significance():
    pt = np.arange(60, dtype=float)
    rng = np.random.default_rng(0)
    rising = pt + rng.normal(0, 2, 60)          # tracks pseudotime  -> rho ~ +1
    falling = -pt + rng.normal(0, 2, 60)        # anti-tracks        -> rho ~ -1
    flat = rng.normal(0, 1, 60)                 # no relation        -> rho ~ 0
    X = np.column_stack([rising, falling, flat])
    genes, rho, pval, padj = _spearman_vs_pseudotime(_adata(X, ["UP", "DOWN", "FLAT"]), pt)

    assert genes == ["UP", "DOWN", "FLAT"]
    assert rho[0] > 0.9 and rho[1] < -0.9       # correct direction + strength
    assert abs(rho[2]) < 0.4
    assert padj[0] < 0.01 and padj[1] < 0.01    # strong trends are significant
    assert padj[2] > padj[0]                    # the flat gene is less significant


def test_benjamini_hochberg_matches_reference():
    p = np.array([0.01, 0.02, 0.03, 0.04, 0.05])
    adj = _benjamini_hochberg(p)
    # Step-up: each p * n / rank, then monotone-enforced from the largest. All equal 0.05 here.
    assert np.allclose(adj, 0.05)
    assert (adj <= 1.0).all() and (adj >= p).all()  # never below the raw p, capped at 1


def test_benjamini_hochberg_monotone_and_capped():
    p = np.array([0.5, 0.9, 0.001, 1.0])
    adj = _benjamini_hochberg(p)
    assert adj.max() <= 1.0
    # the smallest raw p gets the smallest adjusted p
    assert np.argmin(adj) == np.argmin(p)


def test_fill_gaps_interior_leading_and_all_empty():
    nan = float("nan")
    assert _fill_gaps([1.0, nan, 3.0]) == [1.0, 1.0, 3.0]      # interior -> forward fill
    assert _fill_gaps([nan, nan, 2.0, 4.0]) == [2.0, 2.0, 2.0, 4.0]  # leading -> back fill
    assert _fill_gaps([nan, nan]) == [0.0, 0.0]                # all empty -> zeros
    assert all(not math.isnan(v) for v in _fill_gaps([nan, 5.0, nan]))
