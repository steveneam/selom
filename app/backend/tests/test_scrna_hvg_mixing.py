"""HVG selection + integration batch-mixing diagnostic (OSCA Gaps B/G).

Fast, deterministic unit tests. ``_batch_mixing`` is exercised on synthetic embeddings
(numpy + sklearn — no scanpy); ``select_hvg`` no-op guards need no heavy deps, and one
test confirms the real Seurat-flavour subset works (scanpy, already in the suite).
"""

import numpy as np

from skills._scrna import select_hvg
from skills.integration.run_real import _batch_mixing


# --- batch-mixing diagnostic ----------------------------------------------------


def test_mixing_low_for_separated_batches():
    rng = np.random.default_rng(0)
    # Batch A near the origin, batch B far away: every cell's neighbours are same-batch.
    emb = np.vstack([rng.normal(0, 1, (100, 2)), rng.normal(100, 1, (100, 2))])
    m = _batch_mixing(emb, ["A"] * 100 + ["B"] * 100, k=15)
    assert m is not None and m < 0.2          # ~0 = unmixed


def test_mixing_high_for_overlapping_batches():
    rng = np.random.default_rng(1)
    # Both batches drawn from the SAME distribution -> neighbours are ~50/50 -> ~1.
    emb = rng.normal(0, 1, (200, 2))
    m = _batch_mixing(emb, ["A", "B"] * 100, k=20)
    assert m > 0.8                            # ~1 = well mixed


def test_mixing_none_for_single_batch():
    emb = np.random.default_rng(2).normal(0, 1, (50, 2))
    assert _batch_mixing(emb, ["A"] * 50) is None


# --- HVG selection --------------------------------------------------------------


def test_select_hvg_noop_guards():
    import anndata as ad

    a = ad.AnnData(np.ones((10, 5), dtype=float))
    assert select_hvg(a, 0) is a              # disabled -> same object (no scanpy needed)
    assert select_hvg(a, 5) is a              # n_hvg == n_vars -> no-op
    assert select_hvg(a, 99) is a             # n_hvg > n_vars -> no-op


def test_select_hvg_subsets_to_top_n():
    import anndata as ad

    rng = np.random.default_rng(0)
    a = ad.AnnData(np.log1p(rng.poisson(2, size=(80, 40)).astype(float)))
    out = select_hvg(a, 10)
    assert out.n_vars == 10 and out.n_obs == 80   # genes subset, cells preserved
