"""Real expression-heatmap engine — scRNA (scanpy) or bulk CSV (pandas).

scRNA: rank markers per cluster, take the top few per group, show mean log1p
expression per cluster, z-scored per gene. Bulk CSV (genes x samples): take the
top-variance genes, z-scored per gene. Both feed ``run.heatmap_spec``.
"""

from skills.heatmap.run import heatmap_spec
from skills._plotly import jsonable


def run(data_path: str, params: dict) -> dict:
    if str(data_path).lower().endswith((".h5ad", ".h5")):
        return _scrna(data_path, params)
    return _bulk(data_path, params)


def _scrna(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd
    import scanpy as sc

    n_genes = int(params["n_genes"])
    from skills._genes import read_anndata

    adata = read_anndata(data_path)
    sc.pp.filter_genes(adata, min_cells=3)
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)

    groupby = params.get("groupby") or "leiden"
    if groupby not in adata.obs.columns:
        n_pcs = max(2, min(50, adata.n_obs - 1, adata.n_vars - 1))
        sc.pp.pca(adata, n_comps=n_pcs)
        sc.pp.neighbors(adata, n_neighbors=15, n_pcs=n_pcs)
        sc.tl.leiden(adata, flavor="igraph", n_iterations=2, directed=False)
        groupby = "leiden"

    sc.tl.rank_genes_groups(adata, groupby, method="wilcoxon")
    names = adata.uns["rank_genes_groups"]["names"]
    groups = list(names.dtype.names)
    per = max(1, n_genes // len(groups))
    genes: list[str] = []
    for g in groups:
        for i in range(per):
            sym = str(names[g][i])
            if sym not in genes:
                genes.append(sym)
    genes = genes[:n_genes]

    sub = adata[:, genes]
    X = sub.X
    dense = np.asarray(X.todense()) if hasattr(X, "todense") else np.asarray(X)
    expr = pd.DataFrame(dense, columns=genes)
    expr["__g"] = sub.obs[groupby].astype(str).to_numpy()
    means = expr.groupby("__g")[genes].mean().T  # genes x groups
    z = _row_zscore(means, np)
    z, genes, xlabels, row_dendro, col_dendro = _cluster(z, genes, list(means.columns), params)
    return jsonable(
        heatmap_spec(z.tolist(), xlabels, genes, "Marker heatmap", "cluster", row_dendro, col_dendro)
    )


def _bulk(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd

    n_genes = int(params["n_genes"])
    df = pd.read_csv(data_path, index_col=0)
    top = df.var(axis=1).sort_values(ascending=False).head(n_genes).index
    sub = df.loc[top]
    z = _row_zscore(sub, np)
    ylabels0 = [str(g) for g in sub.index]
    z, ylabels, xlabels, row_dendro, col_dendro = _cluster(z, ylabels0, list(sub.columns), params)
    return jsonable(
        heatmap_spec(z.tolist(), xlabels, ylabels, "Top-variable genes", "sample", row_dendro, col_dendro)
    )


def _row_zscore(frame, np):
    """Per-row z-score (rounded), with zero-variance rows left at 0."""
    values = frame.to_numpy(dtype=float)
    mean = values.mean(axis=1, keepdims=True)
    std = values.std(axis=1, keepdims=True)
    std[std == 0] = 1.0
    return np.round((values - mean) / std, 4)


_CLUSTER_OPTIONS = ("none", "row", "column", "both")


def _resolve_cluster(params) -> str:
    """The clustering mode ∈ {none, row, column, both} from the ``cluster`` param (default none)."""
    val = str(params.get("cluster") or "none").lower()
    return val if val in _CLUSTER_OPTIONS else "none"


def _cluster(z, ylabels, xlabels, params):
    """Apply the resolved clustering mode to a genes×samples z-matrix.

    Rows (genes) are ALWAYS reordered into hierarchical-clustering leaf order — the standard
    *clustered* heatmap baseline — regardless of mode; the mode only governs which dendrogram
    TREES are drawn and whether the COLUMNS are also reordered. ``row``/``both`` draw the row
    tree; ``column``/``both`` cluster + reorder the samples and draw the column tree (needs ≥3
    samples, else it no-ops gracefully). Returns ``(z, ylabels, xlabels, row_dendro, col_dendro)``.
    """
    mode = _resolve_cluster(params)
    want_row_tree = mode in ("row", "both")
    want_cols = mode in ("column", "both")

    z, ylabels, row_dendro = _order_rows(z, ylabels, want_row_tree)
    col_dendro = None
    if want_cols:
        # Cluster samples by transposing: rows-of-the-transpose ARE the columns. Distances over
        # columns are invariant to the row permutation above, so order of operations is safe.
        zt, xlabels, col_dendro = _order_rows(z.T, xlabels, True, orientation="top")
        z = zt.T
    return z, ylabels, xlabels, row_dendro, col_dendro


def _order_rows(z, labels, want_dendro=False, orientation="left"):
    """Reorder rows by hierarchical-clustering leaf order so co-varying genes sit
    together — the standard *clustered* heatmap layout (vs. raw input order). Rows are
    already z-scored, so correlation distance groups by expression *pattern*, not
    magnitude; average linkage. Falls back to euclidean when correlation is undefined
    (a constant row), and no-ops for trivially small matrices.

    Returns ``(z, labels, dendro)``. When ``want_dendro`` is set, ``dendro`` carries the
    SciPy dendrogram line coordinates (``icoord``/``dcoord``) for an ``orientation`` tree
    (``left`` for a row gutter, ``top`` for a column gutter) so the caller can draw the
    clustering tree aligned to these leaf-ordered rows; otherwise ``dendro`` is None.
    """
    import numpy as np

    z = np.asarray(z, dtype=float)
    if z.shape[0] < 3 or z.shape[1] < 2:
        return z, labels, None

    from scipy.cluster.hierarchy import dendrogram, leaves_list, linkage
    from scipy.spatial.distance import pdist

    dist = pdist(z, metric="correlation")
    if not np.all(np.isfinite(dist)):
        dist = pdist(z, metric="euclidean")
    linkage_matrix = linkage(dist, method="average")
    if want_dendro:
        dd = dendrogram(linkage_matrix, no_plot=True, orientation=orientation)
        order = dd["leaves"]  # same leaf order the icoord positions are built against
        dendro = {"icoord": dd["icoord"], "dcoord": dd["dcoord"]}
    else:
        order = leaves_list(linkage_matrix)
        dendro = None
    return z[order], [labels[i] for i in order], dendro
