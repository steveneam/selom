"""Gene-symbol ingest helpers — keep ``var_names`` matchable across references.

Public CellRanger / GEO matrices frequently prefix every gene symbol with the
genome build (``GRCh38_RHO``, ``mm10_Rho``) — a custom-reference artifact that
silently breaks downstream gene-name matching (marker panels in ``annotate``, the
gene param in ``violin``, readable labels in ``markers``/``heatmap``). Surfaced while
dogfooding the Hani GSE201356 organoid data, where ``annotate`` matched zero panel
markers until the ``GRCh38_`` prefix was stripped.

``read_anndata`` is the standard Selom scRNA read: ``sc.read_h5ad`` + a *conservative*
genome-prefix strip. A prefix is only removed when it is shared by the large majority
of features, so a real gene that merely starts with such a token is never mangled.
(EAMOS resolves contigs/transcripts at clinical-variant grade; Selom only needs this
lightweight symbol-cleaning at ingest.)
"""

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


def read_anndata(path):
    """``sc.read_h5ad`` with genome-prefix-cleaned, de-duplicated ``var_names`` — the
    shared scRNA read so every skill matches gene symbols consistently. Clean inputs
    pass through untouched (no prefix detected → no rename, no dedupe)."""
    import scanpy as sc

    adata = sc.read_h5ad(path)
    cleaned = strip_genome_prefix(adata.var_names)
    if cleaned != list(map(str, adata.var_names)):
        adata.var_names = cleaned
        adata.var_names_make_unique()
    return adata
