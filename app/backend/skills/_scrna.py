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
