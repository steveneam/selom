"""Build a license-clean WikiPathways gene-set library (dev-time, one-off).

Phase A of the gene-set builder (DECISIONS #11): WikiPathways is **CC0** — an open,
license-clean alternative to KEGG/MSigDB. Its GMT is keyed by **Entrez Gene ID**, but
Selom's inputs (and the GO library) are gene-symbol keyed, so this maps Entrez ->
HGNC symbol via NCBI ``Homo_sapiens.gene_info`` (public domain) and writes the same
``{"<pathway>": [SYMBOLS], "_provenance": ...}`` shape every Selom corpus file uses.

The symbol-keyed output is small (~0.3 MB) and **committed** so the product ships the
WikiPathways corpus out of the box — no download needed at runtime or on a fresh clone.

Run (stdlib only — no extra deps):
    uv run --directory app/backend python scripts/build_wikipathways.py
"""

from __future__ import annotations

import gzip
import json
import pathlib
import re
import shutil
import urllib.request

WP_INDEX = "https://data.wikipathways.org/current/gmt/"
GENEINFO_URL = "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz"
CACHE = pathlib.Path("D:/selom-data/genesets/raw")
OUT = pathlib.Path(__file__).resolve().parent.parent / "gene_sets" / "corpus" / "gene_sets_wikipathways.json"

MIN_SET, MAX_SET = 5, 500  # drop tiny noise + giant near-meta pathways
_UA = {"User-Agent": "Mozilla/5.0 (Selom gene-set builder)"}  # plain urllib UA gets 403'd by some CDNs


def _download(url: str, dest: pathlib.Path) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  cached: {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest
    print(f"  downloading {url} ...")
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as out:  # noqa: S310 (trusted URLs)
        shutil.copyfileobj(resp, out)
    print(f"  saved {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def _resolve_current_gmt() -> str:
    """The dated Homo sapiens GMT filename changes each release; resolve it from the index."""
    req = urllib.request.Request(WP_INDEX, headers=_UA)
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        html = resp.read().decode("utf-8", "replace")
    names = sorted(set(re.findall(r"wikipathways-\d+-gmt-Homo_sapiens\.gmt", html)))
    if not names:
        raise RuntimeError("no Homo sapiens GMT found in the WikiPathways current index")
    return names[-1]  # latest by date-stamped name


def _entrez_to_symbol(gene_info: pathlib.Path) -> dict[str, str]:
    """Entrez GeneID (str) -> HGNC symbol, from NCBI gene_info (cols: GeneID=1, Symbol=2)."""
    mapping: dict[str, str] = {}
    with gzip.open(gene_info, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.split("\t")
            if len(f) > 2 and f[2] not in ("-", ""):
                mapping[f[1]] = f[2]
    return mapping


def main() -> None:
    gmt_name = _resolve_current_gmt()
    gmt = _download(f"{WP_INDEX}{gmt_name}", CACHE / "wikipathways-Homo_sapiens.gmt")
    gene_info = _download(GENEINFO_URL, CACHE / "Homo_sapiens.gene_info.gz")

    print("building Entrez -> symbol map ...")
    e2s = _entrez_to_symbol(gene_info)
    print(f"  {len(e2s):,} Entrez ids mapped")

    print("parsing WikiPathways GMT + mapping to symbols ...")
    sets: dict[str, list[str]] = {}
    n_seen = n_unmapped = 0
    for line in gmt.read_text(encoding="utf-8").splitlines():
        fields = line.rstrip("\n").split("\t")
        if len(fields) < 3:
            continue
        name = fields[0].split("%")[0].strip()  # "Name%WikiPathways_date%WPxxx%Homo sapiens"
        symbols, seen = [], set()
        for entrez in fields[2:]:
            n_seen += 1
            sym = e2s.get(entrez.strip())
            if sym is None:
                n_unmapped += 1
                continue
            if sym not in seen:
                seen.add(sym)
                symbols.append(sym)
        if name and MIN_SET <= len(symbols) <= MAX_SET:
            sets[name] = sorted(symbols)

    sets["_provenance"] = (
        f"WikiPathways {gmt_name} (data.wikipathways.org, CC0-1.0); Entrez->symbol via "
        f"NCBI Homo_sapiens.gene_info (public domain); sizes {MIN_SET}-{MAX_SET}. "
        "Built by scripts/build_wikipathways.py."
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(sets, indent=1))

    n = len([k for k in sets if not k.startswith("_")])
    bg = {g for k, v in sets.items() if not k.startswith("_") for g in v}
    print(f"\nBUILT {n} WikiPathways sets; {len(bg):,} unique symbols "
          f"({n_unmapped:,}/{n_seen:,} gene refs unmapped)")
    print(f"  wrote -> {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
