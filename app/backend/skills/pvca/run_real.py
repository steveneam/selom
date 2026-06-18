"""Real PVCA engine — variance apportionment over the leading principal components.

Reads a samples × (features + factor columns) CSV. The factor columns (named via the
``factors`` param, else auto-detected as the non-numeric columns) are the sources of
variance to apportion; the remaining numeric columns are the expression features.

Method (a library-only PVCA, numpy/pandas only):
  1. z-score the feature matrix (optional) and run PCA via SVD.
  2. retain the leading PCs that together explain ``pct_threshold`` of the variance.
  3. for each retained PC, estimate each factor's variance fraction by one-way ANOVA
     (eta-squared = between-group SS / total SS).
  4. weight each PC's fractions by that PC's share of total variance and sum across PCs;
     the leftover is the unexplained residual.

This is the established lightweight PVCA approximation (ANOVA variance components rather
than a REML mixed model), which is enough to read off the dominant source of variance and
whether batch is large — the Fig 2B question.
"""

from skills.pvca.run import pvca_spec

_MAX_PC = 20      # cap the PCs we decompose over
_MIN_LEVELS = 2   # a factor needs >=2 levels to explain any variance


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd

    df = pd.read_csv(data_path)
    factor_cols, feature_cols = _columns(df, params)
    if not factor_cols:
        raise ValueError("pvca needs at least one categorical factor column")
    if len(feature_cols) < 2:
        raise ValueError("pvca needs at least two numeric feature columns")

    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    X = np.nan_to_num(X, nan=np.nanmean(X) if np.isfinite(np.nanmean(X)) else 0.0)
    X = X - X.mean(axis=0, keepdims=True)
    if _truthy(params.get("normalize", True)):
        sd = X.std(axis=0, keepdims=True)
        X = X / np.where(sd > 0, sd, 1.0)

    scores, var_frac = _pca(X, np)
    keep = _retain(var_frac, float(params.get("pct_threshold", 0.6)))

    factors = {c: df[c].astype(str).to_numpy() for c in factor_cols}
    weighted = {c: 0.0 for c in factor_cols}
    explained = 0.0
    for pc in keep:
        w = float(var_frac[pc])
        for name, labels in factors.items():
            eta = _eta_squared(scores[:, pc], labels, np)
            weighted[name] += w * eta
            explained += w * eta
    total_kept = float(var_frac[keep].sum()) if len(keep) else 0.0
    residual = max(total_kept - explained, 0.0)

    # Renormalize so the bars sum to 1 (the apportionment of the retained variance).
    denom = explained + residual or 1.0
    components = [(name, weighted[name] / denom) for name in factor_cols]
    components.append(("residual", residual / denom))
    return pvca_spec(components, f"PVCA — {len(keep)} PCs, {total_kept * 100:.0f}% of variance")


def _pca(X, np):
    """Return (scores n×k, variance-fraction per component)."""
    u, s, _vt = np.linalg.svd(X, full_matrices=False)
    scores = u * s
    var = s**2
    k = min(_MAX_PC, scores.shape[1])
    return scores[:, :k], (var[:k] / var.sum() if var.sum() else var[:k])


def _retain(var_frac, threshold):
    import numpy as np

    csum = np.cumsum(var_frac)
    n = int(np.searchsorted(csum, threshold) + 1)
    return list(range(min(n, len(var_frac))))


def _eta_squared(y, labels, np):
    """One-way ANOVA eta-squared: fraction of y's variance explained by the grouping."""
    grand = y.mean()
    ss_total = float(((y - grand) ** 2).sum()) or 1.0
    ss_between = 0.0
    levels = 0
    for lvl in set(labels):
        yi = y[labels == lvl]
        if yi.size:
            levels += 1
            ss_between += yi.size * (yi.mean() - grand) ** 2
    if levels < _MIN_LEVELS:
        return 0.0
    return float(min(max(ss_between / ss_total, 0.0), 1.0))


def _columns(df, params):
    import pandas as pd

    explicit = [c.strip() for c in str(params.get("factors") or "").split(",") if c.strip()]
    cols = {c.lower(): c for c in df.columns}
    if explicit:
        factor_cols = [cols[c.lower()] for c in explicit if c.lower() in cols]
    else:
        factor_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    feature_cols = [c for c in df.columns if c not in factor_cols
                    and pd.api.types.is_numeric_dtype(df[c])]
    return factor_cols, feature_cols


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on") if not isinstance(v, bool) else v
