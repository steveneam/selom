"""Integration mixing metrics — pure numpy / scikit-learn (no scanpy / anndata import).

The graded scIB-standard suite computed from an embedding + a batch/label vector:
iLISI · cLISI · kBET · ARI · NMI · ASW_batch · ASW_label. Kept dependency-light and
scanpy-free so it unit-tests in the fast gate; ``run_real`` reads the AnnData and calls
``compute_all``.

License posture ([[license-decision-framework]], mirrors Selom Melody):
- ARI / NMI / silhouette come from scikit-learn (BSD-3).
- **LISI and kBET are clean-room reimplementations from the published definitions** — the
  canonical implementations (harmonypy ``compute_lisi``; the R ``kBET`` package) are GPL
  lineage and are NOT used. LISI is the perplexity-calibrated inverse-Simpson diversity of a
  cell's kNN neighbourhood (the t-SNE entropy calibration + Simpson's index, both textbook);
  kBET is a per-neighbourhood χ² of local vs global batch frequency (Büttner et al. 2019).
"""

from __future__ import annotations

import numpy as np


def _codes(labels) -> tuple[np.ndarray, int]:
    """Integer codes 0..C-1 for an arbitrary (e.g. string) label vector + the class count."""
    _, inv = np.unique(np.asarray(labels), return_inverse=True)
    return inv.astype(np.intp), int(inv.max()) + 1 if len(inv) else 0


def _calibrate_weights(d_row: np.ndarray, perplexity: float, *, tol: float = 1e-5, max_iter: int = 50) -> np.ndarray:
    """Neighbour weights whose distribution has the target ``perplexity`` (t-SNE Hbeta search).

    Binary-searches the precision ``beta`` (= 1/2σ²) so the Shannon entropy of the Gaussian
    kernel weights ``exp(-d·beta)`` equals ``log(perplexity)``; returns the normalised weights.
    """
    target = np.log(perplexity)
    beta, lo, hi = 1.0, -np.inf, np.inf
    p = np.full(d_row.shape, 1.0 / max(len(d_row), 1))
    for _ in range(max_iter):
        w = np.exp(-d_row * beta)
        sum_w = w.sum()
        if sum_w <= 0 or not np.isfinite(sum_w):
            return np.full(d_row.shape, 1.0 / max(len(d_row), 1))
        entropy = np.log(sum_w) + beta * float((d_row * w).sum()) / sum_w
        p = w / sum_w
        diff = entropy - target
        if abs(diff) < tol:
            break
        if diff > 0:  # entropy too high → sharpen (raise beta)
            lo = beta
            beta = beta * 2.0 if hi == np.inf else (beta + hi) / 2.0
        else:
            hi = beta
            beta = beta / 2.0 if lo == -np.inf else (beta + lo) / 2.0
    return p


def compute_lisi(embedding: np.ndarray, labels, perplexity: float = 30.0) -> float | None:
    """Mean Local Inverse Simpson's Index over cells (clean-room).

    For each cell: take ``~3·perplexity`` nearest neighbours, weight them by a Gaussian kernel
    calibrated to ``perplexity``, accumulate weight per label, and take the inverse Simpson index
    ``1/Σ p_l²`` — the effective number of labels in the neighbourhood. Range ``[1, n_labels]``:
    high on batch labels = well mixed (iLISI); low on cell-type labels = well separated (cLISI).
    Returns ``None`` when there are <2 labels or <3 cells.
    """
    from sklearn.neighbors import NearestNeighbors

    emb = np.asarray(embedding, dtype=np.float64)
    codes, n_lab = _codes(labels)
    n = emb.shape[0]
    if n_lab < 2 or n < 3:
        return None
    perp = float(max(2.0, min(perplexity, (n - 1) / 3.0)))
    k = int(min(max(3 * perp, 3), n - 1))
    nn = NearestNeighbors(n_neighbors=k + 1).fit(emb)
    dist, idx = nn.kneighbors(emb)
    dist, idx = dist[:, 1:], idx[:, 1:]  # drop self
    total = 0.0
    for i in range(n):
        p = _calibrate_weights(dist[i], perp)
        neigh_codes = codes[idx[i]]
        prob = np.bincount(neigh_codes, weights=p, minlength=n_lab)
        simpson = float((prob * prob).sum())
        total += (1.0 / simpson) if simpson > 0 else 1.0
    return total / n


