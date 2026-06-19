"""Selom Melody — clean-room batch-integration tests (proprietary engine).

Validates the pure-numpy Harmony-method reimplementation (``skills/integration/melody``)
on synthetic data with a KNOWN batch shift, where the right answer is unambiguous: a
deterministic two-batch set whose batches differ only by a constant offset must come back
with (a) that offset removed (per-cell-type batch centroids coincide), (b) cell-type
structure preserved (not over-corrected), and (c) batches mixed in the kNN graph. No heavy
deps. Real-data validation against the harmonypy oracle on GSE201356 is a dogfood reported
in the handoff, not a CI fixture (the engine is stochastic in its init; we validate by the
mixing METRIC, not a pixel-identical embedding).
"""

import numpy as np
import pytest

from skills.integration.melody import melody

D = 10              # embedding dimensions (PCs)
N_PER = 150         # cells per (cell type, batch)


def _two_batch_with_shift(seed=42):
    """3 cell types as Gaussian blobs in D dims; batch B = batch A + a constant offset.

    Returns (Z, celltype, batch, shift_norm). The ONLY difference between batches is the
    additive ``shift`` — so a correct integration collapses the per-type batch gap to ~0
    while keeping the three cell types apart.
    """
    rng = np.random.default_rng(seed)
    centers = rng.normal(0, 5, size=(3, D))
    shift = rng.normal(0, 3, size=D)

    def blob(offset):
        xs, ct = [], []
        for c in range(3):
            xs.append(centers[c] + rng.normal(0, 0.6, size=(N_PER, D)) + offset)
            ct += [c] * N_PER
        return np.vstack(xs), np.array(ct)

    Xa, cta = blob(np.zeros(D))
    Xb, ctb = blob(shift)
    Z = np.vstack([Xa, Xb])
    celltype = np.concatenate([cta, ctb])
    batch = np.array(["A"] * len(Xa) + ["B"] * len(Xb))
    return Z, celltype, batch, float(np.linalg.norm(shift))


def _batch_gap(emb, celltype, batch):
    """Mean distance between batch-A and batch-B centroids WITHIN each cell type."""
    gaps = []
    for c in np.unique(celltype):
        a = emb[(celltype == c) & (batch == "A")].mean(0)
        b = emb[(celltype == c) & (batch == "B")].mean(0)
        gaps.append(np.linalg.norm(a - b))
    return float(np.mean(gaps))


def _celltype_separation(emb, celltype):
    """Between-type spread / within-type spread — higher = better-separated cell types."""
    gm = emb.mean(0)
    between = np.mean([np.linalg.norm(emb[celltype == c].mean(0) - gm) for c in np.unique(celltype)])
    within = np.mean([emb[celltype == c].std(0).mean() for c in np.unique(celltype)])
    return float(between / within)


def _knn_mixing(emb, batch, k=30):
    """Mean normalized kNN batch-entropy (1 = fully mixed, 0 = each cell's neighbours are
    one batch) — the same diagnostic the integration skill emits."""
    from sklearn.neighbors import NearestNeighbors

    cats, codes = np.unique(batch, return_inverse=True)
    _, idx = NearestNeighbors(n_neighbors=k + 1).fit(emb).kneighbors(emb)
    neigh = codes[idx[:, 1:]]
    ent = np.zeros(len(batch))
    for c in range(len(cats)):
        p = (neigh == c).mean(axis=1)
        nz = p > 0
        ent[nz] -= p[nz] * np.log(p[nz])
    return float((ent / np.log(len(cats))).mean())


def test_removes_known_batch_shift():
    """The core property: a pure additive batch offset is regressed out — the per-cell-type
    gap between batches collapses from ~the shift magnitude to near zero."""
    Z, celltype, batch, shift_norm = _two_batch_with_shift()
    before = _batch_gap(Z, celltype, batch)
    after = _batch_gap(melody(Z, batch, random_state=0), celltype, batch)
    assert before > 0.8 * shift_norm                 # before ~ the injected shift
    assert after < 0.2 * before                      # >80% of the batch gap removed


def test_preserves_celltype_structure():
    """Integration must not over-correct: the three cell types stay at least as separated
    after as before (Melody's deliberate single-linear-model design avoids collapse)."""
    Z, celltype, batch, _ = _two_batch_with_shift()
    before = _celltype_separation(Z, celltype)
    after = _celltype_separation(melody(Z, batch, random_state=0), celltype)
    assert after >= before


def test_increases_batch_mixing():
    """Batches should interleave in the kNN graph after correction."""
    Z, _, batch, _ = _two_batch_with_shift()
    assert _knn_mixing(Z, batch) < 0.2               # cleanly batch-separated to start
    assert _knn_mixing(melody(Z, batch, random_state=0), batch) > 0.8


def test_deterministic_with_seed():
    """Same input + random_state -> bit-stable output (seeded KMeans + block order)."""
    Z, _, batch, _ = _two_batch_with_shift()
    a = melody(Z, batch, theta=2.0, random_state=0)
    b = melody(Z, batch, theta=2.0, random_state=0)
    assert np.allclose(a, b)


def test_single_batch_is_noop():
    """Fewer than two batches -> nothing to integrate -> Z returned unchanged."""
    Z, _, _, _ = _two_batch_with_shift()
    out = melody(Z, np.array(["only"] * len(Z)))
    assert np.array_equal(out, Z)


def test_shape_and_orientation_preserved():
    """(N, d) in -> (N, d) out, same orientation as scanpy's obsm['X_pca']."""
    Z, _, batch, _ = _two_batch_with_shift()
    out = melody(Z, batch, random_state=0)
    assert out.shape == Z.shape


def test_tiny_n_does_not_crash():
    """Very small N (K heuristic floors to 1) still returns a valid corrected embedding."""
    rng = np.random.default_rng(0)
    Z = rng.normal(size=(20, D))
    batch = np.array(["A", "B"] * 10)
    out = melody(Z, batch, random_state=0)
    assert out.shape == (20, D)
    assert np.isfinite(out).all()


def test_rejects_non_finite():
    Z, _, batch, _ = _two_batch_with_shift()
    Z = Z.copy()
    Z[0, 0] = np.nan
    with pytest.raises(ValueError):
        melody(Z, batch)


def test_rejects_batch_length_mismatch():
    Z, _, batch, _ = _two_batch_with_shift()
    with pytest.raises(ValueError):
        melody(Z, batch[:-5])
