"""Real Scanpy + Harmony -> editable Plotly figure-spec engine for the integration skill.

Requires the heavy stack: ``uv sync --extra omics`` (scanpy + harmonypy). Imports are
lazy (inside ``run``) so importing this module stays cheap and the light skeleton never
pays for the heavy deps unless this engine is actually invoked.

Pipeline: read -> drop all-zero genes -> (normalize -> log1p) -> PCA -> Harmony batch
correction on the chosen ``batch_key`` (scanpy's ``external.pp.harmony_integrate``, which
wraps harmonypy and writes ``X_pca_harmony``) -> kNN graph + Leiden + UMAP on the
*corrected* embedding. The return value is the EDITABLE Plotly spec ({data, layout}) the
frontend renders — the SAME shape ``umap_scrna`` produces, so an integrated UMAP drops
straight into the editor. Colour defaults to the batch key (to show the mixing); pass
``color_by`` to colour by Leiden cluster or any obs column instead.

Graceful single-batch fallback: if the batch key is missing or has fewer than two levels
there is nothing to integrate, so PCA is used directly (no Harmony) and the title says so —
the skill never errors just because a dataset happens to be one batch.
"""

# Common obs columns that carry the library/batch label, tried in order when the
# requested batch_key is absent (real h5ads disagree on the name).
_BATCH_FALLBACKS = ("sample", "batch", "dataset", "donor", "library", "orig.ident")


def _resolve_batch_key(adata, requested: str) -> str | None:
    """The first usable (>=2 levels) batch column: the requested one, else a known alias."""
    candidates = [requested] if requested else []
    candidates += [c for c in _BATCH_FALLBACKS if c != requested]
    for col in candidates:
        if col and col in adata.obs and adata.obs[col].nunique() >= 2:
            return col
    return None


def run(data_path: str, params: dict) -> dict:
    import scanpy as sc
    import plotly.express as px

    from skills._engine import to_bool
    from skills._genes import read_anndata
    from skills._plotly import jsonable

    adata = read_anndata(data_path)

    sc.pp.filter_genes(adata, min_cells=3)
    if to_bool(params.get("normalize", True)):
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    # Optional feature selection before PCA (OSCA step). Off by default (n_hvg=0); ~2000
    # is standard, and OSCA recommends more HVGs for multi-batch integration.
    from skills._scrna import select_hvg
    adata = select_hvg(adata, params.get("n_hvg", 0))

    # Guard n_comps so PCA never exceeds the data's rank (small inputs / tiny demos).
    n_pcs = max(2, min(int(params["n_pcs"]), adata.n_obs - 1, adata.n_vars - 1))
    sc.pp.pca(adata, n_comps=n_pcs)

    batch_key = _resolve_batch_key(adata, str(params.get("batch_key") or "").strip())
    integrated = batch_key is not None
    if integrated:
        # scanpy wraps harmonypy.run_harmony; theta = diversity penalty (higher = stronger mixing).
        sc.external.pp.harmony_integrate(
            adata, batch_key,
            theta=float(params.get("theta", 2.0)),
            max_iter_harmony=int(params.get("max_iter_harmony", 10)),
        )
        use_rep = "X_pca_harmony"
        title = f"Integrated scRNA UMAP — Harmony (batch: {batch_key})"
    else:
        use_rep = "X_pca"
        title = "scRNA UMAP — no batch correction (single batch)"

    # Over-correction diagnostic (OSCA): quantify batch mixing BEFORE (raw PCA) vs AFTER
    # (Harmony) as the mean normalized kNN batch-label entropy (1 = fully mixed, 0 = each
    # cell's neighbours are all one batch). A real rise is the number that proves Harmony
    # mixed batches; no rise means correction didn't take (or there was nothing to mix).
    if integrated:
        before = _batch_mixing(adata.obsm["X_pca"], adata.obs[batch_key].to_numpy())
        after = _batch_mixing(adata.obsm["X_pca_harmony"], adata.obs[batch_key].to_numpy())
        if before is not None and after is not None:
            title = f"{title}<br><sub>batch mixing {before:.2f} → {after:.2f} (kNN entropy, 1=fully mixed)</sub>"

    sc.pp.neighbors(adata, n_neighbors=int(params["n_neighbors"]), use_rep=use_rep)
    sc.tl.leiden(adata, flavor="igraph", n_iterations=2, directed=False)
    sc.tl.umap(adata)

    df = adata.obs.copy()
    df["UMAP1"] = adata.obsm["X_umap"][:, 0]
    df["UMAP2"] = adata.obsm["X_umap"][:, 1]

    # Default to colouring by the batch key (shows the mixing); fall back to leiden.
    color_by = str(params.get("color_by") or "").strip()
    if color_by not in df.columns:
        color_by = batch_key if integrated and batch_key in df.columns else "leiden"

    fig = px.scatter(df, x="UMAP1", y="UMAP2", color=color_by, title=title)
    fig.update_traces(marker={"size": 4})
    fig.update_layout(legend_title_text=color_by)

    # Plain JSON arrays + native scalars (see umap_scrna.run_scanpy) so mock and live
    # render byte-for-byte the same spec.
    return jsonable(fig.to_plotly_json())


def _batch_mixing(embedding, labels, k: int = 30):
    """Mean normalized kNN batch-label entropy over cells — a cheap mixing diagnostic.

    For each cell, look at its ``k`` nearest neighbours in ``embedding`` and compute the
    Shannon entropy of their batch labels, normalized by ``log(n_batches)`` so it lands in
    ``[0, 1]``: 1 = neighbours span batches evenly (well mixed), 0 = neighbours are all one
    batch (unmixed). Returns the mean over all cells, or ``None`` with fewer than 2 batches.
    """
    import numpy as np
    from sklearn.neighbors import NearestNeighbors

    labels = np.asarray(labels)
    cats, codes = np.unique(labels, return_inverse=True)
    if len(cats) < 2:
        return None
    k = min(int(k), len(labels) - 1)
    if k < 1:
        return None
    _, idx = NearestNeighbors(n_neighbors=k + 1).fit(embedding).kneighbors(embedding)
    neigh = codes[idx[:, 1:]]  # drop self-neighbour
    ent = np.zeros(len(labels))
    for c in range(len(cats)):
        p = (neigh == c).mean(axis=1)
        nz = p > 0  # take logs only where defined (avoids log(0) warnings; 0·log0 ≡ 0)
        ent[nz] -= p[nz] * np.log(p[nz])
    return float((ent / np.log(len(cats))).mean())
