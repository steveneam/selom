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

    method = params.get("method") or "wilcoxon"
    sc.tl.rank_genes_groups(
        adata, groupby, method=method, pts=True, tie_correct=(method == "wilcoxon")
    )
    names = adata.uns["rank_genes_groups"]["names"]
    groups = list(names.dtype.names)

    # Top-N markers per group, in group order, de-duplicated (a gene can rank in two).
    n_genes = int(params["n_genes"])
    genes: list[str] = []
    for g in groups:
        for i in range(min(n_genes, len(names[g]))):
            sym = str(names[g][i])
            if sym in adata.var_names and sym not in genes:
                genes.append(sym)
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
        title=f"Marker genes — top {n_genes} per {groupby} ({method})",
    )
    spec["data"][0]["marker"]["colorbar"]["title"]["text"] = scale_note
    return jsonable(spec)


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
