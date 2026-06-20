"""Real proteomics differential-abundance engine.

Reads an intensity matrix (proteins x samples; first column = protein/gene id),
log2-transforms and median-normalizes the samples, filters proteins that are too
sparse, fills residual missing values per the chosen ``missing`` strategy, then runs a
per-protein Welch or empirical-Bayes moderated t-test (unequal variance) between two
sample groups with Benjamini-Hochberg FDR. Emits the same volcano spec as the
``volcano`` skill via its ``_assemble``. Stats are proteomics-native (log-intensity),
so this is distinct from the count-based ``deg`` skill while sharing the figure.

Missing-value handling (``missing``): proteomics dropouts are mostly MNAR (below the
run's detection limit), so the default per-protein **mean** impute biases real
fold-changes toward zero. ``mindet`` / ``minprob`` instead fill from each sample's low
(detection-limit) tail — the Perseus/limma-recommended left-censored treatment — which
preserves true MNAR effects. Defaults to ``mean`` so verified outputs stay unchanged.
"""

import re

from skills._engine import to_bool
from skills.volcano.run import _assemble


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd
    from scipy import stats

    df = pd.read_csv(data_path)
    id_col = df.columns[0]
    genes = df[id_col].astype(str)
    mat = df.drop(columns=[id_col]).apply(pd.to_numeric, errors="coerce")
    samples = list(mat.columns)

    cols_a, cols_b = _split_groups(samples, str(params.get("group_a", "")), str(params.get("group_b", "")))
    if not cols_a or not cols_b:
        raise ValueError(
            "proteomics_de needs two sample groups — set group_a / group_b to sample-name substrings"
        )

    X = mat.to_numpy(dtype=float)
    if not to_bool(params.get("log_input", False)):
        X = np.log2(X + 1.0)
    # median-normalize each sample (column) to a common median
    col_med = np.nanmedian(X, axis=0)
    X = X - col_med + np.nanmedian(col_med)

    ai = [samples.index(c) for c in cols_a]
    bi = [samples.index(c) for c in cols_b]
    A, B = X[:, ai], X[:, bi]

    min_valid = float(params.get("min_valid", 0.5))
    keep = (np.isfinite(A).mean(axis=1) >= min_valid) & (np.isfinite(B).mean(axis=1) >= min_valid)

    # fill residual dropouts per the chosen strategy (mean = default; mindet/minprob = MNAR-aware)
    miss_mode = str(params.get("missing") or "mean").lower()
    A, B = _impute(A, miss_mode, np), _impute(B, miss_mode, np)

    mode = str(params.get("stats") or "welch").lower()
    if mode == "moderated":
        lfc, pvals = _moderated_stats(A, B)
    else:
        lfc = np.nanmean(A, axis=1) - np.nanmean(B, axis=1)
        with np.errstate(all="ignore"):
            _, pvals = stats.ttest_ind(A, B, axis=1, equal_var=False)
        pvals = np.where(np.isfinite(pvals), pvals, 1.0)
    padj = _bh(pvals, np)
    nlp = -np.log10(np.clip(padj, 1e-300, 1.0))

    fc_t = float(params.get("fc_threshold", 1.0))
    fdr_t = float(params.get("fdr_threshold", 0.05))
    top_n = int(params.get("top_n", 10))
    y_cut = -np.log10(fdr_t) if fdr_t > 0 else 0.0

    idx = np.where(keep & np.isfinite(lfc) & np.isfinite(nlp))[0]
    up, down, ns = ([], []), ([], []), ([], [])
    for i in idx:
        x, y = round(float(lfc[i]), 4), round(float(nlp[i]), 4)
        bucket = up if (x >= fc_t and y >= y_cut) else down if (x <= -fc_t and y >= y_cut) else ns
        bucket[0].append(x)
        bucket[1].append(y)

    labels = []
    if top_n > 0:
        sig = idx[(np.abs(lfc[idx]) >= fc_t) & (nlp[idx] >= y_cut)]
        order = sig[np.argsort(nlp[sig])[::-1]][:top_n]
        labels = [(round(float(lfc[i]), 4), round(float(nlp[i]), 4), str(genes.iloc[i])) for i in order]

    stat_label = "moderated t" if mode == "moderated" else "Welch t"
    imp_label = "" if miss_mode == "mean" else f", {miss_mode} impute"
    title = (
        f"Proteomics differential abundance — {len(cols_a)}v{len(cols_b)} samples, "
        f"{int(keep.sum())} proteins ({stat_label}{imp_label})"
    )
    return _assemble(up, down, ns, labels, fc_t, y_cut, title)


