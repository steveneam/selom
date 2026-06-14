"""Build a compact HGNC-style symbol map for gene-set compile/normalize (dev-time).

Phase B of the gene-set builder: compiling sets (union/intersect across sources) needs
to reconcile gene symbols to a current approved symbol so the same gene from two sources
dedups. Built from NCBI ``Homo_sapiens.gene_info`` (public domain) — the same file the
WikiPathways ingest caches — so there is no new dependency or download.

Output ``gene_sets/corpus/hgnc_symbols.json`` = {"approved": [...], "alias": {ALIAS: SYMBOL}}.
Aliases that map to more than one approved symbol are dropped (ambiguous). Committed if
small enough; gene_sets/normalize.py degrades gracefully to upper+dedup when it is absent.

Run:  uv run --directory app/backend python scripts/build_symbols.py
"""

from __future__ import annotations

import gzip
import json
import pathlib

CACHE = pathlib.Path("D:/selom-data/genesets/raw/Homo_sapiens.gene_info.gz")
OUT = pathlib.Path(__file__).resolve().parent.parent / "gene_sets" / "corpus" / "hgnc_symbols.json"


def main() -> None:
    if not CACHE.exists():
        raise SystemExit(f"missing {CACHE} — run scripts/build_wikipathways.py first (it caches gene_info)")

    approved: set[str] = set()
    # alias -> set of approved symbols (to detect ambiguity)
    alias_to: dict[str, set[str]] = {}
    with gzip.open(CACHE, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.split("\t")
            if len(f) < 5:
                continue
            symbol, synonyms = f[2], f[4]
            if symbol in ("-", ""):
                continue
            approved.add(symbol)
            if synonyms and synonyms != "-":
                for syn in synonyms.split("|"):
                    syn = syn.strip()
                    if syn and syn != "-":
                        alias_to.setdefault(syn.upper(), set()).add(symbol)

    # Keep only unambiguous aliases that are not themselves an approved symbol.
    alias = {
        a: next(iter(s)) for a, s in alias_to.items()
        if len(s) == 1 and a not in approved
    }
    payload = {"approved": sorted(approved), "alias": alias}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload))
    print(f"BUILT {len(approved):,} approved symbols + {len(alias):,} aliases")
    print(f"  wrote -> {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
