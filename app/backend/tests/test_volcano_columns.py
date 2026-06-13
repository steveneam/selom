"""volcano column detection — tolerant of real-world DE-table headers.

Real edgeR / limma / RUVseq exports name the gene column things like `GeneID`, not
just `gene`/`symbol`. These pure-function tests (no pandas) guard that detection so a
real table gets gene-symbol labels instead of falling back to the row index.
"""

from skills.volcano.run_real import _GENE_COLS, _FC_COLS, _P_COLS, _pick


def _cols(*names):
    return {c.lower(): c for c in names}


def test_picks_geneid_from_limma_header():
    # Header from EYG_28 RUVseq/limma DE tables.
    cols = _cols("GeneID", "ensembl_gene_id", "entrezgene_id", "logFC", "AveExpr", "t", "P.Value", "B", "FDR")
    assert _pick(cols, _GENE_COLS) == "GeneID"
    assert _pick(cols, _FC_COLS) == "logFC"
    assert _pick(cols, _P_COLS) == "FDR"  # FDR preferred over raw P.Value


def test_picks_symbol_and_gene_name_variants():
    assert _pick(_cols("gene_name", "log2FC", "padj"), _GENE_COLS) == "gene_name"
    assert _pick(_cols("symbol", "log2FC", "padj"), _GENE_COLS) == "symbol"


def test_no_gene_column_returns_none():
    # Nothing gene-like -> None, so the runner falls back to the frame index.
    assert _pick(_cols("foo", "log2fc", "fdr"), _GENE_COLS) is None
