"""Real genes-along-pseudotime engine (scanpy DPT + scipy rank correlation).

Assigns each cell a diffusion pseudotime (reusing ``_scrna.compute_pseudotime``), then
correlates every gene's expression with pseudotime by Spearman's rank correlation,
Benjamini-Hochberg corrects the p-values, and draws the top-N trending genes as mean
expression binned along pseudotime. This is the OSCA ``testPseudotime`` idea: an ordering
is only useful once you know which genes track it.

Caveat (surfaced in the methods text): pseudotime is derived from the same expression, so
these associations characterize the trajectory rather than constituting an independent test.
"""


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import scanpy as sc

    from skills._engine import to_bool
    from skills._genes import read_anndata
    from skills._plotly import jsonable
    from skills._scrna import compute_pseudotime
    from skills._table import table
    from skills.pseudotime_genes.run import _pseudotime_spec

    adata = read_anndata(data_path)
    sc.pp.filter_genes(adata, min_cells=3)
    if to_bool(params.get("normalize", True)):  # skip if input is already normalized
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    pt, root_note = compute_pseudotime(adata, params.get("root", ""), params.get("groupby") or "leiden")
    if not np.isfinite(pt).any() or float(np.nanmax(pt) - np.nanmin(pt)) <= 0:
        raise ValueError("pseudotime is degenerate (no spread) — is the data a single state?")

    genes, rho, pval, padj = _spearman_vs_pseudotime(adata, pt)

    top_n = int(params["top_n"])
    # Significant first (adjusted p), then strongest absolute correlation.
    order = sorted(range(len(genes)), key=lambda i: (padj[i], -abs(rho[i])))[:top_n]

    # Mean log-expression of each top gene per equal-width pseudotime bin -> a smooth curve.
    n_bins = int(params.get("n_bins", 20))
    lo, hi = float(pt.min()), float(pt.max())
    edges = np.linspace(lo, hi, n_bins + 1)
    centers = [round(float((edges[k] + edges[k + 1]) / 2.0), 4) for k in range(n_bins)]
    bin_idx = np.clip(np.digitize(pt, edges[1:-1]), 0, n_bins - 1)

    top_genes = [genes[i] for i in order]
    sub = adata[:, top_genes]
    X = sub.X
    dense = np.asarray(X.todense()) if hasattr(X, "todense") else np.asarray(X)
    series, rows = [], []
    for col, i in enumerate(order):
        vals = dense[:, col].astype(float)
        y = [float(vals[bin_idx == b].mean()) if (bin_idx == b).any() else float("nan") for b in range(n_bins)]
        # forward/back-fill empty bins so the spline stays continuous
        y = _fill_gaps(y)
        series.append({"name": genes[i], "y": y, "rho": rho[i]})
        rows.append([genes[i], round(float(rho[i]), 4), float(f"{pval[i]:.3g}"),
                     float(f"{padj[i]:.3g}"), "up" if rho[i] >= 0 else "down"])

    n_sig = int((padj < 0.05).sum())
    subtitle = (
        f"{root_note} · Spearman gene-vs-pseudotime · {n_sig} genes FDR<0.05 · "
        f"{adata.n_obs} cells · {n_bins} bins"
    )
    spec = _pseudotime_spec(centers, series, f"Genes along pseudotime — top {len(series)}", subtitle)
    spec["table"] = table(
        ["gene", "Spearman rho", "p", "adj p", "trend"], rows,
        "Genes correlated with pseudotime",
    )
    return jsonable(spec)


def _spearman_vs_pseudotime(adata, pt):
    """Per-gene Spearman correlation of expression with pseudotime + BH-adjusted p-values.

    Spearman rho = Pearson on ranks; pseudotime is ranked once and each gene column is
    ranked in chunks so the dense rank matrix stays bounded (the same pattern as the AUC
    marker scorer). p-values use the t approximation; BH gives the adjusted p.
    """
    import numpy as np
    import scipy.sparse as sp
    from scipy.stats import rankdata
    from scipy.stats import t as tdist

    X = adata.X
    genes = [str(g) for g in adata.var_names]
    n = adata.n_obs
    is_sparse = sp.issparse(X)

    ptr = rankdata(pt)
    ptc = ptr - ptr.mean()
    ptn = float(np.sqrt((ptc**2).sum()))

    rho = np.zeros(len(genes))
    chunk = 1000
    for start in range(0, len(genes), chunk):
        sl = slice(start, start + chunk)
        block = X[:, sl]
        block = np.asarray(block.todense(), dtype=float) if is_sparse else np.asarray(block, dtype=float)
        gr = rankdata(block, axis=0)
        grc = gr - gr.mean(axis=0)
        den = np.sqrt((grc**2).sum(axis=0)) * ptn
        num = (grc * ptc[:, None]).sum(axis=0)
        rho[sl] = np.divide(num, den, out=np.zeros_like(den), where=den > 0)

    rho_c = np.clip(rho, -0.999999, 0.999999)
    tstat = rho_c * np.sqrt((n - 2) / (1.0 - rho_c**2))
    pval = 2.0 * tdist.sf(np.abs(tstat), n - 2)
    return genes, rho, pval, _benjamini_hochberg(pval)


def _benjamini_hochberg(pvals):
    """Vectorized Benjamini-Hochberg adjusted p-values (step-up, monotone-enforced)."""
    import numpy as np

    p = np.asarray(pvals, dtype=float)
    n = p.size
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1.0)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(adj, 0.0, 1.0)
    return out


def _fill_gaps(y):
    """Forward- then back-fill empty (NaN) bins so a sparsely-populated curve stays
    continuous; an all-empty curve degrades to zeros."""
    import math

    filled = list(y)
    n = len(filled)
    last = None
    for k in range(n):  # forward-fill interior / trailing gaps
        if math.isnan(filled[k]):
            if last is not None:
                filled[k] = last
        else:
            last = filled[k]
    nxt = None
    for k in range(n - 1, -1, -1):  # back-fill leading gaps
        if math.isnan(filled[k]):
            if nxt is not None:
                filled[k] = nxt
        else:
            nxt = filled[k]
    return [round(float(0.0 if math.isnan(v) else v), 4) for v in filled]
