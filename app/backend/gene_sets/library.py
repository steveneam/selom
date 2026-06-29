"""Unified, license-clean gene-set library over Selom's owned/open corpus.

Phase A of the gene-set builder (docs/records/gene-set-builder-design.md §4 · DECISIONS #11):
surface the gene sets Selom already owns or that are openly licensed as a single
browsable/searchable corpus, and resolve a chosen source as an ORA library the
`enrichment` skill scores against. **Open-core only** — no gseapy/MSigDB (DECISIONS #9).

Sources (all license-clean):
  - go            CC-BY-4.0     skills/enrichment/gene_sets_go.json  (build_gene_sets.py; sample fallback)
  - wikipathways  CC0-1.0       gene_sets/corpus/gene_sets_wikipathways.json  (build_wikipathways.py)
  - curated       Selom (owned) gene_sets/corpus/gene_sets_curated.json  (canonical literature panels)

Every corpus file shares one on-disk shape so the loader is source-agnostic:
``{"<set name>": ["SYMBOL", ...], "_provenance": "..."}`` (underscore keys = metadata).
"""

from __future__ import annotations

import functools
import hashlib
import json
import pathlib

_BACKEND = pathlib.Path(__file__).resolve().parent.parent
_ENRICHMENT = _BACKEND / "skills" / "enrichment"
_DATA = pathlib.Path(__file__).resolve().parent / "corpus"

# source key -> metadata; ``files`` is tried in order (first present wins), so the GO
# source uses the full library when built and the committed sample otherwise.
SOURCES: dict[str, dict] = {
    "go": {
        "label": "Gene Ontology",
        "license": "CC-BY-4.0",
        "files": [_ENRICHMENT / "gene_sets_go.json", _ENRICHMENT / "gene_sets.json"],
    },
    "wikipathways": {
        "label": "WikiPathways",
        "license": "CC0-1.0",
        "files": [_DATA / "gene_sets_wikipathways.json"],
    },
    "curated": {
        "label": "Selom curated",
        "license": "Selom (owned)",
        "files": [_DATA / "gene_sets_curated.json"],
    },
    # Reference panels derived from CMRI Fidelle curation + published resources. Uses the
    # RICH per-set format ({genes, license, attribution}) so each set cites its own source
    # (DECISIONS #11 #3 clarification, owner 2026-06-14: attribute, don't claim/exclude).
    "reference": {
        "label": "Reference panels",
        "license": "Per set (attributed)",
        "files": [_DATA / "gene_sets_reference.json"],
    },
}


def _entry_genes(value) -> tuple[str, ...]:
    """Members from a corpus entry — a flat ``[genes]`` list or a rich ``{genes, ...}`` dict."""
    genes = value["genes"] if isinstance(value, dict) else value
    return tuple(str(g).upper() for g in genes)


@functools.lru_cache(maxsize=None)
def _load_source(source: str) -> dict[str, tuple[str, ...]]:
    """``name -> (SYMBOL, ...)`` for one source; first present file wins, else ``{}``.

    Cached — the GO library is ~7.7k sets / 5 MB, so it is parsed at most once.
    Tuples keep the cached value immutable (callers must not mutate it in place).
    Accepts both the flat list shape and the rich per-set dict shape.
    """
    meta = SOURCES.get(source)
    if not meta:
        return {}
    for path in meta["files"]:
        if path.exists():
            raw = json.loads(path.read_text())
            return {k: _entry_genes(v) for k, v in raw.items() if not k.startswith("_")}
    return {}


@functools.lru_cache(maxsize=None)
def _overrides(source: str) -> dict[str, dict]:
    """Per-set ``{license?, attribution?}`` for sources whose file uses the rich format."""
    meta = SOURCES.get(source)
    if not meta:
        return {}
    for path in meta["files"]:
        if path.exists():
            raw = json.loads(path.read_text())
            out: dict[str, dict] = {}
            for k, v in raw.items():
                if k.startswith("_") or not isinstance(v, dict):
                    continue
                ov = {f: v[f] for f in ("license", "attribution") if v.get(f)}
                if ov:
                    out[k] = ov
            return out
    return {}


def _set_id(source: str, name: str) -> str:
    """Stable, URL-safe id for a set (source + a hash of its name)."""
    return f"{source}:{hashlib.sha1(name.encode('utf-8')).hexdigest()[:10]}"


