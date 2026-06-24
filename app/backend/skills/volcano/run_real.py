"""Real volcano engine — reads a DE results CSV and plots it.

Column detection is tolerant of the common DE-tool outputs (DESeq2, edgeR/limma,
scanpy): a fold-change column, an adjusted-p column, and a gene-id column (or the
frame index). Emits the same spec shape as the stub via ``run._assemble``.
"""

import math

from skills.volcano.run import _assemble

_FC_COLS = ["log2foldchange", "log2fc", "logfc", "log2_fold_change", "avg_log2fc"]
_P_COLS = ["padj", "adj.p.val", "fdr", "qvalue", "q.value", "pvals_adj", "pvalue", "pval", "p.value"]
# Priority order: prefer a clean gene-symbol column over an id column, so a biomaRt-style
# DE table (clean ``external_gene_name`` alongside a composite ``GeneID`` = ``ENSG…~SYMBOL``)
# resolves to the mappable symbols rather than the unmappable composite id.
_GENE_COLS = ["external_gene_name", "gene_symbol", "gene_name", "symbol", "gene", "genes",
              "feature", "geneid", "gene_id", "ensembl_gene_id", "entrezgene_id", "names", "id"]


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

    gene_vals = genes.to_numpy()
    up, down, ns = ([], [], []), ([], [], []), ([], [], [])
    for x, y, pj, gene, ok in zip(lfc, nlp, padj, gene_vals, keep):
        if not ok:
            continue
        bucket = up if (x >= fc_t and y >= y_cut) else down if (x <= -fc_t and y >= y_cut) else ns
        bucket[0].append(round(float(x), 4))
        bucket[1].append(round(float(y), 4))
        # Per-point customdata = [gene symbol, adj p] (generalization-spec §H): the labelling
        # substrate + the hover readout. padj is the raw value (not the -log10), formatted on hover.
        bucket[2].append([str(gene), float(pj) if math.isfinite(float(pj)) else None])

    labels = []
    if top_n > 0:
        sig = np.where(keep & (np.abs(lfc) >= fc_t) & (nlp >= y_cut))[0]
        order = sig[np.argsort(nlp[sig])[::-1]][:top_n]
        labels = [(round(float(lfc[i]), 4), round(float(nlp[i]), 4), str(genes.iloc[i])) for i in order]

    # Optional gene-set highlight (applied from the "Gene Sets" surface): mark + label
    # every member of the panel that appears in this DE table, drawn on top.
    highlight = []
    panel = _parse_panel(params.get("highlight", ""))
    if panel:
        gene_upper = genes.str.upper()
        for i in np.where(keep)[0]:
            if str(gene_upper.iloc[i]) in panel:
                highlight.append((round(float(lfc[i]), 4), round(float(nlp[i]), 4), str(genes.iloc[i])))

    spec = _assemble(up, down, ns, labels, fc_t, y_cut, "Volcano plot", highlight=highlight)
    # Statistics node (Pillar 1): the full DE table the figure was drawn from — the
    # figure keeps only the plotted points + top-N labels, so this carries the real values.
    from skills._table import de_table

    spec["table"] = de_table(list(genes), lfc, padj, fc_t=fc_t, fdr_t=fdr_t)
    return spec


def _parse_panel(raw) -> set[str]:
    """A gene-set highlight panel: comma/space/newline-separated symbols -> uppercased set."""
    import re

    return {tok.upper() for tok in re.split(r"[,\s]+", str(raw or "").strip()) if tok}


def _pick(cols: dict, candidates: list[str]):
    for cand in candidates:
        if cand in cols:
            return cols[cand]
    return None