def kbet_acceptance(
    embedding: np.ndarray,
    batch,
    *,
    k: int = 30,
    n_repeat: int = 100,
    alpha: float = 0.05,
    seed: int = 0,
) -> float | None:
    """kBET acceptance rate over sampled neighbourhoods (clean-room, Büttner et al. 2019).

    For each sampled cell, compare its k-neighbourhood's batch counts to the global batch
    frequencies with a χ² test (``df = n_batch-1``); a neighbourhood is *accepted* when
    ``p >= alpha`` (its composition is consistent with the global mix). Returns the acceptance
    fraction — higher = better mixing. ``None`` for <2 batches or <3 cells.
    """
    from scipy.stats import chi2
    from sklearn.neighbors import NearestNeighbors

    emb = np.asarray(embedding, dtype=np.float64)
    codes, n_batch = _codes(batch)
    n = emb.shape[0]
    if n_batch < 2 or n < 3:
        return None
    kk = int(min(max(k, n_batch), n - 1))
    global_freq = np.bincount(codes, minlength=n_batch) / n
    expected = global_freq * kk
    # Guard: a batch with zero global mass would divide by zero; such codes can't occur
    # (every code has >=1 member), so expected > 0 for all present batches.
    nn = NearestNeighbors(n_neighbors=kk + 1).fit(emb)
    rng = np.random.default_rng(seed)
    m = int(min(n_repeat, n)) if n_repeat else n
    sample = rng.choice(n, size=m, replace=False) if m < n else np.arange(n)
    _, idx = nn.kneighbors(emb[sample])
    idx = idx[:, 1:]  # drop self
    df = n_batch - 1
    accepted = 0
    for row in idx:
        observed = np.bincount(codes[row], minlength=n_batch)
        stat = float(((observed - expected) ** 2 / expected).sum())
        if chi2.sf(stat, df) >= alpha:
            accepted += 1
    return accepted / len(idx)


def clustering_agreement(embedding: np.ndarray, labels) -> tuple[float | None, float | None]:
    """(ARI, NMI) of a KMeans(k = #labels) clustering of the embedding vs the ground-truth labels."""
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

    emb = np.asarray(embedding, dtype=np.float64)
    codes, n_lab = _codes(labels)
    n = emb.shape[0]
    if n_lab < 2 or n < n_lab:
        return None, None
    pred = KMeans(n_clusters=n_lab, random_state=0, n_init=10).fit_predict(emb)
    return (
        float(adjusted_rand_score(codes, pred)),
        float(normalized_mutual_info_score(codes, pred)),
    )


def silhouette_scores(embedding: np.ndarray, batch, labels) -> tuple[float | None, float | None]:
    """(ASW_batch, ASW_label), each rescaled to [0,1]; ``None`` when its label set is unusable.

    ``ASW_label = (silhouette(labels)+1)/2`` (higher = better cell-type separation);
    ``ASW_batch = 1 - (silhouette(batch)+1)/2`` (higher = better batch mixing).
    """
    from sklearn.metrics import silhouette_score

    emb = np.asarray(embedding, dtype=np.float64)

    def _asw(group) -> float | None:
        codes, n_g = _codes(group)
        if n_g < 2 or n_g >= emb.shape[0]:
            return None
        return float(silhouette_score(emb, codes))

    asw_b = _asw(batch) if batch is not None else None
    asw_l = _asw(labels) if labels is not None else None
    return (
        (1.0 - (asw_b + 1.0) / 2.0) if asw_b is not None else None,
        ((asw_l + 1.0) / 2.0) if asw_l is not None else None,
    )


# Ordered metric descriptors. direction is shown in the table so each row reads on its own.
_DIRS = {
    "iLISI": "↑ mixing",
    "cLISI": "↓ separation",
    "kBET": "↑ mixing",
    "ARI": "↑ agreement",
    "NMI": "↑ agreement",
    "ASW_batch": "↑ mixing",
    "ASW_label": "↑ separation",
}
_LABELS = {
    "iLISI": "iLISI (batch)",
    "cLISI": "cLISI (label)",
    "kBET": "kBET acceptance",
    "ARI": "ARI",
    "NMI": "NMI",
    "ASW_batch": "ASW batch",
    "ASW_label": "ASW label",
}


def compute_all(
    embedding: np.ndarray,
    batch,
    labels=None,
    *,
    perplexity: float = 30.0,
    k: int = 30,
) -> list[dict]:
    """Compute the full suite, returning ordered rows ``{key,label,value,direction,note}``.

    Batch-only metrics (iLISI, kBET, ASW_batch) need a batch vector with ≥2 levels; label-dependent
    ones (cLISI, ARI, NMI, ASW_label) compute only when ``labels`` is given. A metric that can't be
    computed gets ``value=None`` (rendered "N/A") + a note — the skill never raises.
    """
    emb = np.asarray(embedding, dtype=np.float64)
    _, n_batch = _codes(batch) if batch is not None else (None, 0)
    one_batch = n_batch < 2

    ari, nmi = clustering_agreement(emb, labels) if labels is not None else (None, None)
    asw_batch, asw_label = silhouette_scores(emb, batch, labels)

    raw = {
        "iLISI": (None if one_batch else compute_lisi(emb, batch, perplexity)),
        "cLISI": (compute_lisi(emb, labels, perplexity) if labels is not None else None),
        "kBET": (None if one_batch else kbet_acceptance(emb, batch, k=k)),
        "ARI": ari,
        "NMI": nmi,
        "ASW_batch": asw_batch,
        "ASW_label": asw_label,
    }

    rows: list[dict] = []
    for key in ("iLISI", "cLISI", "kBET", "ARI", "NMI", "ASW_batch", "ASW_label"):
        value = raw[key]
        note = ""
        if value is None:
            if key in ("iLISI", "kBET", "ASW_batch") and one_batch:
                note = "needs ≥2 batches"
            elif key in ("cLISI", "ARI", "NMI", "ASW_label"):
                note = "needs a label key"
        rows.append(
            {
                "key": key,
                "label": _LABELS[key],
                "value": (round(value, 4) if value is not None else None),
                "direction": _DIRS[key],
                "note": note,
            }
        )
    return rows
