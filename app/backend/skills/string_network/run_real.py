"""Real string_network engine — live STRING PPI network for a gene list.

Posts the input genes to the STRING REST API (string-db.org, /api/json/network), builds the
returned interaction graph, lays it out with networkx, and renders an editable Plotly
node-link. Nodes are coloured by log2 fold change when the input has one, else by degree.

Live API (same posture as the ``pathway``/Reactome skill): STRING data is CC BY 4.0
(attributed in the methods text). It needs the network — a request failure raises a clear
error rather than silently faking a result (the dependency-free ``run.py`` stub is only
selected via SELOM_SKILLS_ENGINE, never as a network fallback).
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from engine.columns import GENE, override_column, resolve_significance
from engine.vocab import DE_LOGFC_SYNONYMS
from skills._plotly import jsonable
from skills.string_network.run import network_spec

_API = "https://string-db.org/api/json/network"
_TIMEOUT = 60


def _pick(cols: dict, synonyms) -> str | None:
    """First column whose lower/stripped name CONTAINS a synonym (synonyms in priority order).
    Substring match, single-sourced from :mod:`engine.vocab` / :mod:`engine.columns` — the same
    header semantics the engine's D1 gate uses, so no forked vocabulary (restructure WS3.1)."""
    for syn in synonyms:
        for low, orig in cols.items():
            if syn in low:
                return orig
    return None


def _query_pairs(pd, data_path: str, params: dict):
    """({GENE: log2FC}, has_fc) from a gene list or full DE table — filter to significant
    rows when an FDR column is present; log2FC defaults to 0 when no FC column exists."""
    df = pd.read_csv(data_path)
    cols = {str(c).strip().lower(): c for c in df.columns}
    ov = params.get("_column_override")
    gene_col = override_column(ov, "gene", df.columns) or _pick(cols, GENE)
    # Significance: ADJUSTED tier first (engine.columns.resolve_significance) — the query set is
    # defined on the corrected value. This skill draws no p-axis of its own, so the raw-p
    # fallback is surfaced to the user by the `raw_pvalues_only` QC flag (engine/qc.py) rather
    # than a claim here; the tier is deliberately not re-stated.
    fdr_col, _tier_adjusted = resolve_significance(ov, df.columns, cols)
    fc_col = override_column(ov, "logFC", df.columns) or _pick(cols, DE_LOGFC_SYNONYMS)
    sub = df
    if fdr_col is not None:
        sub = sub[pd.to_numeric(sub[fdr_col], errors="coerce") <= float(params.get("fdr_threshold", 0.05))]
    genes = sub[gene_col] if gene_col is not None else sub.iloc[:, 0]
    if fc_col is not None:
        fcs = pd.to_numeric(sub[fc_col], errors="coerce")
        pairs = {str(g).strip().upper(): float(v) for g, v in zip(genes, fcs) if str(g).strip() and v == v}
        return pairs, True
    return {str(g).strip().upper(): 0.0 for g in genes if str(g).strip()}, False


def run(data_path: str, params: dict) -> dict:
    import networkx as nx
    import pandas as pd

    pairs, has_fc = _query_pairs(pd, data_path, params)
    if not pairs:
        return network_spec([], [], [], "STRING interaction network (no input genes)", "degree")

    genes = list(pairs)[: int(params.get("max_genes", 50))]
    body = urllib.parse.urlencode(
        {
            "identifiers": "\r".join(genes),
            "species": int(params.get("species", 9606)),
            "required_score": int(params.get("required_score", 400)),
            "caller_identity": "selom.bio",
        }
    ).encode()
    req = urllib.request.Request(_API, data=body, headers={"Accept": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            interactions = json.load(resp)
    except urllib.error.URLError as exc:  # network down, DNS, HTTP error, timeout
        raise RuntimeError(f"STRING request failed ({_API}): {exc}") from exc

    g = nx.Graph()
    for it in interactions:
        a, b = it.get("preferredName_A"), it.get("preferredName_B")
        if a and b and a != b:
            g.add_edge(a, b, score=float(it.get("score", 0.0)))
    if g.number_of_nodes() == 0:
        return network_spec([], [], [], "STRING interaction network (no interactions)", "degree")

    pos = nx.spring_layout(g, seed=0, k=2.2 / (g.number_of_nodes() ** 0.5))
    color_mode = "fc" if has_fc else "degree"
    nodes = []
    for n in g.nodes():
        deg = g.degree(n)
        fc = pairs.get(str(n).upper(), 0.0)
        nodes.append(
            {
                "x": round(float(pos[n][0]), 4), "y": round(float(pos[n][1]), 4), "label": str(n),
                "hover": f"{n}<br>{deg} interactions" + (f" · log2FC {fc:+.2f}" if has_fc else ""),
                "size": round(12 + 3 * deg ** 0.5, 1),
                "color": float(fc if has_fc else deg),
            }
        )

    edge_x: list = []
    edge_y: list = []
    for u, v in g.edges():
        edge_x += [round(float(pos[u][0]), 4), round(float(pos[v][0]), 4), None]
        edge_y += [round(float(pos[u][1]), 4), round(float(pos[v][1]), 4), None]
    return jsonable(network_spec(nodes, edge_x, edge_y, "STRING interaction network", color_mode))