@functools.lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    """``id -> card`` over every available source. Cached once; cards omit gene lists."""
    idx: dict[str, dict] = {}
    for key, meta in SOURCES.items():
        overrides = _overrides(key)
        for name, genes in _load_source(key).items():
            ov = overrides.get(name, {})
            sid = _set_id(key, name)
            card = {
                "id": sid,
                "name": name,
                "source": key,
                "source_label": meta["label"],
                "license": ov.get("license", meta["license"]),
                "size": len(genes),
                "sample_genes": list(genes[:8]),
            }
            if ov.get("attribution"):
                card["attribution"] = ov["attribution"]
            idx[sid] = card
    return idx


def list_sources() -> list[dict]:
    """Each available source with its label, license and set count (present files only)."""
    out = []
    for key, meta in SOURCES.items():
        sets = _load_source(key)
        if not sets:
            continue
        out.append({"key": key, "label": meta["label"], "license": meta["license"], "n_sets": len(sets)})
    return out


def search(q: str = "", source: str | None = None, limit: int = 50) -> list[dict]:
    """Ranked candidate cards. Empty query = a useful browse (curated first, then by name).

    Match tiers (name): exact > prefix > substring; ties broken by shorter name. This is
    the same tiered idea as the FE command palette — keeps results on-target, no noise.
    """
    items = list(_index().values())
    if source:
        items = [it for it in items if it["source"] == source]

    q = (q or "").strip().lower()
    if not q:
        items.sort(key=lambda it: (it["source"] != "curated", it["name"].lower()))
        return items[:limit]

    scored: list[tuple[int, int, dict]] = []
    for it in items:
        name = it["name"].lower()
        if q == name:
            rank = 0
        elif name.startswith(q):
            rank = 1
        elif q in name:
            rank = 2
        else:
            continue
        scored.append((rank, len(it["name"]), it))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [it for _, _, it in scored[:limit]]


def get_set(set_id: str) -> dict | None:
    """Full card + member symbols + provenance for one set, or ``None`` if unknown."""
    meta = _index().get(set_id)
    if meta is None:
        return None
    genes = list(_load_source(meta["source"]).get(meta["name"], ()))
    prov = {
        "source": meta["source"],
        "source_label": meta["source_label"],
        "license": meta["license"],
        "set_name": meta["name"],
        "n_genes": len(genes),
    }
    if meta.get("attribution"):
        prov["attribution"] = meta["attribution"]
    return {**meta, "genes": genes, "provenance": prov}


def compile_sets(set_ids: list[str], op: str = "union", do_normalize: bool = True) -> dict:
    """Compile several catalog sets into one (gene-set builder Phase B).

    Union or intersect the chosen sets' members, then HGNC-normalize/dedup
    (gene_sets/normalize.py). Returns the compiled gene list + provenance (the source
    sets with their licenses/attribution, the op, and dedup/remap stats) so the result
    is a reproducible, citable `GeneSet`.
    """
    from gene_sets.normalize import normalize

    op = op if op in ("union", "intersect") else "union"
    members: list[set[str]] = []
    resolved: list[dict] = []
    missing: list[str] = []
    for sid in set_ids:
        meta = _index().get(sid)
        if meta is None:
            missing.append(sid)
            continue
        genes = set(_load_source(meta["source"]).get(meta["name"], ()))
        members.append(genes)
        resolved.append({
            "id": sid, "name": meta["name"], "source": meta["source"],
            "source_label": meta["source_label"], "license": meta["license"], "size": len(genes),
        })

    if not members:
        combined: set[str] = set()
    elif op == "intersect":
        combined = set.intersection(*members)
    else:
        combined = set.union(*members)

    norm = normalize(combined) if do_normalize else {
        "genes": sorted(combined), "remapped": {}, "unrecognized": [], "mapped": False,
    }
    return {
        "genes": norm["genes"],
        "op": op,
        "sources": resolved,
        "missing": missing,
        "provenance": {
            "compiled_from": resolved,
            "op": op,
            "n_in": len(combined),
            "n_out": len(norm["genes"]),
            "n_remapped": len(norm["remapped"]),
            "n_unrecognized": len(norm["unrecognized"]),
            "normalized": norm["mapped"],
            "licenses": sorted({r["license"] for r in resolved}),
        },
    }


def load_collection(source: str | None) -> dict[str, list[str]]:
    """An ORA library for the ``enrichment`` skill: one source, or ``all`` to union every source.

    ``name -> [SYMBOLS]``. ``all``/empty merges every present source (set names rarely
    collide across sources; on a collision, the later source wins — acceptable for ORA).
    """
    if not source or source == "all":
        merged: dict[str, list[str]] = {}
        for key in SOURCES:
            for name, genes in _load_source(key).items():
                merged[name] = list(genes)
        return merged
    return {name: list(genes) for name, genes in _load_source(source).items()}
