"""Real expression-heatmap engine — scRNA (scanpy) or bulk CSV (pandas).

scRNA: rank markers per cluster, take the top few per group, show mean log1p
expression per cluster, z-scored per gene. Bulk CSV (genes x samples): take the
top-variance genes, z-scored per gene. Both feed ``run.heatmap_spec``.
"""

from skills.heatmap.run import _CLUSTER_PALETTE, _TRUNK_COLOR, heatmap_spec
from skills._plotly import jsonable
from skills._design import load_design


def run(data_path: str, params: dict) -> dict:
    if str(data_path).lower().endswith((".h5ad", ".h5")):
        return _scrna(data_path, params)
    return _bulk(data_path, params)


def _resolve_annotations(params: dict) -> list[str]:
    """The design-sheet columns the user asked to paint as annotation tracks (comma-separated)."""
    raw = str(params.get("annotations") or "").strip()
    return [c.strip() for c in raw.split(",") if c.strip()]


def _col_tracks(xlabels, params: dict):
    """Categorical annotation tracks aligned to the (already-ordered) columns, from the design sheet.

    For each requested column, map every heatmap column label → its category value via the sample
    sheet (joined on sample id), encode categories as integer codes (stable, sorted order), and
    hand ``heatmap_spec`` the strips to paint. Returns None when no tracks are asked for or no sheet
    is supplied; silently skips a requested column that isn't in the sheet (honest — never invents
    a track). A column with no resolvable categories is dropped.
    """
    cols = _resolve_annotations(params)
    if not cols:
        return None
    design = load_design(params)
    if design is None:
        return None
    labels = [str(s) for s in xlabels]
    tracks = []
    for col in cols:
        if col not in design.columns:
            continue
        values = [
            str(design[col].get(s)) if s in design.index and design[col].get(s) is not None else ""
            for s in labels
        ]
        cats = sorted({v for v in values if v and v.lower() != "nan"})
        if not cats:
            continue
        index = {c: i for i, c in enumerate(cats)}
        codes = [index.get(v, -1) for v in values]
        tracks.append({"name": col, "categories": cats, "codes": codes})
    return tracks or None


_QUANT_PREF = ("condition", "genotype", "group", "treatment")


def _two_group_columns(columns, params):
    """The two sample groups for a log₂FC side track, from the sample sheet — the first design column
    that splits these samples into exactly two levels (a named factor preferred). Returns
    ``(group_a_cols, group_b_cols, label)`` sorted so the second level is the numerator, or None."""
    design = load_design(params)
    if design is None:
        return None
    labels = [str(c) for c in columns]
    cols = list(design.columns)
    ordered = [c for c in cols if str(c).strip().lower() in _QUANT_PREF]
    ordered += [c for c in cols if c not in ordered]
    for col in ordered:
        groups: dict[str, list[str]] = {}
        for s in labels:
            if s in design.index:
                v = design[col].get(s)
                if v is not None and str(v).strip() and str(v).lower() != "nan":
                    groups.setdefault(str(v), []).append(s)
        if len(groups) == 2:
            (ga, a_cols), (gb, b_cols) = sorted(groups.items())
            return a_cols, b_cols, f"log2FC {gb}/{ga}"
    return None


def _row_quant(frame, params):
    """A per-gene quantitative side-track value keyed by gene label, or None. ``variance`` / ``mean``
    are computed from the displayed matrix (always available); ``logfc`` is the log₂ mean-count
    fold-change between the sample sheet's two condition groups (falls back to None when no 2-level
    design column applies)."""
    import numpy as np

    mode = str(params.get("quant_track") or "none").lower()
    if mode in ("", "none"):
        return None
    labels = [str(g) for g in frame.index]
    if mode == "variance":
        vals = frame.var(axis=1).to_numpy()
        return {"name": "variance", "diverging": False, "map": dict(zip(labels, map(float, vals)))}
    if mode == "mean":
        vals = frame.mean(axis=1).to_numpy()
        return {"name": "mean", "diverging": False, "map": dict(zip(labels, map(float, vals)))}
    if mode == "logfc":
        groups = _two_group_columns(list(frame.columns), params)
        if groups is None:
            return None
        a_cols, b_cols, name = groups
        a = frame[a_cols].mean(axis=1).to_numpy()
        b = frame[b_cols].mean(axis=1).to_numpy()
        fc = np.log2(b + 1.0) - np.log2(a + 1.0)
        return {"name": name, "diverging": True, "map": dict(zip(labels, map(float, fc)))}
    return None


def _build_row_quant(rq, ylabels):
    """Project a ``_row_quant`` map onto the final (clustered) row order → the spec's value list."""
    if rq is None:
        return None
    return {
        "name": rq["name"],
        "diverging": rq["diverging"],
        "values": [rq["map"].get(str(label), 0.0) for label in ylabels],
    }


