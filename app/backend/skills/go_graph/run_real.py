"""Real GO-DAG enrichment engine — ORA + the is_a/part_of hierarchy among the hits.

Loads the built go_dag.json (id -> {name, ns, ancestors, genes}; scripts/build_gene_sets.py),
runs over-representation (hypergeometric + Benjamini-Hochberg) of the input gene list /
DE table against it, keeps the top-N terms, and lays them out as a node-link DAG
(networkx) with edges = nearest-selected ancestry (transitive-reduced). License-clean GO
(CC-BY); no gseapy/MSigDB (DECISIONS #9). Falls back to the run.py stub if go_dag.json
hasn't been built (uv run --with obonet ... scripts/build_gene_sets.py).
"""

import json
import math
import pathlib

from skills.go_graph.run import nodelink_spec

# Priority order: prefer a clean gene-symbol column over an id column, so a biomaRt-style
# DE table (clean ``external_gene_name`` alongside a composite ``GeneID`` = ``ENSG…~SYMBOL``)
# resolves to the mappable symbols rather than the unmappable composite id.
_GENE_COLS = ["external_gene_name", "gene_symbol", "gene_name", "symbol", "gene", "genes",
              "feature", "geneid", "gene_id", "ensembl_gene_id", "entrezgene_id", "names", "id"]
_FC_COLS = ["log2foldchange", "log2fc", "logfc", "log2_fold_change", "avg_log2fc"]
_P_COLS = ["padj", "adj.p.val", "fdr", "qvalue", "q.value", "pvals_adj", "pvalue", "pval", "p.value"]


def _load_dag() -> dict:
    return json.loads((pathlib.Path(__file__).parent / "go_dag.json").read_text())


def _query_genes(pd, data_path: str, params: dict, background: set) -> set:
    """Query set from a gene list or full DE table — filter to significant rows when an
    FDR column is present, else use every gene (same contract as the enrichment skill)."""
    df = pd.read_csv(data_path)
    cols = {c.lower(): c for c in df.columns}
    gene_col = next((cols[name] for name in _GENE_COLS if name in cols), None)
    fdr_col = next((cols[c] for c in _P_COLS if c in cols), None)
    fc_col = next((cols[c] for c in _FC_COLS if c in cols), None)
    sub = df
    if fdr_col is not None:
        sub = sub[pd.to_numeric(sub[fdr_col], errors="coerce") <= float(params.get("fdr_threshold", 0.05))]
        fc_t = float(params.get("fc_threshold", 0.0))
        if fc_col is not None and fc_t > 0:
            sub = sub[pd.to_numeric(sub[fc_col], errors="coerce").abs() >= fc_t]
    series = sub[gene_col] if gene_col is not None else sub.iloc[:, 0]
    return {str(g).upper() for g in series} & background


def _benjamini_hochberg(rows: list[dict]) -> list[dict]:
    m = len(rows)
    if not m:
        return rows
    order = sorted(range(m), key=lambda i: rows[i]["p"])
    prev = 1.0
    for rank, idx in enumerate(reversed(order), start=1):
        prev = min(prev, rows[idx]["p"] * m / (m - rank + 1))
        rows[idx]["padj"] = prev
    return rows


def run(data_path: str, params: dict) -> dict:
    import networkx as nx
    import pandas as pd
    from scipy.stats import hypergeom

    dag = _load_dag()
    background = {g for t in dag.values() for g in t["genes"]}
    bg_size = len(background)
    ns_filter = (params.get("namespace") or "").strip().upper()
    query = _query_genes(pd, data_path, params, background)
    n_query = len(query)

    rows = []
    for tid, term in dag.items():
        if ns_filter and term["ns"] != ns_filter:
            continue
        k = len(query.intersection(term["genes"]))
        if k == 0 or n_query == 0:
            continue
        rows.append({"id": tid, "k": k, "p": float(hypergeom.sf(k - 1, bg_size, len(term["genes"]), n_query))})

    rows = _benjamini_hochberg(rows)
    rows.sort(key=lambda r: r["padj"])
    top = rows[: int(params["top_n"])]
    if not top:
        return nodelink_spec([], [], [], "GO enrichment graph (no overlap)")

    selected = {r["id"] for r in top}
    anc_in_sel = {r["id"]: [a for a in dag[r["id"]]["ancestors"] if a in selected] for r in top}

    # Transitive reduction: child -> a only when a is a *nearest* selected ancestor
    # (no other selected ancestor b of the child has a among its own ancestors).
    edges = []
    for child, ancestors in anc_in_sel.items():
        for a in ancestors:
            if not any(a in set(dag[b]["ancestors"]) for b in ancestors if b != a):
                edges.append((child, a))

    g = nx.DiGraph()
    g.add_nodes_from(selected)
    g.add_edges_from(edges)
    pos = nx.spring_layout(g, seed=0, k=1.8 / (len(selected) ** 0.5))

    nlp = {r["id"]: round(-math.log10(max(r["padj"], 1e-300)), 3) for r in top}
    overlap = {r["id"]: r["k"] for r in top}
    nodes = []
    for tid in selected:
        term = dag[tid]
        label = term["name"] if len(term["name"]) <= 28 else term["name"][:27] + "…"
        nodes.append({
            "x": float(pos[tid][0]), "y": float(pos[tid][1]),
            "label": label,
            "hover": f"GO:{term['ns']}: {term['name']}<br>{overlap[tid]} genes · -log10 padj {nlp[tid]}",
            "size": round(12 + 2 * overlap[tid] ** 0.5, 1),
            "color": nlp[tid],
        })

    edge_x, edge_y = [], []
    for u, v in edges:
        edge_x += [float(pos[u][0]), float(pos[v][0]), None]
        edge_y += [float(pos[u][1]), float(pos[v][1]), None]
    return nodelink_spec(nodes, edge_x, edge_y, "GO enrichment graph")
