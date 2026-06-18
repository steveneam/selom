"""normalization_qc adaptive MAD filter: per-group outlier flagging + summary table.

Fast, deterministic unit tests for the scater/OSCA-style adaptive filter logic
(``_adaptive_filter``), exercised directly on a small obs DataFrame so they need only
numpy/pandas/scipy — no scanpy. The full ``run`` integration (figure + table wiring) is
verified live on real data, matching the heavy-dep-free convention of test_deg_bulk.
"""

import numpy as np
import pandas as pd

from skills.normalization_qc.run_real import _adaptive_filter


def _obs(groups, total, genes, mito):
    return pd.DataFrame(
        {
            "sample": list(groups),
            "total_counts": np.asarray(total, dtype=float),
            "n_genes_by_counts": np.asarray(genes, dtype=float),
            "pct_counts_mt": np.asarray(mito, dtype=float),
        }
    )


def test_flags_low_library_and_high_mito():
    rng = np.random.default_rng(0)
    n = 60
    total = rng.normal(5000, 150, n)
    genes = rng.normal(1500, 30, n)
    mito = rng.normal(5, 0.6, n)
    total[0] = 50   # low-library outlier  -> flagged via log library size
    mito[1] = 60    # high-mito  outlier   -> flagged via mitochondrial %
    discard, rows = _adaptive_filter(_obs(["S1"] * n, total, genes, mito), "sample", 3.0)

    assert discard[0] and discard[1]              # both planted outliers flagged
    assert not discard[30]                        # a clearly-normal cell is kept
    assert discard.sum() <= 3                      # no runaway over-flagging
    assert rows[0][:1] == ["S1"] and rows[0][3] >= 2  # group row records the removals


def test_per_group_thresholds_are_adaptive():
    # Two batches with very different sequencing depth: a cell normal for the LOW-depth
    # batch must NOT be flagged just because it looks low against the HIGH-depth batch.
    rng = np.random.default_rng(1)
    a_total = rng.normal(5000, 150, 40)
    b_total = rng.normal(500, 25, 40)
    a_total[0] = 500  # outlier for batch A (its median ~5000), but a normal value for B
    total = np.concatenate([a_total, b_total])
    genes = np.concatenate([rng.normal(1500, 40, 40), rng.normal(400, 15, 40)])
    mito = np.concatenate([rng.normal(5, 0.5, 40), rng.normal(5, 0.5, 40)])
    groups = ["A"] * 40 + ["B"] * 40
    discard, rows = _adaptive_filter(_obs(groups, total, genes, mito), "sample", 3.0)

    assert discard[0]                              # 500 is a low outlier within batch A
    assert not discard[40:].any()                  # batch B (~500) is normal for B -> kept
    assert rows[-1][0] == "all"                    # overall row appended for >1 group


def test_zero_mad_degenerate_flags_nothing():
    n = 20
    discard, _ = _adaptive_filter(_obs(["S"] * n, [1000.0] * n, [500.0] * n, [5.0] * n), "sample", 3.0)
    assert not discard.any()                       # constant metric (MAD=0) flags nothing


def test_summary_rows_consistent_and_overall():
    rng = np.random.default_rng(2)
    total = rng.normal(5000, 200, 30)
    total[0] = 10
    obs = _obs(["S1"] * 15 + ["S2"] * 15, total, rng.normal(1500, 50, 30), rng.normal(5, 1, 30))
    discard, rows = _adaptive_filter(obs, "sample", 3.0)

    for group, n_cells, kept, removed, pct in rows:
        assert kept + removed == n_cells           # kept + removed == cells, every row
        assert 0.0 <= pct <= 100.0
    assert rows[-1][0] == "all" and rows[-1][1] == 30 and rows[-1][3] == int(discard.sum())


def test_groupby_none_single_overall_group():
    rng = np.random.default_rng(3)
    obs = pd.DataFrame(
        {
            "total_counts": rng.normal(5000, 200, 25),
            "n_genes_by_counts": rng.normal(1500, 50, 25),
            "pct_counts_mt": rng.normal(5, 1, 25),
        }
    )
    discard, rows = _adaptive_filter(obs, None, 3.0)
    assert len(rows) == 1 and rows[0][0] == "all"  # no groupby -> one 'all' group
    assert len(discard) == 25
