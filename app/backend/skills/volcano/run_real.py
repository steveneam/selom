"""Real volcano engine — reads a DE results CSV and plots it.

Column detection is tolerant of the common DE-tool outputs (DESeq2, edgeR/limma,
scanpy): a fold-change column, an adjusted-p column, and a gene-id column (or the
frame index). Emits the same spec shape as the stub via ``run._assemble``.
"""

import math

from engine.columns import GENE, override_column, resolve_significance
from engine.vocab import DE_LOGFC_SYNONYMS
from skills.volcano.run import _assemble


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd

    df = pd.read_csv(data_path)
    cols = {str(c).strip().lower(): c for c in df.columns}
    # User column-override (the AI map_columns action / a hand-set override): a mapped, EXISTING
    # column wins over synonym auto-detection, so a non-standard-named fold-change/significance/gene
    # column the shared synonym sets miss is still read. Recorded in provenance → reproduces with no AI.
    ov = params.get("_column_override")
    fc_col = override_column(ov, "logFC", df.columns) or _pick(cols, DE_LOGFC_SYNONYMS)
    # Significance: ADJUSTED tier first (engine.columns.resolve_significance). `p_adjusted` is False
    # only when the table carries no corrected column at all — then the y-axis title and the table's
    # column name say "raw p" instead of claiming a Benjamini-Hochberg value the data doesn't hold.
    p_col, p_adjusted = resolve_significance(ov, df.columns, cols)
    if fc_col is None or p_col is None:
        raise ValueError("volcano needs a log2 fold-change column and a p-value column")
    gene_col = override_column(ov, "gene", df.columns) or _pick(cols, GENE)
    # Always a Series (positional-aligned with the row arrays below) so the .iloc / .str reads later
    # work whether the labels come from a gene column or the frame index — a bare Index has no .iloc.
    genes = df[gene_col].astype(str) if gene_col else pd.Series(df.index.astype(str))

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

    spec = _assemble(up, down, ns, labels, fc_t, y_cut, "Volcano plot", highlight=highlight,
                     adjusted=p_adjusted)
    # Statistics node (Pillar 1): the full DE table the figure was drawn from — the
    # figure keeps only the plotted points + top-N labels, so this carries the real values.
    from skills._table import de_table

    spec["table"] = de_table(list(genes), lfc, padj, fc_t=fc_t, fdr_t=fdr_t, adjusted=p_adjusted)
    return spec


def _parse_panel(raw) -> set[str]:
    """A gene-set highlight panel: comma/space/newline-separated symbols -> uppercased set."""
    import re

    return {tok.upper() for tok in re.split(r"[,\s]+", str(raw or "").strip()) if tok}


def _pick(cols: dict, synonyms) -> str | None:
    """First column whose lower/stripped name CONTAINS a synonym (synonyms in priority order).

    Substring match, single-sourced from :mod:`engine.vocab` / :mod:`engine.columns` — the same
    header semantics the engine's D1 data-contract gate and role resolver use, so a header the gate
    recognizes as a fold-change / significance / gene column is the same one the runner reads (no
    forked vocabulary — restructure WS3.1). ``cols`` is ``{lower-stripped: original}`` in column
    order, so a tie between two synonym-matching columns resolves to the earlier column."""
    for syn in synonyms:
        for low, orig in cols.items():
            if syn in low:
                return orig
    return None
