"""Real Scanpy -> editable Plotly figure-spec engine for the scRNA UMAP skill.

Requires the scRNA stack: ``uv sync --extra scrna`` (scanpy + leidenalg + igraph).
Imports are lazy (inside ``run``) so importing this module stays cheap and the light
skeleton never pays for the heavy deps unless this engine is actually invoked. The
return value is the EDITABLE Plotly spec ({data, layout}) the frontend renders —
never a baked PNG.
"""


def run(data_path: str, params: dict) -> dict:
    import scanpy as sc
    import plotly.express as px

    from skills._plotly import jsonable

    adata = sc.read_h5ad(data_path)

    # Minimal, honest scRNA pipeline: drop all-zero genes -> normalize -> log1p ->
    # PCA -> kNN graph -> Leiden clusters -> UMAP embedding.
    sc.pp.filter_genes(adata, min_cells=3)
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)

    # Guard n_comps so PCA never exceeds the data's rank (small inputs / tiny demos).
    n_pcs = max(2, min(int(params["n_pcs"]), adata.n_obs - 1, adata.n_vars - 1))
    sc.pp.pca(adata, n_comps=n_pcs)
    sc.pp.neighbors(adata, n_neighbors=int(params["n_neighbors"]), n_pcs=n_pcs)
    sc.tl.leiden(adata, flavor="igraph", n_iterations=2, directed=False)
    sc.tl.umap(adata)

    df = adata.obs.copy()
    df["UMAP1"] = adata.obsm["X_umap"][:, 0]
    df["UMAP2"] = adata.obsm["X_umap"][:, 1]

    color_by = params.get("color_by", "leiden")
    if color_by not in df.columns:
        color_by = "leiden"

    fig = px.scatter(df, x="UMAP1", y="UMAP2", color=color_by, title="scRNA UMAP")
    fig.update_traces(marker={"size": 4})
    fig.update_layout(legend_title_text=color_by)

    # Return PLAIN JSON arrays + native scalars (no numpy types, no Plotly base64
    # typed-array encoding). FastAPI's encoder needs JSON-safe primitives, and the
    # frontend/MSW mock are built against the stub's plain-array shape — keeping the
    # live engine identical means mock and live render byte-for-byte the same spec.
    return jsonable(fig.to_plotly_json())
