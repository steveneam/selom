"""Real scanpy engine for marker-gene violins.

Needs the scRNA stack. Normalizes -> log1p, ensures a grouping (computes Leiden if
the requested ``groupby`` is absent), picks a marker gene, and emits one violin
trace per group. Output is the editable Plotly spec via the shared decoder.
"""


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import scanpy as sc

    from skills._engine import to_bool
    from skills._plotly import jsonable

    adata = sc.read_h5ad(data_path)
    sc.pp.filter_genes(adata, min_cells=3)
    if to_bool(params.get("normalize", True)):  # skip if input is already normalized
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    groupby = params.get("groupby") or "leiden"
    if groupby not in adata.obs.columns:
        n_pcs = max(2, min(50, adata.n_obs - 1, adata.n_vars - 1))
        sc.pp.pca(adata, n_comps=n_pcs)
        sc.pp.neighbors(adata, n_neighbors=15, n_pcs=n_pcs)
        sc.tl.leiden(
            adata,
            resolution=float(params["resolution"]),
            flavor="igraph",
            n_iterations=2,
            directed=False,
        )
        groupby = "leiden"

    gene = (params.get("gene") or "").strip()
    if gene not in set(map(str, adata.var_names)):
        gene = str(adata.var_names[_argmax_variance(adata.X, np)])

    expr = adata[:, gene].X
    expr = np.asarray(expr.todense()).ravel() if hasattr(expr, "todense") else np.asarray(expr).ravel()
    groups = adata.obs[groupby].astype(str)

    traces = []
    for g in sorted(groups.unique(), key=lambda s: (len(s), s)):
        ys = expr[(groups == g).to_numpy()]
        traces.append(
            {
                "type": "violin",
                "name": f"cluster {g}",
                "y": ys,
                "box": {"visible": True},
                "meanline": {"visible": True},
                "points": False,
            }
        )

    spec = {
        "data": traces,
        "layout": {
            "title": {"text": f"{gene} expression by {groupby}"},
            "xaxis": {"title": {"text": groupby}},
            "yaxis": {"title": {"text": "expression (log1p)"}},
        },
    }
    return jsonable(spec)


def _argmax_variance(X, np) -> int:
    """Index of the highest-variance gene, handling sparse or dense X."""
    if hasattr(X, "multiply"):  # scipy sparse
        mean = np.asarray(X.mean(axis=0)).ravel()
        mean_sq = np.asarray(X.multiply(X).mean(axis=0)).ravel()
        var = mean_sq - mean**2
    else:
        var = np.asarray(X).var(axis=0)
    return int(np.argmax(var))
