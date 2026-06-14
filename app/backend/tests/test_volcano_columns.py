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


def test_prefers_external_gene_name_over_composite_geneid():
    # biomaRt-style header (ALPK1 RO/iRPE limma export): GeneID is a composite
    # ENSG...~SYMBOL that maps to nothing, so the clean external_gene_name must win.
    cols = _cols("Comparison", "GeneID", "ensembl_gene_id", "external_gene_name",
                 "entrezgene_id", "logFC", "AveExpr", "t", "PValue", "B", "FDR")
    assert _pick(cols, _GENE_COLS) == "external_gene_name"
    assert _pick(cols, _FC_COLS) == "logFC"
    assert _pick(cols, _P_COLS) == "FDR"


def test_gene_col_lists_agree_across_skills():
    # The gene/fc/p column lists are duplicated in each DE-consuming skill; keep them in
    # lock-step so a fix in one (e.g. symbol-over-id priority) can't silently drift.
    from skills.enrichment.run_real import _GENE_COLS as enrichment_cols
    from skills.go_graph.run_real import _GENE_COLS as go_graph_cols
    from skills.pathway.run_real import _GENE_COLS as pathway_cols

    assert _GENE_COLS == enrichment_cols == go_graph_cols == pathway_cols


def test_picks_symbol_and_gene_name_variants():
    assert _pick(_cols("gene_name", "log2FC", "padj"), _GENE_COLS) == "gene_name"
    assert _pick(_cols("symbol", "log2FC", "padj"), _GENE_COLS) == "symbol"


def test_no_gene_column_returns_none():
    # Nothing gene-like -> None, so the runner falls back to the frame index.
    assert _pick(_cols("foo", "log2fc", "fdr"), _GENE_COLS) is None
