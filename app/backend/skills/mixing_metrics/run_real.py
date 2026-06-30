"""Real engine for mixing_metrics — AnnData → metrics bar chart + Statistics table.

Lazy heavy imports (scanpy only when an embedding must be computed); the metric math lives
in the scanpy-free ``metrics`` module. Reads an embedding from ``obsm`` (or computes PCA),
resolves the batch + optional label columns, and returns the editable Plotly spec with the
metric table attached as ``spec["table"]`` (the Pillar-1 Statistics pattern).
"""

from __future__ import annotations

# Common obs columns that carry the library/batch label, tried in order (real h5ads disagree
# on the name) — same alias set the integration engine uses.
_BATCH_FALLBACKS = ("sample", "batch", "dataset", "donor", "library", "orig.ident")
# Embedding preference when embedding_key is unset: the corrected reps first, then raw PCA.
_EMBED_PREF = ("X_pca_melody", "X_pca_harmony", "X_emb", "X_pca")


def _resolve_batch_key(adata, requested: str) -> str | None:
    """The first usable (>=2 levels) batch column: the requested one, else a known alias."""
    candidates = [requested] if requested else []
    candidates += [c for c in _BATCH_FALLBACKS if c != requested]
    for col in candidates:
        if col and col in adata.obs and adata.obs[col].nunique() >= 2:
            return col
    return None


def _resolve_embedding(adata, params) -> tuple["object", str]:
    """An (embedding, name) pair: the requested obsm key, a known corrected/PCA rep, or computed PCA."""
    from skills._engine import to_bool

    key = str(params.get("embedding_key") or "").strip()
    if key and key in adata.obsm:
        return adata.obsm[key], key
    for cand in _EMBED_PREF:
        if cand in adata.obsm:
            return adata.obsm[cand], cand

    # No embedding present → compute one (normalize + log1p + PCA), like the integration engine.
    import scanpy as sc

    sc.pp.filter_genes(adata, min_cells=3)
    if to_bool(params.get("normalize", True)):
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)
    n_pcs = max(2, min(int(params.get("n_pcs", 50)), adata.n_obs - 1, adata.n_vars - 1))
    sc.pp.pca(adata, n_comps=n_pcs)
    return adata.obsm["X_pca"], "X_pca (computed)"


def run(data_path: str, params: dict) -> dict:
    from skills._genes import read_anndata
    from skills.mixing_metrics.metrics import compute_all

    adata = read_anndata(data_path)

    batch_key = _resolve_batch_key(adata, str(params.get("batch_key") or "").strip())
    label_key = str(params.get("label_key") or "").strip() or None
    if label_key and label_key not in adata.obs:
        label_key = None  # honest: a missing label column just makes those metrics N/A

    embedding, emb_name = _resolve_embedding(adata, params)
    batch = adata.obs[batch_key].to_numpy() if batch_key else None
    labels = adata.obs[label_key].to_numpy() if label_key else None

    rows = compute_all(
        embedding,
        batch,
        labels,
        perplexity=int(params.get("perplexity", 30)),
        k=int(params.get("n_neighbors", 30)),
    )
    return _figure(rows, batch_key, label_key, emb_name)


def _figure(rows: list[dict], batch_key: str | None, label_key: str | None, emb_name: str) -> dict:
    from skills._table import table

    computed = [r for r in rows if r["value"] is not None]
    bar = {
        "type": "bar",
        "orientation": "h",
        "x": [r["value"] for r in computed],
        "y": [r["label"] for r in computed],
        "name": "mixing metrics",
        "hovertext": [f"{r['label']}: {r['value']} ({r['direction']})" for r in computed],
    }
    title = f"Integration mixing metrics — batch: {batch_key or 'n/a'}"
    if label_key:
        title += f", labels: {label_key}"
    title += f"<br><sub>embedding: {emb_name}</sub>"

    spec = {
        "data": [bar],
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": "score"}},
        },
    }
    spec["table"] = table(
        ["metric", "value", "direction", "note"],
        [
            [r["label"], (r["value"] if r["value"] is not None else "N/A"), r["direction"], r["note"]]
            for r in rows
        ],
        title="Integration mixing metrics",
    )
    return spec