def _impute(M, mode, np):
    """Fill missing (NaN) intensities per the chosen strategy.

    - ``mean`` (default): per-protein (row) group mean. Simple, but biases MNAR dropouts
      toward the observed mean, shrinking real fold-changes (the limma/Perseus caution).
    - ``mindet``: per-sample (column) deterministic left-censored — fill with the low (1%)
      quantile of that sample's observed intensities, a detection-limit proxy.
    - ``minprob``: per-sample downshifted-normal draw (Perseus: mean-1.8*sd, width 0.3*sd),
      seeded so the run is reproducible.

    Left-censored modes operate per sample (column) because MNAR is a per-run detection
    limit, independent of group. ``mean`` reproduces the prior behaviour exactly.
    """
    mode = (mode or "mean").lower()
    M = M.copy()
    if mode == "mean":
        means = np.nanmean(M, axis=1)
        bad = np.where(~np.isfinite(M))
        M[bad] = np.take(means, bad[0])
        return M

    rng = np.random.default_rng(0) if mode == "minprob" else None
    for j in range(M.shape[1]):
        col = M[:, j]
        miss = ~np.isfinite(col)
        if not miss.any():
            continue
        obs = col[~miss]
        if obs.size == 0:
            continue  # whole sample missing -> leave as NaN (filtered downstream)
        if mode == "mindet":
            col[miss] = float(np.quantile(obs, 0.01))
        else:  # minprob
            sd = float(obs.std())
            sd = sd if sd > 0 else 1e-6
            col[miss] = rng.normal(float(obs.mean()) - 1.8 * sd, 0.3 * sd, size=int(miss.sum()))
    return M


def _moderated_stats(A, B):
    """limma-style empirical-Bayes moderated t-test (Smyth, 2004) for a two-group contrast.

    Returns ``(lfc, pvals)``. The pooled within-group variance of each protein is shrunk
    toward a global prior estimated by method-of-moments from the variance distribution
    across all proteins (Smyth's fitFDist). This stabilizes the per-protein variance and
    recovers more true effects than an un-moderated t-test at small sample sizes. numpy +
    scipy only (no R, no statsmodels) — keeps the skill on the core stack (ADR 0002).
    """
    import numpy as np
    from scipy.special import digamma, polygamma
    from scipy.stats import t as tdist

    na, nb = A.shape[1], B.shape[1]
    d = na + nb - 2  # residual df of the two-group linear model
    mean_a, mean_b = A.mean(axis=1), B.mean(axis=1)
    lfc = mean_a - mean_b
    ss = ((A - mean_a[:, None]) ** 2).sum(axis=1) + ((B - mean_b[:, None]) ** 2).sum(axis=1)
    s2 = ss / d if d > 0 else np.full(A.shape[0], np.nan)

    s2_pos = s2[np.isfinite(s2) & (s2 > 0)]
    if d <= 0 or s2_pos.size < 2:  # cannot estimate a prior -> fall back to ordinary t
        s2_tilde = s2
        df_total = np.full(A.shape[0], float(max(d, 1)))
    else:
        # fitFDist: estimate prior df (d0) and prior variance (s0^2) from the s2 distribution
        e = np.log(s2_pos) - digamma(d / 2.0) + np.log(d / 2.0)
        e_mean = float(e.mean())
        e_var = float(e.var(ddof=1)) - float(polygamma(1, d / 2.0))
        if e_var <= 0:  # between-protein variance within sampling noise -> full shrinkage
            s0_2 = float(np.exp(e_mean))
            s2_tilde = np.full_like(s2, s0_2)
            df_total = np.full(A.shape[0], 1e6)
        else:
            d0 = 2.0 * _trigamma_inverse(e_var)
            s0_2 = float(np.exp(e_mean + digamma(d0 / 2.0) - np.log(d0 / 2.0)))
            s2_tilde = (d0 * s0_2 + d * s2) / (d0 + d)
            df_total = np.full(A.shape[0], d + d0)

    se = np.sqrt(s2_tilde * (1.0 / na + 1.0 / nb))
    with np.errstate(all="ignore"):
        tvals = lfc / se
        pvals = 2.0 * tdist.sf(np.abs(tvals), df_total)
    pvals = np.where(np.isfinite(pvals), pvals, 1.0)
    return lfc, pvals


def _trigamma_inverse(x):
    """Solve trigamma(y) = x for y > 0 by Newton's method (Smyth's trigammaInverse)."""
    from scipy.special import polygamma

    y = 0.5 + 1.0 / x
    for _ in range(50):
        tri = polygamma(1, y)
        dif = tri * (1.0 - tri / x) / polygamma(2, y)
        y = y + dif
        if abs(dif / y) < 1e-8:
            break
    return y


def _bh(p, np):
    """Benjamini-Hochberg FDR (no statsmodels dep — keeps this on the core stack)."""
    p = np.asarray(p, dtype=float)
    n = p.size
    order = np.argsort(p)
    ranked = p[order] * n / np.arange(1, n + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(ranked, 0.0, 1.0)
    return out


def _split_groups(samples, a_key, b_key):
    """Two sample groups: explicit substrings if given, else inferred by name prefix."""
    import collections

    a_key, b_key = a_key.strip(), b_key.strip()
    if a_key and b_key:
        return ([s for s in samples if a_key.lower() in str(s).lower()],
                [s for s in samples if b_key.lower() in str(s).lower()])
    pref = {}
    for s in samples:
        m = re.match(r"^([A-Za-z]+)", str(s))
        pref[s] = m.group(1).lower() if m else str(s)
    top = [p for p, _ in collections.Counter(pref.values()).most_common(2)]
    if len(top) < 2:
        return [], []
    return ([s for s in samples if pref[s] == top[0]], [s for s in samples if pref[s] == top[1]])
