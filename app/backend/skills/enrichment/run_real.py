"""Real over-representation engine — hypergeometric test + BH FDR.

License-clean by construction: the enrichment math is implemented here against the
bundled ``gene_sets.json`` (a GO/Reactome sample), so there is no gseapy/MSigDB
dependency (DECISIONS.md #9 / RISKS.md #6).

Input: a CSV carrying a gene column (e.g. a DE gene list). The background is the
union of all genes across the bundled sets. Emits the dotplot spec in ``run``.
"""

from skills.enrichment.run import dotplot_spec, dotplot_split_spec

# The ``gene_sets`` param selects which license-clean library the ORA scores against
# (gene-set builder Phase A · DECISIONS #11). Aliases keep the old default working:
# the seed/default ``GO_Reactome`` still resolves to the full GO library.
_SOURCE_ALIASES = {
    "go": "go", "go_reactome": "go", "gene ontology": "go",
    "wikipathways": "wikipathways", "wp": "wikipathways",
    "curated": "curated", "selom": "curated",
    "all": "all",
}

# Priority order: prefer a clean gene-symbol column over an id column, so a biomaRt-style
# DE table (clean ``external_gene_name`` alongside a composite ``GeneID`` = ``ENSG…~SYMBOL``)
# resolves to the mappable symbols rather than the unmappable composite id.
_GENE_COLS = ["external_gene_name", "gene_symbol", "gene_name", "symbol", "gene", "genes",
              "feature", "geneid", "gene_id", "ensembl_gene_id", "entrezgene_id", "names", "id"]
_FC_COLS = ["log2foldchange", "log2fc", "logfc", "log2_fold_change", "avg_log2fc"]
_P_COLS = ["padj", "adj.p.val", "fdr", "qvalue", "q.value", "pvals_adj", "pvalue", "pval", "p.value"]


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    sets = _load_gene_sets(params.get("gene_sets"))
    background = {g for genes in sets.values() for g in genes}

    df = pd.read_csv(data_path)
    cols = {c.lower(): c for c in df.columns}
    gene_col = next((cols[name] for name in _GENE_COLS if name in cols), None)
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

    top_n = int(params["top_n"])
    genes_series = sub[gene_col] if gene_col is not None else sub.iloc[:, 0]

    # Up/down split: score the up- and down-regulated significant genes SEPARATELY and draw
    # them as a diverging dotplot (Suppl Fig 6 / 5C). Needs a fold-change column to assign
    # direction — erroring is more honest than silently collapsing to a combined plot.
    if str(params.get("direction") or "combined").lower() == "split":
        if fc_col is None:
            raise ValueError(
                "enrichment up/down split needs a fold-change column "
                "(e.g. log2FoldChange) to assign direction"
            )
        fc_vals = pd.to_numeric(sub[fc_col], errors="coerce")
        up_q = {str(g).upper() for g, v in zip(genes_series, fc_vals) if pd.notna(v) and v > 0} & background
        down_q = {str(g).upper() for g, v in zip(genes_series, fc_vals) if pd.notna(v) and v < 0} & background
        up_rows = _ora(up_q, sets, background, top_n)
        down_rows = _ora(down_q, sets, background, top_n)
        if not up_rows and not down_rows:
            return dotplot_spec([], [], [], "Pathway enrichment (no overlap)")
        return dotplot_split_spec(up_rows, down_rows, "Pathway enrichment — up/down split")

    query = {str(g).upper() for g in genes_series} & background
    rows = _ora(query, sets, background, top_n)
    if not rows:  # nothing overlapped the bundled sets — return an honest empty plot.
        return dotplot_spec([], [], [], "Pathway enrichment (no overlap)")
    pathways = [r["pathway"] for r in rows]
    nlp = [r["nlp"] for r in rows]
    overlap = [r["overlap"] for r in rows]
    return dotplot_spec(pathways, nlp, overlap, "Pathway enrichment (GO)")


def _ora(query: set, sets: dict, background: set, top_n: int) -> list[dict]:
    """Hypergeometric over-representation of ``query`` against ``sets`` with BH correction.
    Returns the top_n rows ``{pathway, overlap, set_size, p, padj, nlp}`` ordered most- to
    least-significant. Empty when the query is empty or nothing overlaps the bundled sets."""
    import math

    from scipy.stats import hypergeom

    bg_size = len(background)
    n_query = len(query)
    if n_query == 0:
        return []
    rows = []
    for name, genes in sets.items():
        members = set(genes) & background
        k = len(query & members)
        if k == 0:
            continue
        # P(X >= k) for X ~ Hypergeometric(bg_size, |members|, n_query).
        p = float(hypergeom.sf(k - 1, bg_size, len(members), n_query))
        rows.append({"pathway": name, "overlap": k, "set_size": len(members), "p": p})
    rows = _benjamini_hochberg(rows)
    rows.sort(key=lambda r: r["padj"])
    rows = rows[:top_n]
    for r in rows:
        r["nlp"] = round(-math.log10(max(r["padj"], 1e-300)), 3)
    return rows


def _load_gene_sets(source_param=None) -> dict:
    # Resolve the requested source ('go' default / 'wikipathways' / 'curated' / 'all') and
    # load it from the unified gene-set library (gene_sets/library.py) — the same corpus
    # the "Gene Sets" surface browses. GO still falls back to the committed sample when the
    # full library has not been built, so the skill runs out of the box.
    from gene_sets.library import load_collection

    source = _SOURCE_ALIASES.get(str(source_param or "").strip().lower(), "go")
    return load_collection(source)


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
