"""Real Cepo engine — differential-stability markers (numpy/scipy/scanpy).

``cepo_ds`` is the algorithm core: it takes a cells x genes matrix (sparse or dense) +
a per-cell label vector and returns the gene x cell-type **DS** (differential-stability)
and **detection** matrices. It needs only numpy + scipy (no scanpy/anndata), so it is
unit-testable on synthetic data. ``run`` is the skill entrypoint: read → (optionally)
normalize → resolve the cell-type label column → ``cepo_ds`` → top-N-per-type dotplot +
Statistics table. Faithful to Cepo's ``R/Cepo.R`` (see run.py docstring; cite Kim 2021).
"""

# Common cell-type label columns, tried in order when none is given.
_LABEL_COLS = ("celltypes", "cell_type", "cell_types", "CellType", "celltype",
               "labels", "leiden", "clusters", "cluster")


def _col_stats(Xc):
    """Per-gene detection (fraction > 0) and CV (sd/mean) over the rows of ``Xc``
    (one cell type's cells). Sparse-aware — never densifies the full matrix. CV is
    +inf where the mean is 0, so undetected genes rank to the bottom of stability."""
    import numpy as np
    import scipy.sparse as sp

    n = Xc.shape[0]
    if sp.issparse(Xc):
        Xc = Xc.tocsr()
        mean = np.asarray(Xc.sum(axis=0)).ravel() / n
        sq = np.asarray(Xc.multiply(Xc).sum(axis=0)).ravel()
        nz = np.asarray((Xc > 0).sum(axis=0)).ravel() / n
    else:
        Xc = np.asarray(Xc, dtype=float)
        mean = Xc.mean(axis=0)
        sq = (Xc * Xc).sum(axis=0)
        nz = (Xc > 0).mean(axis=0)
    var = sq / n - mean**2
    if n > 1:
        var = var * n / (n - 1)  # sample variance (ddof=1) — matches R sd()
    sd = np.sqrt(np.maximum(var, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        cv = np.where(mean > 0, sd / np.where(mean > 0, mean, 1.0), np.inf)
    return nz, cv


def cepo_ds(X, labels, genes=None, weights=(0.5, 0.5), min_cells=20, exprs_pct=0.05):
    """Cepo differential-stability scores.

    Args:
        X: cells x genes expression (log-normalized; sparse or dense).
        labels: length-``n_cells`` cell-type labels.
        genes: optional gene names (defaults to integer positions).
        weights: (w_detection, w_stability) for the segment index. Default (.5, .5).
        min_cells: cell types with fewer cells are dropped.
        exprs_pct: keep genes detected in >= this fraction of cells in >= 1 type.

    Returns:
        (ds_df, det_df) — pandas DataFrames indexed by gene, columns = cell types.
        ``DS[g, c] = segIdx[g, c] - mean_{d != c} segIdx[g, d]``.
    """
    import numpy as np
    import pandas as pd
    from scipy.stats import rankdata

    labels = np.asarray(labels).astype(str)
    n_cells, n_genes = X.shape
    if genes is None:
        genes = np.array([str(i) for i in range(n_genes)])
    else:
        genes = np.asarray([str(g) for g in genes])

    types = [t for t in pd.unique(labels) if int((labels == t).sum()) >= min_cells]
    types = sorted(types)
    if len(types) < 2:
        raise ValueError(
            f"cepo needs >= 2 cell types with >= {min_cells} cells (got {len(types)})"
        )

    # One stats pass per type over the full gene set (detection + CV).
    nz_full = np.zeros((n_genes, len(types)))
    cv_full = np.zeros((n_genes, len(types)))
    for ci, t in enumerate(types):
        nz, cv = _col_stats(X[labels == t])
        nz_full[:, ci] = nz
        cv_full[:, ci] = cv

    # Gene filter: detected in >= exprs_pct of cells in at least one type.
    keep = nz_full.max(axis=1) >= exprs_pct
    if keep.sum() < 2:
        raise ValueError("cepo: no genes pass the expression filter — lower exprs_pct")
    nz_k, cv_k, genes_k = nz_full[keep], cv_full[keep], genes[keep]
    G = int(keep.sum())
    w1, w2 = weights

    # Segment index: rank detection up, rank CV down (more stable = higher), within each type.
    seg = np.zeros((G, len(types)))
    for ci in range(len(types)):
        x1 = rankdata(nz_k[:, ci]) / (G + 1)
        x2 = 1.0 - rankdata(cv_k[:, ci]) / (G + 1)
        seg[:, ci] = w1 * x1 + w2 * x2

    # DS: each type's segIdx minus the mean over the other types.
    k = len(types)
    rowsum = seg.sum(axis=1, keepdims=True)
    others = (rowsum - seg) / (k - 1)
    ds = seg - others

    ds_df = pd.DataFrame(ds, index=genes_k, columns=types)
    det_df = pd.DataFrame(nz_k, index=genes_k, columns=types)
    return ds_df, det_df


def _resolve_group(adata, requested):
    """Pick the cell-type label column: the requested one if present, else the first
    known label column, else Leiden-cluster the data as a fallback."""
    import scanpy as sc

    if requested and requested in adata.obs.columns:
        return requested
    for col in _LABEL_COLS:
        if col in adata.obs.columns:
            return col
    n_pcs = max(2, min(50, adata.n_obs - 1, adata.n_vars - 1))
    sc.pp.pca(adata, n_comps=n_pcs)
    sc.pp.neighbors(adata, n_neighbors=15, n_pcs=n_pcs)
    sc.tl.leiden(adata, flavor="igraph", n_iterations=2, directed=False)
    return "leiden"


def run(data_path: str, params: dict) -> dict:
    import scanpy as sc

    from skills._engine import to_bool
    from skills._genes import read_anndata
    from skills._plotly import jsonable
    from skills.proprietary.cepo.run import _dotplot_spec, _ds_table

    adata = read_anndata(data_path)
    sc.pp.filter_genes(adata, min_cells=3)
    if to_bool(params.get("normalize", True)):  # skip if the input is already normalized
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    group_key = _resolve_group(adata, params.get("group_key"))
    ds_df, det_df = cepo_ds(
        adata.X,
        adata.obs[group_key].to_numpy(),
        genes=adata.var_names,
        min_cells=int(params.get("min_cells", 20)),
        exprs_pct=float(params.get("exprs_pct", 0.05)),
    )

    n_genes = int(params["n_genes"])
    types = list(ds_df.columns)
    gene_order: list[str] = []
    table_rows: list[list] = []
    for t in types:
        top = ds_df[t].sort_values(ascending=False).head(n_genes)
        for gene in top.index:
            if gene not in gene_order:
                gene_order.append(str(gene))
            table_rows.append([t, str(gene), float(ds_df.loc[gene, t]), float(det_df.loc[gene, t])])

    xs: list[str] = []
    ys: list[str] = []
    ds_vals: list[float] = []
    sizes: list[float] = []
    detect: list[float] = []
    for t in types:
        for gene in gene_order:
            d = float(ds_df.loc[gene, t])
            f = float(det_df.loc[gene, t])
            xs.append(gene)
            ys.append(str(t))
            ds_vals.append(round(d, 4))
            detect.append(round(f, 4))
            sizes.append(round(4.0 + f * 22.0, 4))

    spec = _dotplot_spec(
        xs, ys, ds_vals, sizes, detect, gene_order, [str(t) for t in types],
        title=f"Cepo stability markers — top {n_genes} per {group_key}",
        table=_ds_table(table_rows),
    )
    return jsonable(spec)
