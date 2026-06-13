"""enrichment gene-column detection — tolerant of real DE-table headers.

Mirrors the volcano fix: real DE tables name the gene column `GeneID` etc., so the
query-gene column must be found explicitly (not only via the first-column fallback).
"""

from skills.enrichment.run_real import _GENE_COLS


def _detect(columns):
    # same one-liner the runner uses
    return next((c for c in columns if c.lower() in _GENE_COLS), None)


def test_detects_geneid_from_real_de_table():
    assert _detect(["GeneID", "ensembl_gene_id", "entrezgene_id", "logFC", "FDR"]) == "GeneID"


def test_detects_common_symbol_variants():
    assert _detect(["gene_symbol", "logFC"]) == "gene_symbol"
    assert _detect(["symbol", "padj"]) == "symbol"


def test_no_gene_column_returns_none():
    assert _detect(["foo", "bar", "logFC"]) is None
