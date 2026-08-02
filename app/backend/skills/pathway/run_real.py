"""Real pathway engine — live Reactome over-representation drawn as a fold-change map.

Sends the input gene list + log2 fold changes to the Reactome **Analysis Service**
(over-representation with identifier projection to human orthologs), keeps the top-N
enriched pathways, fetches the Reactome **event hierarchy** once to wire parent->child
edges among them (transitive-reduced, like `go_graph`), and lays them out as an editable
Plotly node-link coloured by each pathway's mean log2 fold change.

Live API (option C, docs/records/p1-skills-scope.md): Reactome data is open (CC0), so this stays
license-clean without gseapy/MSigDB (DECISIONS #9). It needs the network — a request
failure raises a clear error rather than silently faking a result (the dependency-free
``run.py`` stub is only selected via SELOM_SKILLS_ENGINE, never as a network fallback).
"""

import json
import urllib.error
import urllib.request

from engine.columns import normalize, resolve, resolve_significance
from skills.pathway.run import pathway_spec

_BASE = "https://reactome.org"
_ANALYSIS = (
    _BASE + "/AnalysisService/identifiers/projection"
    "?pageSize={n}&page=1&sortBy=ENTITIES_FDR&order=ASC"
)
_HIERARCHY = _BASE + "/ContentService/data/eventsHierarchy/9606"  # Homo sapiens (projection target)
_TIMEOUT = 60
# Reactome sits behind CloudFront, which 403s urllib's default ``Python-urllib/3.x`` UA — so every
# live call failed with a bare "Reactome request failed", measured by the skill smoke matrix
# (docs/skill-coverage/matrix.md). Identify ourselves like a browser, exactly as
# ``scripts/build_gene_sets.py`` already does for the GO downloads.
_UA = "Mozilla/5.0 (Selom pathway skill)"


def _http_json(url: str, body: bytes | None = None):
    headers = {"Content-Type": "text/plain", "Accept": "application/json"} if body else {"Accept": "application/json"}
    headers["User-Agent"] = _UA
    req = urllib.request.Request(url, data=body, headers=headers, method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.load(resp)
    except urllib.error.URLError as exc:  # network down, DNS, HTTP error, timeout
        raise RuntimeError(f"Reactome request failed ({url}): {exc}") from exc


def _query_pairs(pd, data_path: str, params: dict) -> dict:
    """{GENE: log2FC} from a gene list or full DE table — filter to significant rows when
    an FDR column is present (same contract as enrichment/go_graph); fold change is 0 when
    the input carries no FC column (the map then shows enrichment with neutral colour)."""
    df = pd.read_csv(data_path)
    cols = normalize(df.columns)
    ov = params.get("_column_override")
    # One shared resolver (engine.columns.resolve): normalization + override + the role's selection
    # order, gene exact-tier-first so an annotation/count column is never read as the label (A10).
    gene_col = resolve("gene", df.columns, ov, cols=cols)
    # Significance: ADJUSTED tier first (engine.columns.resolve_significance) — the query set is
    # defined on the corrected value. This skill draws no p-axis of its own, so the raw-p
    # fallback is surfaced to the user by the `raw_pvalues_only` QC flag (engine/qc.py) rather
    # than a claim here; the tier is deliberately not re-stated.
    fdr_col, _tier_adjusted = resolve_significance(ov, df.columns, cols)
    fc_col = resolve("logFC", df.columns, ov, cols=cols)
    sub = df
    if fdr_col is not None:
        sub = sub[pd.to_numeric(sub[fdr_col], errors="coerce") <= float(params.get("fdr_threshold", 0.05))]
        fc_t = float(params.get("fc_threshold", 0.0))
        if fc_col is not None and fc_t > 0:
            sub = sub[pd.to_numeric(sub[fc_col], errors="coerce").abs() >= fc_t]
    genes = sub[gene_col] if gene_col is not None else sub.iloc[:, 0]
    if fc_col is not None:
        fcs = pd.to_numeric(sub[fc_col], errors="coerce")
        return {str(g).strip().upper(): float(v) for g, v in zip(genes, fcs) if str(g).strip() and v == v}
    return {str(g).strip().upper(): 0.0 for g in genes if str(g).strip()}


def _ancestor_map(hierarchy: list) -> dict:
    """stId -> set(all ancestor stIds) from the Reactome event forest. A pathway can
    appear under several parents, so ancestors accumulate across every appearance."""
    ancestors: dict[str, set] = {}

    def walk(node: dict, path: list):
        sid = node.get("stId")
        if sid is None:
            return
        ancestors.setdefault(sid, set()).update(path)
        for child in node.get("children", []) or []:
            walk(child, path + [sid])

    for top in hierarchy:
        walk(top, [])
    return ancestors


def run(data_path: str, params: dict) -> dict:
    import networkx as nx
    import pandas as pd

    pairs = _query_pairs(pd, data_path, params)
    if not pairs:
        return pathway_spec([], [], [], "Reactome pathway enrichment (no input genes)")

    top_n = int(params["top_n"])
    body = ("#Gene\tFC\n" + "\n".join(f"{g}\t{v}" for g, v in pairs.items())).encode()
    result = _http_json(_ANALYSIS.format(n=top_n), body)
    pathways = result.get("pathways", [])[:top_n]
    if not pathways:
        return pathway_spec([], [], [], "Reactome pathway enrichment (no overlap)")

    ancestors = _ancestor_map(_http_json(_HIERARCHY))

    selected = {p["stId"] for p in pathways}
    anc_in_sel = {sid: [a for a in ancestors.get(sid, ()) if a in selected] for sid in selected}
    # Transitive reduction: child -> a only when a is a *nearest* selected ancestor.
    edges = []
    for child, ancs in anc_in_sel.items():
        for a in ancs:
            if not any(a in ancestors.get(b, set()) for b in ancs if b != a):
                edges.append((child, a))

    g = nx.DiGraph()
    g.add_nodes_from(selected)
    g.add_edges_from(edges)
    pos = nx.spring_layout(g, seed=0, k=1.8 / (len(selected) ** 0.5))

    nodes = []
    for p in pathways:
        sid, e = p["stId"], p["entities"]
        fc = float(e["exp"][0]) if e.get("exp") else 0.0
        found, total, fdr = int(e["found"]), int(e["total"]), float(e["fdr"])
        name = p["name"]
        label = name if len(name) <= 28 else name[:27] + "…"
        nodes.append({
            "x": float(pos[sid][0]), "y": float(pos[sid][1]),
            "label": label,
            "hover": f"{name}<br>{sid} · {found}/{total} genes<br>FDR {fdr:.1e} · mean log2FC {fc:+.2f}",
            "size": round(12 + 2 * found ** 0.5, 1),
            "color": fc,
        })

    edge_x, edge_y = [], []
    for u, v in edges:
        edge_x += [float(pos[u][0]), float(pos[v][0]), None]
        edge_y += [float(pos[u][1]), float(pos[v][1]), None]
    return pathway_spec(nodes, edge_x, edge_y, "Reactome pathway enrichment")
