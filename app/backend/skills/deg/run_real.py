"""Real differential-expression engines — scRNA (scanpy) and bulk (pyDESeq2).

Mode is chosen from the ``mode`` param (``auto`` -> scRNA for ``.h5ad``, bulk for a
CSV counts table). Both paths emit the same figure: a horizontal bar of the top-N
genes by signed score, coloured up (cyan) / down (rose).

Bulk input contract: a CSV of raw integer counts, genes in rows (first column =
gene id), samples in columns. The 2-level design is inferred from each column
name's prefix before the first ``_`` (e.g. ``ctrl_1``, ``treat_2``); exactly two
groups are required.
"""

UP = "#22d3ee"
DOWN = "#f43f5e"


def run(data_path: str, params: dict) -> dict:
    mode = (params.get("mode") or "auto").lower()
    if mode == "auto":
        mode = "scrna" if str(data_path).lower().endswith((".h5ad", ".h5")) else "bulk"
    if mode == "bulk":
        return _bulk(data_path, params)
    return _scrna(data_path, params)


def _scrna(data_path: str, params: dict) -> dict:
    import scanpy as sc

    from skills._plotly import jsonable

    adata = sc.read_h5ad(data_path)
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

    sc.tl.rank_genes_groups(adata, groupby, method=params.get("method", "wilcoxon"))
    res = adata.uns["rank_genes_groups"]
    group0 = res["names"].dtype.names[0]
    top_n = int(params["top_n"])
    names = [str(res["names"][group0][i]) for i in range(top_n)]
    scores = [float(res["scores"][group0][i]) for i in range(top_n)]
    title = f"Top markers — {groupby} group {group0}"
    return _bar(names, scores, title, jsonable)


def _bulk(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd

    from skills._plotly import jsonable

    counts = pd.read_csv(data_path, index_col=0)
    conditions = [str(c).split("_", 1)[0] for c in counts.columns]
    groups = sorted(set(conditions))
    if len(groups) != 2:
        raise ValueError(
            f"bulk DEG needs exactly 2 conditions inferred from column prefixes, got {groups}"
        )
    metadata = pd.DataFrame({"condition": conditions}, index=counts.columns)
    top_n = int(params["top_n"])

    try:
        from pydeseq2.dds import DeseqDataSet
        from pydeseq2.ds import DeseqStats

        dds = DeseqDataSet(counts=counts.T, metadata=metadata, design="~condition")
        dds.deseq2()
        stat_res = DeseqStats(dds, contrast=["condition", groups[1], groups[0]])
        stat_res.summary()
        res = stat_res.results_df.dropna(subset=["log2FoldChange", "padj"])
        res = res.reindex(res["log2FoldChange"].abs().sort_values(ascending=False).index).head(top_n)
        names = [str(g) for g in res.index]
        scores = [float(v) for v in res["log2FoldChange"]]
    except ModuleNotFoundError:
        # Light fallback when pyDESeq2 isn't installed: log2FC of mean CPM per group.
        cpm = counts.div(counts.sum(axis=0), axis=1) * 1e6
        a = cpm.loc[:, [c == groups[0] for c in conditions]].mean(axis=1)
        b = cpm.loc[:, [c == groups[1] for c in conditions]].mean(axis=1)
        lfc = np.log2((b + 1.0) / (a + 1.0))
        lfc = lfc.reindex(lfc.abs().sort_values(ascending=False).index).head(top_n)
        names = [str(g) for g in lfc.index]
        scores = [float(v) for v in lfc]

    return _bar(names, scores, f"Top DE genes — {groups[1]} vs {groups[0]}", jsonable)


def _bar(names, scores, title, jsonable) -> dict:
    # Ascending so the strongest |score| sits at the top of the horizontal bar.
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    names = [names[i] for i in order]
    scores = [scores[i] for i in order]
    spec = {
        "data": [
            {
                "type": "bar",
                "orientation": "h",
                "x": scores,
                "y": names,
                "marker": {"color": [UP if s >= 0 else DOWN for s in scores]},
                "name": "score",
            }
        ],
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": "score (signed)"}},
            "yaxis": {"title": {"text": "gene"}},
            "bargap": 0.3,
        },
    }
    return jsonable(spec)
