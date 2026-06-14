"""Real scanpy engine for Leiden clustering.

Needs the scRNA stack (``uv sync --extra scrna``). Lazy imports keep the module
cheap until invoked. Emits the editable Plotly spec (cluster-size bar) via the
shared ``jsonable`` decoder so the wire shape matches the stub and the FE mock.
"""


def run(data_path: str, params: dict) -> dict:
    import scanpy as sc
    import plotly.express as px

    from skills._engine import to_bool
    from skills._plotly import jsonable

    from skills._genes import read_anndata

    adata = read_anndata(data_path)

    sc.pp.filter_genes(adata, min_cells=3)
    if to_bool(params.get("normalize", True)):  # skip if input is already normalized
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    # Guard n_comps so PCA never exceeds the data's rank (tiny demos / small inputs).
    n_pcs = max(2, min(int(params["n_pcs"]), adata.n_obs - 1, adata.n_vars - 1))
    sc.pp.pca(adata, n_comps=n_pcs)
    sc.pp.neighbors(adata, n_neighbors=int(params["n_neighbors"]), n_pcs=n_pcs)
    sc.tl.leiden(
        adata,
        resolution=float(params["resolution"]),
        flavor="igraph",
        n_iterations=2,
        directed=False,
    )

    counts = adata.obs["leiden"].value_counts().sort_index()
    subtitle = _silhouette_subtitle(adata, n_pcs)
    fig = px.bar(
        x=[str(c) for c in counts.index],
        y=counts.to_numpy(),
    )
    fig.update_traces(marker={"color": "#22d3ee"}, name="cells")
    fig.update_layout(
        title={
            "text": f"Leiden clusters (resolution {params['resolution']})",
            "subtitle": {"text": subtitle},
        },
        xaxis_title="cluster",
        yaxis_title="cells",
        bargap=0.25,
    )
    return jsonable(fig.to_plotly_json())


def _silhouette_subtitle(adata, n_pcs: int) -> str:
    """Publish-confidence guardrail: silhouette of the clustering on the PCA
    embedding (sklearn, BSD). Higher = cleaner separation; flags over/under-clustering.
    """
    from sklearn.metrics import silhouette_score

    labels = adata.obs["leiden"].to_numpy()
    n_clusters = len(set(labels))
    if n_clusters < 2:
        return f"{n_clusters} cluster · silhouette n/a (need ≥2 clusters)"
    emb = adata.obsm["X_pca"][:, :n_pcs]
    score = float(
        silhouette_score(emb, labels, sample_size=min(2000, adata.n_obs), random_state=0)
    )
    return f"{n_clusters} clusters · silhouette {score:.2f} — higher = cleaner separation"
