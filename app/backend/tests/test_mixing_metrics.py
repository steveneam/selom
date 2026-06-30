"""Unit tests for the pure mixing-metrics math (numpy/sklearn only — no scanpy).

Validates the clean-room LISI + kBET and the sklearn-backed ARI/NMI/silhouette against
constructed embeddings with KNOWN structure: well-separated batches (poor mixing) vs fully
interleaved batches (good mixing), and clusters that do / don't match labels.
"""

from __future__ import annotations

import numpy as np

from skills.mixing_metrics.metrics import (
    clustering_agreement,
    compute_all,
    compute_lisi,
    kbet_acceptance,
    silhouette_scores,
)


def _separated_batches(n: int = 60, seed: int = 0):
    """Two batches at distant locations → each cell's neighbours are all one batch (poor mixing)."""
    rng = np.random.default_rng(seed)
    a = rng.normal((0.0, 0.0), 0.4, (n, 2))
    b = rng.normal((50.0, 50.0), 0.4, (n, 2))
    emb = np.vstack([a, b])
    batch = np.array(["A"] * n + ["B"] * n)
    return emb, batch


def _mixed_batches(n: int = 120, seed: int = 1):
    """One shared cloud, batch assigned independently of position → neighbours ~50/50 (good mixing)."""
    rng = np.random.default_rng(seed)
    emb = rng.normal((0.0, 0.0), 1.0, (n, 2))
    batch = np.array(["A", "B"] * (n // 2))
    return emb, batch


def test_ilisi_higher_when_mixed():
    sep_emb, sep_b = _separated_batches()
    mix_emb, mix_b = _mixed_batches()
    ilisi_sep = compute_lisi(sep_emb, sep_b, perplexity=15)
    ilisi_mix = compute_lisi(mix_emb, mix_b, perplexity=15)
    assert ilisi_sep < 1.3, ilisi_sep  # neighbours nearly all one batch → ~1
    assert ilisi_mix > 1.6, ilisi_mix  # ~50/50 → approaches 2
    assert ilisi_mix > ilisi_sep


def test_kbet_acceptance_higher_when_mixed():
    sep_emb, sep_b = _separated_batches()
    mix_emb, mix_b = _mixed_batches()
    acc_sep = kbet_acceptance(sep_emb, sep_b, k=20)
    acc_mix = kbet_acceptance(mix_emb, mix_b, k=20)
    assert acc_sep < 0.2, acc_sep  # pure neighbourhoods are rejected
    assert acc_mix > 0.7, acc_mix
    assert acc_mix > acc_sep


def test_asw_batch_higher_when_mixed():
    sep_emb, sep_b = _separated_batches()
    mix_emb, mix_b = _mixed_batches()
    asw_sep, _ = silhouette_scores(sep_emb, sep_b, None)
    asw_mix, _ = silhouette_scores(mix_emb, mix_b, None)
    assert asw_mix > asw_sep
    assert asw_sep < 0.2  # batches well-separated → low mixing score


def test_clisi_near_one_for_separated_labels():
    """cLISI on well-separated cell types ≈ 1 (each cell's neighbours share its type)."""
    emb, labels = _separated_batches()  # the two clouds double as two cell types
    clisi = compute_lisi(emb, labels, perplexity=15)
    assert clisi is not None and clisi < 1.3, clisi


def test_ari_nmi_high_when_clusters_match_labels():
    rng = np.random.default_rng(2)
    blobs = [rng.normal(c, 0.3, (40, 2)) for c in [(0, 0), (20, 0), (0, 20)]]
    emb = np.vstack(blobs)
    labels = np.array([f"t{i}" for i in range(3) for _ in range(40)])
    ari, nmi = clustering_agreement(emb, labels)
    assert ari > 0.95 and nmi > 0.95


def test_ari_near_zero_for_shuffled_labels():
    rng = np.random.default_rng(3)
    emb = rng.normal((0, 0), 1.0, (90, 2))
    labels = rng.integers(0, 3, size=90).astype(str)  # labels independent of position
    ari, _ = clustering_agreement(emb, labels)
    assert ari < 0.2, ari


def test_one_batch_metrics_are_na_not_raising():
    rng = np.random.default_rng(4)
    emb = rng.normal((0, 0), 1.0, (30, 2))
    rows = compute_all(emb, np.array(["only"] * 30), labels=None, perplexity=10, k=10)
    by_key = {r["key"]: r for r in rows}
    for key in ("iLISI", "kBET", "ASW_batch"):
        assert by_key[key]["value"] is None
        assert "≥2 batches" in by_key[key]["note"]


def test_no_labels_marks_label_metrics_na():
    emb, batch = _mixed_batches()
    rows = compute_all(emb, batch, labels=None, perplexity=15, k=20)
    by_key = {r["key"]: r for r in rows}
    for key in ("cLISI", "ARI", "NMI", "ASW_label"):
        assert by_key[key]["value"] is None
        assert "label key" in by_key[key]["note"]
    # batch metrics still computed
    assert by_key["iLISI"]["value"] is not None
    assert by_key["kBET"]["value"] is not None


def test_compute_all_shape_and_determinism():
    emb, batch = _mixed_batches()
    labels = np.array(["x", "y"] * 60)
    a = compute_all(emb, batch, labels=labels, perplexity=15, k=20)
    b = compute_all(emb, batch, labels=labels, perplexity=15, k=20)
    assert [r["key"] for r in a] == ["iLISI", "cLISI", "kBET", "ARI", "NMI", "ASW_batch", "ASW_label"]
    assert all(r["direction"] for r in a)
    assert a == b  # deterministic


def test_metric_type_routes_mixing_metrics_to_integration():
    """The grader must type these as MT_INTEGRATION (engine-sensitive, WIDE magnitude) so a measured
    Melody↔Harmony delta is not mislabelled irreproducible."""
    from reproduction.core import MT_INTEGRATION, infer_metric_type

    # skill_id is the strong signal — covers ARI/NMI/ASW/silhouette whose bare names are too generic.
    for metric in ("iLISI", "ARI", "NMI", "ASW batch", "kBET acceptance", "silhouette"):
        assert infer_metric_type(metric, "mixing_metrics") == MT_INTEGRATION
    # characteristic, UNAMBIGUOUS metric names route even without a skill_id.
    for metric in ("iLISI", "kBET", "batch mixing"):
        assert infer_metric_type(metric) == MT_INTEGRATION
    # generic names must NOT be silently widened without an integration skill id — "silhouette" is a
    # general clustering coefficient (the `cluster` skill emits one); only widen it via skill_id.
    assert infer_metric_type("variance", "pca") != MT_INTEGRATION
    assert infer_metric_type("silhouette") != MT_INTEGRATION  # gauntlet 2026-06-30: no over-widen


def test_mixing_metric_magnitude_collapse_is_not_reproduced():
    """A genuine mixing collapse must FAIL, not pass via a sign-only short-circuit (gauntlet HIGH
    2026-06-30). MT_INTEGRATION grades on MAGNITUDE (direction_close=False): a printed-vs-computed
    gulf fails even though both values are positive."""
    from reproduction.core import CLOSE, EXACT, FAIL, MT_INTEGRATION, Golden, classify_metric, resolve_tolerances

    tol = resolve_tolerances(Golden(metric="kbet", value=0.85, metric_type=MT_INTEGRATION))
    assert tol["direction_close"] is False
    # printed 0.85 vs computed 0.03 (a mixing collapse) → FAIL, NOT reproduced.
    assert classify_metric(0.85, 0.03, **tol)[0] == FAIL
    # a small engine-delta still grades reproduced (the WIDE band tolerates Melody↔Harmony).
    assert classify_metric(0.85, 0.80, **tol)[0] in (EXACT, CLOSE)
