"""Build attributed reference gene panels from the staged CMRI/Fidelle gene lists (dev-time).

Gene-set builder Phase B (DECISIONS #11 #3 clarification, owner 2026-06-14): gene lists
from papers / public repos are not license-gated (symbols are facts) — ship them and
**attribute the source**. Each panel here records its own ``attribution`` + ``license`` in
the rich corpus format consumed by gene_sets/library.py (the ``reference`` source).

Sources live under D:/selom-data (outside the repo); the OUTPUT json is committed so the
panels ship without the raw files. Only clean, single-symbol-column lists are ingested;
messy multi-header supplementary tables are skipped.

Run:  uv run --directory app/backend python scripts/build_reference_panels.py
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path("D:/selom-data")
OUT = pathlib.Path(__file__).resolve().parent.parent / "gene_sets" / "corpus" / "gene_sets_reference.json"

# (display name, file, symbol column, attribution, license)
PANELS = [
    ("Ciliopathy genes (CiliaCarta)", "alpk1/gene_lists/CiliaCarta_Nov2023.xlsx",
     "Associated Gene Name", "CiliaCarta — van Dam et al., 2013", "Academic (CiliaCarta, van Dam 2013)"),
    ("Cilium assembly", "alpk1/ro_irpe/gene_lists/CiliumAssembly.csv",
     "external_gene_name", "CMRI Fidelle lab (curated)", "CMRI Fidelle (curated)"),
    ("Proteostasis — ubiquitin–proteasome system", "rpgr/gene_lists/Ubiquitin Proteosome System.xlsx",
     "external_gene_name", "CMRI Fidelle lab (curated, proteostasis network)", "CMRI Fidelle (curated)"),
    ("Proteostasis — autophagy–lysosome", "rpgr/gene_lists/Autophagy-Lysosome pathway.xlsx",
     "external_gene_name", "CMRI Fidelle lab (curated, proteostasis network)", "CMRI Fidelle (curated)"),
    ("Proteostasis — chaperones", "rpgr/gene_lists/Chaperones, protein synthesis, trafficking and degradation.xlsx",
     "external_gene_name", "CMRI Fidelle lab (curated, proteostasis network)", "CMRI Fidelle (curated)"),
]

MIN_SET = 3


def _symbols(path: pathlib.Path, column: str) -> list[str]:
    import pandas as pd

    df = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)
    if column not in df.columns:
        raise KeyError(f"{path.name}: no column '{column}' (has {list(df.columns)[:6]})")
    out, seen = [], set()
    for v in df[column].tolist():
        s = str(v).strip().upper()
        if not s or s in ("NAN", "NONE", "-") or s in seen or not s[0].isalpha():
            continue
        seen.add(s)
        out.append(s)
    return sorted(out)


def main() -> None:
    panels: dict[str, object] = {
        "_provenance": (
            "Attributed reference panels (gene-set builder Phase B). Gene lists from CMRI "
            "Fidelle curation + published resources; each set cites its own source + license "
            "(owner-cleared 2026-06-14: symbols are facts, attribute the source). "
            "Built by scripts/build_reference_panels.py from D:/selom-data."
        )
    }
    for name, rel, column, attribution, license_ in PANELS:
        path = ROOT / rel
        if not path.exists():
            print(f"  SKIP (missing): {rel}")
            continue
        genes = _symbols(path, column)
        if len(genes) < MIN_SET:
            print(f"  SKIP (too small, {len(genes)}): {name}")
            continue
        panels[name] = {"genes": genes, "license": license_, "attribution": attribution}
        print(f"  {name}: {len(genes)} genes  [{attribution}]")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(panels, indent=1))
    n = len([k for k in panels if not k.startswith("_")])
    print(f"\nBUILT {n} attributed reference panels -> {OUT} ({OUT.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
