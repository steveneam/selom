"""Real volcano engine — reads a DE results CSV and plots it.

Column detection is tolerant of the common DE-tool outputs (DESeq2, edgeR/limma,
scanpy): a fold-change column, an adjusted-p column, and a gene-id column (or the
frame index). Emits the same spec shape as the stub via ``run._assemble``.
"""

import math

from skills.volcano.run import _assemble

_FC_COLS = ["log2foldchange", "log2fc", "logfc", "log2_fold_change", "avg_log2fc"]
_P_COLS = ["padj", "adj.p.val", "fdr", "qvalue", "q.value", "pvals_adj", "pvalue", "pval", "p.value"]
_GENE_COLS = ["gene", "genes", "symbol", "names", "gene_id", "id"]


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd

    df = pd.read_csv(data_path)
    cols = {c.lower(): c for c in df.columns}
    fc_col = _pick(cols, _FC_COLS)
    p_col = _pick(cols, _P_COLS)
    if fc_col is None or p_col is None:
        raise ValueError("volcano needs a log2 fold-change column and an adjusted-p column")
    gene_col = _pick(cols, _GENE_COLS)
    genes = df[gene_col].astype(str) if gene_col else df.index.astype(str)

    fc_t = float(params.get("fc_threshold", 1.0))
    fdr_t = float(params.get("fdr_threshold", 0.05))
    top_n = int(params.get("top_n", 10))
    y_cut = -math.log10(fdr_t) if fdr_t > 0 else 0.0

    lfc = df[fc_col].to_numpy(dtype=float)
    padj = df[p_col].to_numpy(dtype=float)
    nlp = -np.log10(np.clip(padj, 1e-300, 1.0))
    keep = np.isfinite(lfc) & np.isfinite(nlp)

    up, down, ns = ([], []), ([], []), ([], [])
    for x, y, ok in zip(lfc, nlp, keep):
        if not ok:
            continue
        bucket = up if (x >= fc_t and y >= y_cut) else down if (x <= -fc_t and y >= y_cut) else ns
        bucket[0].append(round(float(x), 4))
        bucket[1].append(round(float(y), 4))

    labels = []
    if top_n > 0:
        sig = np.where(keep & (np.abs(lfc) >= fc_t) & (nlp >= y_cut))[0]
        order = sig[np.argsort(nlp[sig])[::-1]][:top_n]
        labels = [(round(float(lfc[i]), 4), round(float(nlp[i]), 4), str(genes.iloc[i])) for i in order]

    return _assemble(up, down, ns, labels, fc_t, y_cut, "Volcano plot")


def _pick(cols: dict, candidates: list[str]):
    for cand in candidates:
        if cand in cols:
            return cols[cand]
    return None
