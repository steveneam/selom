"""Build an Ensembl-gene-ID -> HGNC symbol map for scRNA ingest (dev-time).

Some public h5ads key ``var_names`` by Ensembl gene IDs (``ENSG00000139618``) instead of
symbols, which breaks gene-name matching everywhere downstream (marker panels in
``annotate``, the gene param in ``violin``, readable labels in ``markers``/``heatmap``).
``skills/_genes.map_ensembl_to_symbol`` relabels them to symbols at ingest using this map.

Built from NCBI ``Homo_sapiens.gene_info`` (public domain) — the same cache the gene-set
ingest already downloads, so there is no new dependency. The ``dbXrefs`` column carries the
``Ensembl:ENSG...`` cross-reference per gene. Output
``gene_sets/corpus/ensembl_symbols.json`` = ``{ENSG...: SYMBOL}``. Gitignored/regenerable;
``skills/_genes`` degrades to a no-op when it is absent (fresh clone / CI).

Run:  uv run --directory app/backend python scripts/build_ensembl_map.py
"""

from __future__ import annotations

import gzip
import json
import pathlib

from config import datasets_dir

_DATASETS = datasets_dir()
CACHE = (_DATASETS / "genesets/raw/Homo_sapiens.gene_info.gz") if _DATASETS else None
OUT = pathlib.Path(__file__).resolve().parent.parent / "gene_sets" / "corpus" / "ensembl_symbols.json"


def main() -> None:
    if _DATASETS is None:
        raise SystemExit("SELOM_DATASETS_DIR is unset — point it at the datasets corpus root")
    if not CACHE.exists():
        raise SystemExit(
            f"missing {CACHE} — run scripts/build_wikipathways.py first (it caches gene_info)"
        )

    ensembl: dict[str, str] = {}
    ambiguous: set[str] = set()
    with gzip.open(CACHE, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.split("\t")
            if len(f) < 6:
                continue
            symbol, dbxrefs = f[2], f[5]
            if symbol in ("-", "") or "Ensembl:ENSG" not in dbxrefs:
                continue
            for x in dbxrefs.split("|"):
                if x.startswith("Ensembl:ENSG"):
                    eid = x.split(":", 1)[1]
                    if eid in ensembl and ensembl[eid] != symbol:
                        ambiguous.add(eid)  # one Ensembl ID -> two symbols: drop, never guess
                    else:
                        ensembl[eid] = symbol
    for eid in ambiguous:
        ensembl.pop(eid, None)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ensembl))
    print(f"BUILT {len(ensembl):,} Ensembl->symbol mappings ({len(ambiguous)} ambiguous dropped)")
    print(f"  wrote -> {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
