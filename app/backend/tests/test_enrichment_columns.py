"""enrichment gene-column detection — tolerant of real DE-table headers.

Mirrors the volcano fix: real DE tables name the gene column `GeneID` etc., so the
query-gene column must be found explicitly (not only via the first-column fallback).

Post-A19 the runner has no picker of its own — it calls ``engine.columns.resolve`` like every
other DE runner, so gene selection is EXACT-tier first (A10) and cannot drift per skill.
"""

from engine.columns import resolve


def _detect(columns):
    # the same call the runner makes.
    return resolve("gene", columns)


def test_detects_geneid_from_real_de_table():
    assert _detect(["GeneID", "ensembl_gene_id", "entrezgene_id", "logFC", "FDR"]) == "GeneID"


def test_detects_common_symbol_variants():
    # A clean symbol column wins over an id column (the priority baked into GENE's order).
    assert _detect(["gene_symbol", "logFC"]) == "gene_symbol"
    assert _detect(["symbol", "padj"]) == "symbol"
    assert _detect(["GeneID", "external_gene_name", "logFC"]) == "external_gene_name"


def test_no_gene_column_returns_none():
    assert _detect(["foo", "bar", "logFC"]) is None


def test_annotation_column_is_not_a_gene_label():
    # A10, mirrored here because enrichment derives its QUERY SET from this column: a biotype
    # annotation would turn the query into {"protein_coding", "lncRNA"} and score nothing real.
    assert _detect(["gene_biotype", "logFC", "FDR"]) is None
    assert _detect(["gene_biotype", "external_gene_name", "logFC"]) == "external_gene_name"
