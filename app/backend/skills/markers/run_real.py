"""Real marker-dotplot engine (scanpy).

Ranks markers per cluster, takes the top-N per group, then computes the two dotplot
encodings directly from the (log1p) matrix: per-(gene, group) **mean expression** and
**fraction of cells expressing** (>0). Groups are ordered by hierarchical clustering of
their expression profiles (correlation distance, average linkage) so related clusters sit
together — the standard dendrogram-ordered dotplot. Emits the same wire shape as the stub
via the shared ``_dotplot_spec``.
"""


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd
    import scanpy as sc

    from skills._engine import to_bool
    from skills._plotly import jsonable
    from skills.markers.run import _dotplot_spec

    from skills._genes import read_anndata

    adata = read_anndata(data_path)
    sc.pp.filter_genes(adata, min_cells=3)
    if to_bool(params.get("normalize", True)):  # skip if input is already normalized
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    groupby = params.get("groupby") or "leiden"
    if groupby not in adata.obs.columns:
        n_pcs = max(2, min(50, adata.n_obs - 1, adata.n_vars - 1))
        sc.pp.pca(adata, n_comps=n_pcs)
        sc.pp.neighbors(adata, n_neighbors=15, n_pcs=n_pcs)
        sc.tl.leiden(adata, flavor="igraph", n_iterations=2, directed=False)
        groupby = "leiden"
    # rank_genes_groups needs a categorical grouping (a user-supplied label column may be object).
    adata.obs[groupby] = adata.obs[groupby].astype("category")

    n_genes = int(params["n_genes"])
    rank_by = str(params.get("rank_by") or "wilcoxon").strip().lower()
    method = params.get("method") or "wilcoxon"

    # Selection: by an effect size (OSCA scoreMarkers — honest, rankable) or by the
    # classic Wilcoxon p-value (the default; note cluster p-values are circular).
    selection: list[tuple[str, str, float]] = []  # (group, gene, effect) for the stats table
    if rank_by in ("cohens_d", "cohen", "cohens", "d", "auc"):
        metric = "auc" if rank_by == "auc" else "cohens_d"
        effects = _effect_sizes(adata, groupby, metric)            # groups x genes
        groups = [str(g) for g in effects.index]
        genes = []
        for g in groups:
            top = effects.loc[g].sort_values(ascending=False).head(n_genes)
            for gene, val in top.items():
                selection.append((str(g), str(gene), float(val)))
                if str(gene) not in genes:
                    genes.append(str(gene))
        rank_label = {"auc": "AUC", "cohens_d": "Cohen's d"}[metric]
    else:
        metric = None
        sc.tl.rank_genes_groups(
            adata, groupby, method=method, pts=True, tie_correct=(method == "wilcoxon")
        )
        names = adata.uns["rank_genes_groups"]["names"]
        groups = list(names.dtype.names)
        # Top-N markers per group, in group order, de-duplicated (a gene can rank in two).
        genes = []
        for g in groups:
            for i in range(min(n_genes, len(names[g]))):
                sym = str(names[g][i])
                if sym in adata.var_names and sym not in genes:
                    genes.append(sym)
        rank_label = method
    if not genes:
        raise ValueError("no marker genes found — is the input clustered and non-empty?")

    # Per-(gene, group) mean expression and fraction expressing, from the log1p matrix.
    sub = adata[:, genes]
    X = sub.X
    dense = np.asarray(X.todense()) if hasattr(X, "todense") else np.asarray(X)
    expr = pd.DataFrame(dense, columns=genes)
    grp = sub.obs[groupby].astype(str).to_numpy()
    expr["__g"] = grp
    means = expr.groupby("__g")[genes].mean()                 # groups x genes
    fracs = expr.assign(**{g: (expr[g] > 0) for g in genes}).groupby("__g")[genes].mean()

    if to_bool(params.get("standard_scale", True)):
        # Scale each gene's mean across groups to [0, 1] so genes are comparable by colour.
        lo = means.min(axis=0)
        rng = (means.max(axis=0) - lo).replace(0, 1.0)
        means = (means - lo) / rng

    group_order = _dendrogram_order(means)                     # cluster related groups
    means, fracs = means.loc[group_order], fracs.loc[group_order]

    xs: list[str] = []
    ys: list[str] = []
    color: list[float] = []
    size: list[float] = []
    frac_vals: list[float] = []
    for group in group_order:
        for gene in genes:
            m = float(means.loc[group, gene])
            f = float(fracs.loc[group, gene])
            xs.append(gene)
            ys.append(str(group))
            color.append(round(m, 4))
            size.append(round(4.0 + f * 22.0, 4))
            frac_vals.append(round(f, 4))

    scale_note = "scaled mean" if to_bool(params.get("standard_scale", True)) else "mean expr (log1p)"
    spec = _dotplot_spec(
        xs, ys, color, size, frac_vals, genes, [str(g) for g in group_order],
        title=f"Marker genes — top {n_genes} per {groupby} ({rank_label})",
    )
    spec["data"][0]["marker"]["colorbar"]["title"]["text"] = scale_note

    # Pillar-1 Statistics table for the effect-size modes — the metric each gene was
    # ranked by, per cluster (one-vs-rest), strongest first within each cluster.
    if metric is not None and selection:
        from skills._table import table

        rows = [
            [g, gene, round(val, 4), round(float(fracs.loc[g, gene]), 4)]
            for g, gene, val in selection
            if g in fracs.index and gene in fracs.columns
        ]
        spec["table"] = table(
            ["cluster", "gene", rank_label, "frac expressing"],
            rows,
            f"Marker effect sizes ({rank_label}, one-vs-rest)",
        )
    return jsonable(spec)


