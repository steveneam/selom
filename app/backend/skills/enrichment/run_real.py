"""Real over-representation engine — hypergeometric test + BH FDR.

License-clean by construction: the enrichment math is implemented here against the
bundled ``gene_sets.json`` (a GO/Reactome sample), so there is no gseapy/MSigDB
dependency (DECISIONS.md #9 / RISKS.md #6).

Input: a CSV carrying a gene column (e.g. a DE gene list). The background is the
union of all genes across the bundled sets. Emits the dotplot spec in ``run``.
"""

import json
import pathlib

from skills.enrichment.run import dotplot_spec

_GENE_COLS = ["gene", "genes", "symbol", "gene_name", "gene_symbol", "geneid", "gene_id", "feature", "names", "id"]
_FC_COLS = ["log2foldchange", "log2fc", "logfc", "log2_fold_change", "avg_log2fc"]
_P_COLS = ["padj", "adj.p.val", "fdr", "qvalue", "q.value", "pvals_adj", "pvalue", "pval", "p.value"]


def run(data_path: str, params: dict) -> dict:
    import pandas as pd
    from scipy.stats import hypergeom

    sets = _load_gene_sets()
    background = {g for genes in sets.values() for g in genes}
    bg_size = len(background)

    df = pd.read_csv(data_path)
    cols = {c.lower(): c for c in df.columns}
    gene_col = next((c for c in df.columns if c.lower() in _GENE_COLS), None)
    # If the input is a full DE table (has an FDR column), derive the query from the
    # SIGNIFICANT rows; a bare/pre-filtered gene list (no FDR column) is used as-is.
    fdr_col = next((cols[c] for c in _P_COLS if c in cols), None)
    fc_col = next((cols[c] for c in _FC_COLS if c in cols), None)
    sub = df
    if fdr_col is not None:
        sub = sub[pd.to_numeric(sub[fdr_col], errors="coerce") <= float(params.get("fdr_threshold", 0.05))]
        fc_t = float(params.get("fc_threshold", 0.0))
        if fc_col is not None and fc_t > 0:
            sub = sub[pd.to_numeric(sub[fc_col], errors="coerce").abs() >= fc_t]
    query_series = sub[gene_col] if gene_col is not None else sub.iloc[:, 0]
    query = {str(g).upper() for g in query_series} & background
    n_query = len(query)

    rows = []
    for name, genes in sets.items():
        members = set(genes) & background
        k = len(query & members)
        if k == 0 or n_query == 0:
            continue
        # P(X >= k) for X ~ Hypergeometric(bg_size, |members|, n_query).
        p = float(hypergeom.sf(k - 1, bg_size, len(members), n_query))
        rows.append({"pathway": name, "overlap": k, "set_size": len(members), "p": p})

    rows = _benjamini_hochberg(rows)
    rows.sort(key=lambda r: r["padj"])
    rows = rows[: int(params["top_n"])]

    if not rows:  # nothing overlapped the bundled sets — return an honest empty plot.
        return dotplot_spec([], [], [], "Pathway enrichment (no overlap)")

    import math

    pathways = [r["pathway"] for r in rows]
    nlp = [round(-math.log10(max(r["padj"], 1e-300)), 3) for r in rows]
    overlap = [r["overlap"] for r in rows]
    return dotplot_spec(pathways, nlp, overlap, "Pathway enrichment (GO)")


def _load_gene_sets() -> dict:
    # Prefer the full GO library (scripts/build_gene_sets.py) when present; otherwise
    # fall back to the small committed sample so the skill still runs out of the box.
    here = pathlib.Path(__file__).parent
    path = here / "gene_sets_go.json"
    if not path.exists():
        path = here / "gene_sets.json"
    raw = json.loads(path.read_text())
    return {k: [g.upper() for g in v] for k, v in raw.items() if not k.startswith("_")}


def _benjamini_hochberg(rows: list[dict]) -> list[dict]:
    """Attach a BH-adjusted ``padj`` to each row (in place) and return it."""
    m = len(rows)
    if m == 0:
        return rows
    order = sorted(range(m), key=lambda i: rows[i]["p"])
    prev = 1.0
    for rank, idx in enumerate(reversed(order), start=1):
        i = m - rank + 1  # 1-based rank from the largest p downward
        adj = min(prev, rows[idx]["p"] * m / i)
        rows[idx]["padj"] = adj
        prev = adj
    return rows
