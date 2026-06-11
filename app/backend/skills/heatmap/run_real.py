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
    adata = sc.read_h5ad(data_path)
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
    return jsonable(heatmap_spec(z.tolist(), list(means.columns), genes, "Marker heatmap", "cluster"))


def _bulk(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd

    n_genes = int(params["n_genes"])
    df = pd.read_csv(data_path, index_col=0)
    top = df.var(axis=1).sort_values(ascending=False).head(n_genes).index
    sub = df.loc[top]
    z = _row_zscore(sub, np)
    return jsonable(heatmap_spec(z.tolist(), list(sub.columns), [str(g) for g in sub.index],
                                 "Top-variable genes", "sample"))


def _row_zscore(frame, np):
    """Per-row z-score (rounded), with zero-variance rows left at 0."""
    values = frame.to_numpy(dtype=float)
    mean = values.mean(axis=1, keepdims=True)
    std = values.std(axis=1, keepdims=True)
    std[std == 0] = 1.0
    return np.round((values - mean) / std, 4)