def _split_columns(z, xlabels, params):
    """Block-split the columns by a categorical sample-sheet factor (heatmap-clustermap-spec §2 / refs
    035617/035636). Re-orders the columns grouped by ``split_by``'s category, inserts a blank spacer
    column between blocks, and returns a per-block header. Returns ``(z_list, xlabels, headers)`` —
    ``z_list`` is a plain list-of-lists with ``None`` spacer cells (jsonable leaves NaN as invalid
    JSON, so spacers are None, which Plotly draws as a gap). Identity when no/invalid factor or <2
    groups (honest — never invents a split). Column clustering is dropped by the caller when splitting,
    so the imposed categorical order isn't fought by a cross-block tree."""
    import numpy as np

    col = str(params.get("split_by") or "").strip()
    if not col:
        return z, xlabels, None
    design = load_design(params)
    if design is None or col not in design.columns:
        return z, xlabels, None
    labels = [str(s) for s in xlabels]
    grp = {s: (str(design[col].get(s)) if s in design.index else "") for s in labels}
    cats = sorted({g for g in grp.values() if g and g.lower() != "nan"})
    if len(cats) < 2:
        return z, xlabels, None

    z = np.asarray(z, dtype=float)
    src_cols, new_labels, headers = [], [], []
    spacer = 0
    for cat in cats:
        members = [i for i, s in enumerate(labels) if grp[s] == cat]
        if not members:
            continue
        if src_cols:  # a blank spacer column between blocks
            spacer += 1
            src_cols.append(None)
            new_labels.append(" " * spacer)
        start = len(new_labels)
        for i in members:
            src_cols.append(i)
            new_labels.append(labels[i])
        headers.append({"group": cat, "center": new_labels[start + len(members) // 2]})

    z_list = [
        [None if src is None else round(float(z[r, src]), 4) for src in src_cols]
        for r in range(z.shape[0])
    ]
    return z_list, new_labels, headers


def _cluster_and_split(z, ylabels, xcols, params):
    """Cluster the rows (and columns, unless block-splitting) then optionally block-split the columns.
    Splitting imposes the categorical column order, so column clustering + the cross-block tree are
    dropped; rows still cluster. Returns ``(z, ylabels, xlabels, row_dendro, col_dendro, col_headers)``;
    ``z`` is a plain list when split (with None spacers), else the clustered numpy array."""
    split = bool(str(params.get("split_by") or "").strip())
    cluster_params = params
    if split:
        mode = _resolve_cluster(params)
        cluster_params = {**params, "cluster": "row" if mode in ("row", "both") else "none"}
    z, ylabels, xlabels, row_dendro, col_dendro = _cluster(z, ylabels, xcols, cluster_params)
    col_headers = None
    if split:
        z, xlabels, col_headers = _split_columns(z, xlabels, params)
    return z, ylabels, xlabels, row_dendro, col_dendro, col_headers


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
    rq = _row_quant(means, params)
    z, genes, xlabels, row_dendro, col_dendro, col_headers = _cluster_and_split(
        z, genes, list(means.columns), params
    )
    col_tracks = _col_tracks(xlabels, params)
    row_quant = _build_row_quant(rq, genes)
    z_list = z if isinstance(z, list) else z.tolist()
    return jsonable(
        heatmap_spec(
            z_list, xlabels, genes, "Marker heatmap", "cluster", row_dendro, col_dendro,
            col_tracks, row_quant, col_headers,
        )
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
    rq = _row_quant(sub, params)
    z, ylabels, xlabels, row_dendro, col_dendro, col_headers = _cluster_and_split(
        z, ylabels0, list(sub.columns), params
    )
    col_tracks = _col_tracks(xlabels, params)
    row_quant = _build_row_quant(rq, ylabels)
    z_list = z if isinstance(z, list) else z.tolist()
    return jsonable(
        heatmap_spec(
            z_list, xlabels, ylabels, "Top-variable genes", "sample", row_dendro, col_dendro,
            col_tracks, row_quant, col_headers,
        )
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


def _resolve_cut_k(params):
    """The number of clusters to colour the dendrogram branches into (``cut_k`` param), or None when
    unset / < 2 (no cut → the single grey tree). Heatmap-clustermap-spec §9 / refs 035648/035701."""
    try:
        k = int(params.get("cut_k") or 0)
    except (TypeError, ValueError):
        return None
    return k if k >= 2 else None


def _cut_threshold(linkage_matrix, k):
    """The SciPy ``color_threshold`` that splits a tree into ``k`` coloured clusters: the distance of
    the (k−1)-th largest merge, so those k−1 trunk merges stay at-or-above threshold (grey) and
    everything below forms k coloured clusters. None when k is invalid for this tree's leaf count."""
    import numpy as np

    n_leaves = linkage_matrix.shape[0] + 1  # n−1 merges → n leaves
    if k is None or k < 2 or k > n_leaves:
        return None
    dists = np.sort(linkage_matrix[:, 2])
    return float(dists[-(k - 1)])


def _cluster(z, ylabels, xlabels, params):
    """Apply the resolved clustering mode to a genes×samples z-matrix.

    Rows (genes) are ALWAYS reordered into hierarchical-clustering leaf order — the standard
    *clustered* heatmap baseline — regardless of mode; the mode only governs which dendrogram
    TREES are drawn and whether the COLUMNS are also reordered. ``row``/``both`` draw the row
    tree; ``column``/``both`` cluster + reorder the samples and draw the column tree (needs ≥3
    samples, else it no-ops gracefully). Returns ``(z, ylabels, xlabels, row_dendro, col_dendro)``.
    """
    mode = _resolve_cluster(params)
    cut_k = _resolve_cut_k(params)
    want_row_tree = mode in ("row", "both")
    want_cols = mode in ("column", "both")

    z, ylabels, row_dendro = _order_rows(z, ylabels, want_row_tree, cut_k=cut_k)
    col_dendro = None
    if want_cols:
        # Cluster samples by transposing: rows-of-the-transpose ARE the columns. Distances over
        # columns are invariant to the row permutation above, so order of operations is safe.
        zt, xlabels, col_dendro = _order_rows(z.T, xlabels, True, orientation="top", cut_k=cut_k)
        z = zt.T
    return z, ylabels, xlabels, row_dendro, col_dendro


def _order_rows(z, labels, want_dendro=False, orientation="left", cut_k=None):
    """Reorder rows by hierarchical-clustering leaf order so co-varying genes sit
    together — the standard *clustered* heatmap layout (vs. raw input order). Rows are
    already z-scored, so correlation distance groups by expression *pattern*, not
    magnitude; average linkage. Falls back to euclidean when correlation is undefined
    (a constant row), and no-ops for trivially small matrices.

    Returns ``(z, labels, dendro)``. When ``want_dendro`` is set, ``dendro`` carries the
    SciPy dendrogram line coordinates (``icoord``/``dcoord``) for an ``orientation`` tree
    (``left`` for a row gutter, ``top`` for a column gutter) so the caller can draw the
    clustering tree aligned to these leaf-ordered rows; otherwise ``dendro`` is None. When
    ``cut_k`` ≥ 2 the tree is cut into k clusters and ``dendro["colors"]`` carries SciPy's
    per-link colour (each cluster a hue from ``_CLUSTER_PALETTE``, the trunk ``_TRUNK_COLOR``)
    so ``run.heatmap_spec`` draws coloured branches (heatmap-clustermap-spec §9).
    """
    import numpy as np

    z = np.asarray(z, dtype=float)
    if z.shape[0] < 3 or z.shape[1] < 2:
        return z, labels, None

    from scipy.cluster.hierarchy import leaves_list, linkage
    from scipy.spatial.distance import pdist

    dist = pdist(z, metric="correlation")
    if not np.all(np.isfinite(dist)):
        dist = pdist(z, metric="euclidean")
    linkage_matrix = linkage(dist, method="average")
    if want_dendro:
        dd, colors = _dendrogram(linkage_matrix, orientation, cut_k)
        order = dd["leaves"]  # same leaf order the icoord positions are built against
        dendro = {"icoord": dd["icoord"], "dcoord": dd["dcoord"]}
        if colors is not None:
            dendro["colors"] = colors
    else:
        order = leaves_list(linkage_matrix)
        dendro = None
    return z[order], [labels[i] for i in order], dendro


def _dendrogram(linkage_matrix, orientation, cut_k):
    """Build the SciPy dendrogram dict (+ optional per-link ``color_list``). With a valid ``cut_k``
    the link palette is set to ``_CLUSTER_PALETTE`` and above-cut links to ``_TRUNK_COLOR``, so the
    returned colours are the literal hex strings ``run.heatmap_spec`` groups branches by; the global
    palette is reset afterwards so the colouring never leaks to another figure. Returns
    ``(dendrogram_dict, colors_or_None)``."""
    from scipy.cluster.hierarchy import dendrogram, set_link_color_palette

    thr = _cut_threshold(linkage_matrix, cut_k)
    if thr is None:
        return dendrogram(linkage_matrix, no_plot=True, orientation=orientation), None
    set_link_color_palette(list(_CLUSTER_PALETTE))
    try:
        dd = dendrogram(
            linkage_matrix, no_plot=True, orientation=orientation,
            color_threshold=thr, above_threshold_color=_TRUNK_COLOR,
        )
    finally:
        set_link_color_palette(None)  # reset the module-global palette (no cross-figure leak)
    return dd, list(dd["color_list"])
