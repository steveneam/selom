"""Gene-symbol ingest helpers — keep ``var_names`` matchable across references.

Public CellRanger / GEO matrices frequently prefix every gene symbol with the
genome build (``GRCh38_RHO``, ``mm10_Rho``) — a custom-reference artifact that
silently breaks downstream gene-name matching (marker panels in ``annotate``, the
gene param in ``violin``, readable labels in ``markers``/``heatmap``). Surfaced while
dogfooding the Hani GSE201356 organoid data, where ``annotate`` matched zero panel
markers until the ``GRCh38_`` prefix was stripped.

``read_anndata`` is the standard Selom scRNA read: ``sc.read_h5ad`` + a *conservative*
genome-prefix strip + an Ensembl-ID -> symbol relabel. Both are conservative — applied
only when the large majority of features share the pattern — so a real gene that merely
starts with a build token, or a symbol that merely looks ID-ish, is never mangled. (EAMOS
resolves contigs/transcripts at clinical-variant grade; Selom only needs this lightweight
symbol-cleaning at ingest.)
"""

import functools
import json
import pathlib
import re

# Assembly tokens seen as gene-symbol prefixes in public 10x / GEO references.
_GENOME_PREFIX = re.compile(
    r"^(GRCh38|GRCh37|GRCm39|GRCm38|hg19|hg38|mm9|mm10|mm39|GRCz11|mRatBN7|Rnor6)[_\-.:]",
    re.IGNORECASE,
)

_PREFIX_COVERAGE = 0.8  # strip only if >= this fraction of names share the prefix


def strip_genome_prefix(names) -> list[str]:
    """Return ``names`` with a uniform genome-assembly prefix removed, iff one is
    shared by >= 80% of entries (else returned unchanged). Accepts any string
    iterable; always returns a plain ``list[str]``."""
    names = [str(n) for n in names]
    if not names:
        return names
    hits = [bool(_GENOME_PREFIX.match(n)) for n in names]
    if sum(hits) < _PREFIX_COVERAGE * len(names):
        return names
    return [_GENOME_PREFIX.sub("", n, count=1) if h else n for n, h in zip(names, hits)]


# Ensembl gene IDs (ENSG…) used as var_names instead of symbols — relabel at ingest.
_ENSEMBL_MAP = (
    pathlib.Path(__file__).resolve().parent.parent / "gene_sets" / "corpus" / "ensembl_symbols.json"
)
_ENSEMBL_RE = re.compile(r"^ENSG\d{6,}", re.IGNORECASE)
_ENSEMBL_COVERAGE = 0.8  # map only if >= this fraction of names look like Ensembl IDs


@functools.lru_cache(maxsize=1)
def _ensembl_symbols() -> dict | None:
    """The Ensembl-ID -> symbol map (``scripts/build_ensembl_map.py``), or None if absent."""
    if not _ENSEMBL_MAP.exists():
        return None
    return json.loads(_ENSEMBL_MAP.read_text(encoding="utf-8"))


def map_ensembl_to_symbol(names) -> list[str]:
    """Relabel Ensembl-gene-ID names (``ENSG00000139618``) to HGNC symbols, iff the
    majority look like Ensembl IDs and the map is available. Version suffixes
    (``ENSG….4``) are stripped before lookup; unmapped IDs and non-Ensembl names are
    kept unchanged. Degrades to a no-op when the corpus is absent (fresh clone / CI)."""
    names = [str(n) for n in names]
    if not names:
        return names
    looks = [bool(_ENSEMBL_RE.match(n)) for n in names]
    if sum(looks) < _ENSEMBL_COVERAGE * len(names):
        return names
    mapping = _ensembl_symbols()
    if not mapping:
        return names
    return [
        (mapping.get(n.split(".", 1)[0].upper(), n) if is_ens else n)
        for n, is_ens in zip(names, looks)
    ]


def read_anndata(path):
    """``sc.read_h5ad`` with genome-prefix-cleaned, Ensembl-ID-relabelled, de-duplicated
    ``var_names`` — the shared scRNA read so every skill matches gene symbols consistently.
    Clean (symbol-keyed) inputs pass through untouched (no rename, no dedupe)."""
    import scanpy as sc

    adata = sc.read_h5ad(path)
    original = list(map(str, adata.var_names))
    cleaned = map_ensembl_to_symbol(strip_genome_prefix(adata.var_names))
    if cleaned != original:
        adata.var_names = cleaned
        adata.var_names_make_unique()
    return adata
