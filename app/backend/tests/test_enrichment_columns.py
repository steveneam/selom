"""enrichment gene-column detection — tolerant of real DE-table headers.

Mirrors the volcano fix: real DE tables name the gene column `GeneID` etc., so the
query-gene column must be found explicitly (not only via the first-column fallback).

Post-WS3.1: the runner reads the single-source gene vocabulary (``engine.columns.GENE``) by
*substring* (the same header semantics as the engine's D1 gate), via the runner's own ``_pick``.
"""

from engine.columns import GENE
from skills.enrichment.run_real import _pick


def _detect(columns):
    # the same detection the runner uses: substring match against the shared GENE vocabulary.
    cols = {str(c).strip().lower(): c for c in columns}
    return _pick(cols, GENE)


def test_detects_geneid_from_real_de_table():
    assert _detect(["GeneID", "ensembl_gene_id", "entrezgene_id", "logFC", "FDR"]) == "GeneID"


def test_detects_common_symbol_variants():
    # A clean symbol column wins over an id column (the priority baked into GENE's order).
    assert _detect(["gene_symbol", "logFC"]) == "gene_symbol"
    assert _detect(["symbol", "padj"]) == "symbol"
    assert _detect(["GeneID", "external_gene_name", "logFC"]) == "external_gene_name"


def test_no_gene_column_returns_none():
    assert _detect(["foo", "bar", "logFC"]) is None
