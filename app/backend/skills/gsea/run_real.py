"""Real GSEA engine — weighted-KS running enrichment over a ranked DE table.

Ranks genes by a signed metric (log2FC or a statistic), walks the list accumulating
a weighted hit/miss running sum (Subramanian 2005), and reports the enrichment score
(max deviation), the leading-edge hits, and a permutation NES + empirical p. Pure
numpy/pandas — no gseapy — matching Selom's in-house ORA. Shares the figure with the
stub via ``run._assemble``.
"""

import re

from skills.gsea.run import _assemble

_METRIC_COLS = ["log2foldchange", "log2fc", "logfc", "log2_fold_change", "avg_log2fc",
                "stat", "score", "t", "signed_rank", "metric"]
_GENE_COLS = ["external_gene_name", "gene_symbol", "gene_name", "symbol", "gene", "genes",
              "feature", "geneid", "gene_id", "names", "id"]
_MAX_PLOT = 800  # downsample the curve/metric to keep the spec light


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd

    df = pd.read_csv(data_path)
    cols = {c.lower(): c for c in df.columns}
    metric_col = _pick(cols, _METRIC_COLS)
    if metric_col is None:
        raise ValueError("gsea needs a ranking metric column (log2 fold-change or a signed statistic)")
    gene_col = _pick(cols, _GENE_COLS)
    genes = (df[gene_col] if gene_col else df.index.to_series()).astype(str).str.upper()
    metric = pd.to_numeric(df[metric_col], errors="coerce")

    ok = metric.notna().to_numpy()
    g = genes.to_numpy()[ok]
    m = metric.to_numpy(dtype=float)[ok]
    order = np.argsort(m)[::-1]            # rank descending by metric
    g, m = g[order], m[order]

    panel = _parse_panel(params.get("gene_set", ""))
    if not panel:
        raise ValueError("gsea needs a gene_set — the set members to test for enrichment")
    hit = np.fromiter((x in panel for x in g), dtype=bool, count=g.size)
    k = int(hit.sum())
    if k < 2:
        raise ValueError(f"only {k} gene_set members found in the ranked list (need >=2)")

    p = float(params.get("weight", 1.0))
    running, es, peak = _running_es(m, hit, p, np)
    nes, pval = _nes_p(m, k, p, es, int(params.get("n_perm", 1000)), np)

    n = m.size
    step = max(1, n // _MAX_PLOT)
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    x_plot = [i + 1 for i in idx]
    y_es = [round(float(running[i]), 4) for i in idx]
    y_m = [round(float(m[i]), 4) for i in idx]
    hit_x = [int(i) + 1 for i in np.where(hit)[0]]

    set_name = str(params.get("set_name", "Gene set")) or "Gene set"
    return _assemble(x_plot, y_es, int(peak) + 1, round(float(es), 4),
                     hit_x, x_plot, y_m, round(float(nes), 4), float(pval), set_name)


def _running_es(metric, hit, p, np):
    w = np.abs(metric) ** p
    hit_w = w * hit
    tot = hit_w.sum() or 1.0
    p_hit = np.cumsum(hit_w) / tot
    n_miss = max(int((~hit).sum()), 1)
    p_miss = np.cumsum((~hit).astype(float)) / n_miss
    running = p_hit - p_miss
    peak = int(np.argmax(np.abs(running)))
    return running, float(running[peak]), peak


def _nes_p(metric, k, p, es, n_perm, np):
    if n_perm <= 0:
        return (es, 1.0)
    w = np.abs(metric) ** p
    n = metric.size
    rng = np.random.default_rng(0)
    null = np.empty(n_perm)
    for i in range(n_perm):
        h = np.zeros(n, dtype=bool)
        h[rng.choice(n, size=k, replace=False)] = True
        hit_w = w * h
        tot = hit_w.sum() or 1.0
        r = np.cumsum(hit_w) / tot - np.cumsum((~h).astype(float)) / (n - k)
        null[i] = r[np.argmax(np.abs(r))]
    same = null[(null >= 0) == (es >= 0)]
    denom = float(np.abs(same).mean()) if same.size else (float(np.abs(null).mean()) or 1.0)
    nes = es / denom if denom else 0.0
    if es >= 0:
        pval = (int(np.sum(null >= es)) + 1) / (n_perm + 1)
    else:
        pval = (int(np.sum(null <= es)) + 1) / (n_perm + 1)
    return float(nes), float(pval)


def _parse_panel(raw) -> set:
    return {tok.upper() for tok in re.split(r"[,\s]+", str(raw or "").strip()) if tok}


def _pick(cols: dict, candidates: list):
    for cand in candidates:
        if cand in cols:
            return cols[cand]
    return None
