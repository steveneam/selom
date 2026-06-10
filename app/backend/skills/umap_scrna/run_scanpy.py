"""Real Scanpy -> editable Plotly figure-spec engine for the scRNA UMAP skill.

Requires the heavy scverse stack: `uv sync --extra omics`. The scanpy/plotly imports
are intentionally lazy (inside `run`) so importing this module is cheap and the light
skeleton never pays for the heavy deps unless this engine is actually invoked.
"""


def run(data_path: str, params: dict) -> dict:
    import scanpy as sc
    import plotly.express as px

    adata = sc.read_h5ad(data_path)                 # or sc.read_10x_mtx(...)
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    sc.pp.pca(adata, n_comps=params["n_pcs"])
    sc.pp.neighbors(adata, n_neighbors=params["n_neighbors"])
    sc.tl.leiden(adata)
    sc.tl.umap(adata)
    df = adata.obs.copy()
    df["UMAP1"], df["UMAP2"] = adata.obsm["X_umap"][:, 0], adata.obsm["X_umap"][:, 1]
    fig = px.scatter(df, x="UMAP1", y="UMAP2", color=params["color_by"],
                     title="scRNA UMAP")
    return fig.to_plotly_json()                     # the EDITABLE spec the frontend renders
