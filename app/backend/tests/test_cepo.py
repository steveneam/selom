"""Cepo differential-stability — algorithm-recovery tests (proprietary skill).

Validates the clean-room Cepo reimplementation (``skills/proprietary/cepo``) on
synthetic data where the ground truth is known. The defining Cepo property — the reason
it beats a mean-difference test — is that a **stably** expressed identity gene must
outrank a **noisy** gene of the *same mean* within a cell type. These tests pin exactly
that, plus per-type specificity, with no heavy data. (Real-data validation against the
Hani mmc2 Cepo oracle is a dogfood, reported in the handoff, not a CI fixture.)
"""

import numpy as np
import pytest

from skills.proprietary.cepo.run_real import cepo_ds

N_PER_TYPE = 120
N_MARK = 10  # genes per signature block


def _synthetic():
    """3 cell types. Type A carries two blocks with the SAME mean (~3.0) but opposite
    stability: A_stable (steady → low CV, full detection) and A_noisy (bursty → high CV,
    half detection). B/C carry their own steady markers. Background is low noise."""
    rng = np.random.default_rng(0)
    types = ["A", "B", "C"]
    labels = np.repeat(types, N_PER_TYPE)
    n = len(labels)

    blocks = ["A_stable", "A_noisy", "B_mark", "C_mark"]
    n_bg = 60
    genes, owner = [], []
    for b in blocks:
        for i in range(N_MARK):
            genes.append(f"{b}_{i}")
            owner.append(b)
    for i in range(n_bg):
        genes.append(f"bg_{i}")
        owner.append("bg")
    G = len(genes)

    # Signature genes are zero outside their type; background genes are housekeeping —
    # expressed the SAME in every type, so they carry ~0 differential stability and never
    # crowd a type's top markers. Within its type, each signature block sets its pattern.
    X = np.zeros((n, G))
    is_a, is_b, is_c = labels == "A", labels == "B", labels == "C"
    for gi, b in enumerate(owner):
        if b == "bg":
            X[:, gi] = rng.normal(2.0, 0.6, size=n).clip(min=0)               # housekeeping, DS~0
        elif b == "A_stable":
            X[is_a, gi] = rng.normal(3.0, 0.10, size=is_a.sum()).clip(min=0)  # steady, CV~0.03
        elif b == "A_noisy":
            X[is_a, gi] = rng.binomial(1, 0.2, size=is_a.sum()) * 15.0         # mean~3, bursty CV~2
        elif b == "B_mark":
            X[is_b, gi] = rng.normal(3.0, 0.10, size=is_b.sum()).clip(min=0)
        elif b == "C_mark":
            X[is_c, gi] = rng.normal(3.0, 0.10, size=is_c.sum()).clip(min=0)
    return X, labels, np.array(genes), np.array(owner)


def test_cepo_ds_shape_and_columns():
    X, labels, genes, _ = _synthetic()
    ds, det = cepo_ds(X, labels, genes=genes)
    assert list(ds.columns) == ["A", "B", "C"]
    assert ds.shape == det.shape
    assert (det.to_numpy() >= 0).all() and (det.to_numpy() <= 1).all()


def test_stable_outranks_noisy_in_same_type():
    """The core Cepo property: in type A, the steady markers must score higher DS than
    the bursty same-mean markers — a mean-difference test would rank them similarly."""
    X, labels, genes, owner = _synthetic()
    ds, _ = cepo_ds(X, labels, genes=genes)
    stable = ds.loc[[g for g, o in zip(genes, owner) if o == "A_stable"], "A"]
    noisy = ds.loc[[g for g, o in zip(genes, owner) if o == "A_noisy"], "A"]
    assert stable.min() > noisy.max(), "every stable marker should beat every noisy one in DS"


def test_top_ds_per_type_is_that_types_signature():
    """The top-N DS genes of each type are dominated by that type's own steady markers."""
    X, labels, genes, owner = _synthetic()
    ds, _ = cepo_ds(X, labels, genes=genes)
    owner_of = dict(zip(genes, owner))
    for ctype, sig in (("A", "A_stable"), ("B", "B_mark"), ("C", "C_mark")):
        top = ds[ctype].sort_values(ascending=False).head(N_MARK).index
        hits = sum(owner_of[g] == sig for g in top)
        assert hits >= N_MARK - 1, f"{ctype}: only {hits}/{N_MARK} top-DS were {sig}"


def test_marker_ds_is_type_specific():
    """A type's steady markers carry their highest DS in that type, not the others."""
    X, labels, genes, owner = _synthetic()
    ds, _ = cepo_ds(X, labels, genes=genes)
    a_stable = [g for g, o in zip(genes, owner) if o == "A_stable"]
    assert (ds.loc[a_stable, "A"] > ds.loc[a_stable, "B"]).all()
    assert (ds.loc[a_stable, "A"] > ds.loc[a_stable, "C"]).all()


def test_requires_two_types():
    X, labels, genes, _ = _synthetic()
    one = np.where(labels == "A", "A", "A")  # collapse to a single type
    with pytest.raises(ValueError):
        cepo_ds(X, one, genes=genes)


def test_run_real_end_to_end_on_tiny_anndata():
    """Exercise the skill entrypoint (label-column resolve → figure + Statistics table)."""
    pytest.importorskip("anndata")
    pytest.importorskip("scanpy")
    import anndata as ad
    import pandas as pd

    # Opt in to writing string arrays (newer pandas hands AnnData a nullable StringArray index).
    if hasattr(ad, "settings") and hasattr(ad.settings, "allow_write_nullable_strings"):
        ad.settings.allow_write_nullable_strings = True

    X, labels, genes, _ = _synthetic()
    adata = ad.AnnData(
        X=X.astype("float32"),
        obs=pd.DataFrame({"celltypes": labels}, index=pd.Index([f"c{i}" for i in range(len(labels))], dtype=object)),
        var=pd.DataFrame(index=pd.Index([str(g) for g in genes], dtype=object)),
    )
    import tempfile

    from skills.proprietary.cepo.run_real import run

    with tempfile.TemporaryDirectory() as d:
        path = f"{d}/tiny.h5ad"
        adata.write_h5ad(path)
        fig = run(path, {"n_genes": 5, "min_cells": 20, "exprs_pct": 0.05, "normalize": False})

    assert fig["data"] and fig["data"][0]["type"] == "scatter"
    assert "table" in fig and fig["table"]["columns"] == ["cell type", "gene", "DS", "detection"]
    # A's steady markers should appear among the plotted genes.
    plotted = set(fig["data"][0]["x"])
    assert any(g.startswith("A_stable") for g in plotted)
