"""Build a license-clean GO gene-set library for the `enrichment` skill (dev-time).

DECISIONS #10 / docs/records/p1-skills-scope.md (Decision #1A): replace the 10-set / 102-gene
sample with real coverage from a primary, openly-licensed source. The GO annotation file
(GAF) is **gene-symbol keyed**, which matches Selom's inputs (rpgrip1 var_names, EYG_28
GeneID) directly — no ID mapping needed.

Pipeline (one-off; not on the runtime hot path):
  1. download go-basic.obo + goa_human.gaf.gz (cached under D:/selom-data/genesets/raw)
  2. parse the ontology (obonet) -> is_a + part_of ancestor closure
  3. parse the GAF -> gene symbol -> directly-annotated GO terms (drop NOT qualifiers)
  4. propagate each annotation up to all ancestors (true-path rule)
  5. invert -> GO term -> {symbols}, keep sets of size [MIN, MAX], tag "GO:<BP|MF|CC>: name"
  6. write app/backend/skills/enrichment/gene_sets_go.json (gitignored; enrichment prefers it)

Run (obonet is dev-only, pulled transiently — never a runtime dep):
    uv run --with obonet --directory app/backend python scripts/build_gene_sets.py

GO data is CC-BY 4.0 (open) — license-clean, unlike gseapy/MSigDB (DECISIONS #9).
"""

from __future__ import annotations

import gzip
import json
import pathlib
import shutil
import urllib.request

OBO_URL = "https://current.geneontology.org/ontology/go-basic.obo"
GAF_URL = "https://current.geneontology.org/annotations/goa_human.gaf.gz"
CACHE = pathlib.Path("D:/selom-data/genesets/raw")
OUT = pathlib.Path(__file__).resolve().parent.parent / "skills" / "enrichment" / "gene_sets_go.json"
DAG_OUT = OUT.parent.parent / "go_graph" / "go_dag.json"  # id -> {name, ns, ancestors, genes}

MIN_SET, MAX_SET = 10, 500            # drop giant near-root terms + tiny noise
_NS = {"biological_process": "BP", "molecular_function": "MF", "cellular_component": "CC"}
_PROP_EDGES = {"is_a", "part_of"}     # standard GO enrichment propagation


def _download(url: str, dest: pathlib.Path) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached: {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
        return dest
    print(f"  downloading {url} ...")
    # CloudFront 403s the default urllib UA — send a browser-like one (curl works too).
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Selom gene-set builder)"})
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as out:  # noqa: S310 (trusted GO URL)
        shutil.copyfileobj(resp, out)
    print(f"  saved {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
    return dest


def _ancestors(graph) -> dict:
    """term -> set(ancestor terms) over is_a + part_of (the term itself included)."""
    import networkx as nx

    keep = nx.MultiDiGraph()
    keep.add_nodes_from(graph.nodes(data=True))
    for u, v, key in graph.edges(keys=True):
        if key in _PROP_EDGES:
            keep.add_edge(u, v)
    out = {}
    for node in keep.nodes:
        anc = nx.descendants(keep, node)  # obonet edges point child -> parent
        anc.add(node)
        out[node] = anc
    return out


def main() -> None:
    import obonet

    obo = _download(OBO_URL, CACHE / "go-basic.obo")
    gaf = _download(GAF_URL, CACHE / "goa_human.gaf.gz")

    print("parsing ontology ...")
    graph = obonet.read_obo(str(obo))
    anc = _ancestors(graph)

    print("parsing annotations + propagating ...")
    term_genes: dict[str, set] = {}
    seen_ann = 0
    with gzip.open(gaf, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("!"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 9:
                continue
            symbol, qualifier, go_id = f[2], f[3], f[4]
            if "NOT" in qualifier or not symbol or go_id not in anc:
                continue
            seen_ann += 1
            for term in anc[go_id]:
                term_genes.setdefault(term, set()).add(symbol)

    sets = {}
    for term, genes in term_genes.items():
        if not (MIN_SET <= len(genes) <= MAX_SET):
            continue
        node = graph.nodes.get(term, {})
        ns = _NS.get(node.get("namespace", ""))
        name = node.get("name")
        if not ns or not name:
            continue
        sets[f"GO:{ns}: {name}"] = sorted(genes)

    sets["_provenance"] = (
        "GO gene-sets from go-basic.obo + goa_human.gaf (current.geneontology.org), "
        "CC-BY 4.0; is_a+part_of propagated; sizes 10-500. Built by scripts/build_gene_sets.py."
    )
    OUT.write_text(json.dumps(sets))
    copy = CACHE.parent / "gene_sets_go.json"
    copy.write_text(json.dumps(sets))

    # GO DAG for the go_graph skill: kept terms keyed by GO id, with the ancestor closure
    # (is_a+part_of) so the skill can draw the hierarchy among enriched terms + run ORA.
    dag = {}
    for term, genes in term_genes.items():
        if not (MIN_SET <= len(genes) <= MAX_SET):
            continue
        node = graph.nodes.get(term, {})
        ns = _NS.get(node.get("namespace", ""))
        if not ns or not node.get("name"):
            continue
        dag[term] = {
            "name": node["name"],
            "ns": ns,
            "ancestors": sorted(anc[term] - {term}),
            "genes": sorted(genes),
        }
    DAG_OUT.parent.mkdir(parents=True, exist_ok=True)
    DAG_OUT.write_text(json.dumps(dag))
    (CACHE.parent / "go_dag.json").write_text(json.dumps(dag))

    n = len([k for k in sets if not k.startswith("_")])
    bg = {g for k, v in sets.items() if not k.startswith("_") for g in v}
    by_ns = {}
    for k in sets:
        if k.startswith("_"):
            continue
        tag = k.split(":", 2)[1].strip()
        by_ns[tag] = by_ns.get(tag, 0) + 1
    print(f"\nBUILT {n} GO sets ({by_ns}); {len(bg)} unique genes; {seen_ann} annotations propagated")
    print(f"  wrote -> {OUT} ({OUT.stat().st_size/1e6:.1f} MB)  + copy {copy}")
    print(f"  wrote -> {DAG_OUT} ({DAG_OUT.stat().st_size/1e6:.1f} MB, {len(dag)} terms w/ hierarchy)")


if __name__ == "__main__":
    main()