def _effect_sizes(adata, groupby, metric):
    """One-vs-rest marker effect sizes per (group, gene): Cohen's d or Mann-Whitney AUC.

    OSCA's ``scoreMarkers`` ranks markers by effect size rather than by a p-value, because
    p-values from data-derived clusters are circular (the clusters were defined from the
    same expression). ``cohens_d`` = the standardized mean difference (group vs the rest,
    pooled SD); ``auc`` = P(expression in group > expression in the rest), recovered from
    the rank-sum (Mann-Whitney U / n_group·n_rest), so >0.5 means up-regulated in the group.
    Returns a (groups x genes) DataFrame. Computed on the (log-normalized) ``adata.X``;
    AUC is rank-based so it is invariant to that transform.
    """
    import numpy as np
    import pandas as pd
    import scipy.sparse as sp

    X = adata.X
    genes = [str(g) for g in adata.var_names]
    grp = adata.obs[groupby].astype(str).to_numpy()
    order = list(dict.fromkeys(grp.tolist()))
    masks = {g: (grp == g) for g in order}
    ng = {g: int(masks[g].sum()) for g in order}
    n_total = adata.n_obs
    is_sparse = sp.issparse(X)

    if metric == "cohens_d":
        sums, sqs = {}, {}
        for g in order:
            sub = X[masks[g]]
            if is_sparse:
                sums[g] = np.asarray(sub.sum(axis=0)).ravel()
                sqs[g] = np.asarray(sub.multiply(sub).sum(axis=0)).ravel()
            else:
                sub = np.asarray(sub, dtype=float)
                sums[g] = sub.sum(axis=0)
                sqs[g] = (sub * sub).sum(axis=0)
        total_s = np.sum(list(sums.values()), axis=0)
        total_sq = np.sum(list(sqs.values()), axis=0)
        out = {}
        for g in order:
            n1, n2 = ng[g], n_total - ng[g]
            if n1 < 1 or n2 < 1:
                out[g] = np.zeros(len(genes))
                continue
            m1 = sums[g] / n1
            m2 = (total_s - sums[g]) / n2
            v1 = np.maximum(sqs[g] / n1 - m1**2, 0.0) * (n1 / max(n1 - 1, 1))
            v2 = np.maximum((total_sq - sqs[g]) / n2 - m2**2, 0.0) * (n2 / max(n2 - 1, 1))
            pooled = np.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / max(n1 + n2 - 2, 1))
            d = np.divide(m1 - m2, pooled, out=np.zeros_like(pooled), where=pooled > 0)
            out[g] = d
        return pd.DataFrame(out, index=genes).T

    # AUC — chunk over genes so the dense rank matrix stays bounded (a full densify of a
    # big sparse matrix would blow memory). One full-column ranking serves every group,
    # since group-vs-rest shares the same union of all cells.
    from scipy.stats import rankdata

    out = {g: np.zeros(len(genes)) for g in order}
    chunk = 1000
    for start in range(0, len(genes), chunk):
        sl = slice(start, start + chunk)
        block = X[:, sl]
        block = np.asarray(block.todense(), dtype=float) if is_sparse else np.asarray(block, dtype=float)
        ranks = rankdata(block, axis=0)  # average ranks for ties
        for g in order:
            n1, n2 = ng[g], n_total - ng[g]
            if n1 >= 1 and n2 >= 1:
                rg = ranks[masks[g]].sum(axis=0)
                out[g][sl] = (rg - n1 * (n1 + 1) / 2.0) / (n1 * n2)
            else:
                out[g][sl] = 0.5
    return pd.DataFrame(out, index=genes).T


def _dendrogram_order(means):
    """Leaf order of the groups from hierarchical clustering of their expression
    profiles (correlation distance, average linkage). No-ops for <3 groups; falls back
    to euclidean when correlation is undefined (a constant profile)."""
    import numpy as np

    labels = list(means.index)
    if len(labels) < 3:
        return labels

    from scipy.cluster.hierarchy import leaves_list, linkage
    from scipy.spatial.distance import pdist

    values = means.to_numpy(dtype=float)
    dist = pdist(values, metric="correlation")
    if not np.all(np.isfinite(dist)):
        dist = pdist(values, metric="euclidean")
    order = leaves_list(linkage(dist, method="average"))
    return [labels[i] for i in order]
