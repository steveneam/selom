"""Shared scRNA pipeline helpers reused across the embedding skills.

Kept dependency-light: scanpy is imported lazily inside the helpers so importing this
module stays cheap for the stub/registry paths.
"""


def select_hvg(adata, n_hvg):
    """Subset to the top-``n_hvg`` highly variable genes before PCA.

    OSCA's feature-selection step: rather than running PCA on every gene, focus on the
    most variable genes so technical noise from low-information genes doesn't dominate
    the principal components. Uses Scanpy's Seurat dispersion flavour (expects
    log-normalized values in ``.X``); returns a new gene-subset AnnData.

    No-op (returns ``adata`` unchanged) when ``n_hvg`` <= 0 or the data already has at
    most ``n_hvg`` genes, so callers can pass it unconditionally.
    """
    n = int(n_hvg or 0)
    if n <= 0 or adata.n_vars <= n:
        return adata
    import scanpy as sc

    sc.pp.highly_variable_genes(adata, n_top_genes=n, flavor="seurat")
    return adata[:, adata.var["highly_variable"]].copy()


def compute_pseudotime(adata, root="", groupby="leiden"):
    """Diffusion pseudotime per cell (OSCA/scanpy: diffusion map -> root -> DPT).

    Reuses an existing ``dpt_pseudotime`` / ``pseudotime`` obs column when present (so this
    chains after the ``trajectory`` skill or accepts a user-supplied ordering); otherwise
    builds a neighbour graph + diffusion map, roots the trajectory at the chosen cluster's
    most-extreme cell along DC1 (else the global DC1 extreme), and runs DPT. inf values
    (cells unreachable from the root) are clamped to the finite maximum. Returns
    ``(pseudotime ndarray, note)``.
    """
    import numpy as np
    import scanpy as sc

    def _clamp(pt):
        finite = pt[np.isfinite(pt)]
        return np.where(np.isfinite(pt), pt, float(finite.max())) if finite.size else pt

    obs = adata.obs
    for col in ("dpt_pseudotime", "pseudotime"):
        if col in obs.columns:
            return _clamp(np.asarray(obs[col], dtype=float)), f"existing {col}"

    n_pcs = max(2, min(50, adata.n_obs - 1, adata.n_vars - 1))
    if "X_pca" not in adata.obsm:
        sc.pp.pca(adata, n_comps=n_pcs)
    if "neighbors" not in adata.uns:
        sc.pp.neighbors(adata, n_neighbors=15, n_pcs=n_pcs)
    sc.tl.diffmap(adata)

    dc1 = np.asarray(adata.obsm["X_diffmap"])[:, 1]
    root = str(root or "").strip()
    groups = adata.obs[groupby].astype(str).to_numpy() if groupby in obs.columns else None
    if root and groups is not None and root in set(groups.tolist()):
        idx = np.where(groups == root)[0]
        adata.uns["iroot"] = int(idx[int(np.argmin(dc1[idx]))])
        note = f"root cluster {root}"
    else:
        adata.uns["iroot"] = int(np.argmin(dc1))
        note = "auto root (DC1 extreme)"
    sc.tl.dpt(adata)
    return _clamp(np.asarray(adata.obs["dpt_pseudotime"], dtype=float)), note
