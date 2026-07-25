"""volcano column detection — tolerant of real-world DE-table headers.

Real edgeR / limma / RUVseq exports name the gene column things like `GeneID`, not
just `gene`/`symbol`. These pure-function tests (no pandas) guard that detection so a
real table gets gene-symbol labels instead of falling back to the row index.

Post-WS3.1: the runner reads the single-source column vocabulary (``engine.vocab`` for
fold-change / significance, ``engine.columns.GENE`` for the gene label) by *substring* — the same
header semantics the engine's D1 data-contract gate uses — via the runner's own ``_pick``.
"""

from engine.columns import GENE, pick_significance
from engine.vocab import DE_LOGFC_SYNONYMS
from skills.volcano.run_real import _pick


def _cols(*names):
    return {str(c).strip().lower(): c for c in names}


def test_picks_geneid_from_limma_header():
    # Header from EYG_28 RUVseq/limma DE tables.
    cols = _cols("GeneID", "ensembl_gene_id", "entrezgene_id", "logFC", "AveExpr", "t", "P.Value", "B", "FDR")
    assert _pick(cols, GENE) == "GeneID"
    assert _pick(cols, DE_LOGFC_SYNONYMS) == "logFC"
    # FDR preferred over raw P.Value. Restored after WS3.1 (7440f56) inverted it: pointing selection
    # at the PRESENCE union made the raw token win for every non-DESeq2 convention, so a limma
    # volcano plotted + thresholded uncorrected p on an axis labelled "adjusted" (429 "significant"
    # genes vs 14 on the real EYG_28 export). Selection now goes through the adjusted-tier-first
    # resolver, and the flag it returns is what labels the axis/table.
    assert pick_significance(cols) == ("FDR", True)


def test_prefers_external_gene_name_over_composite_geneid():
    # biomaRt-style header (ALPK1 RO/iRPE limma export): GeneID is a composite
    # ENSG...~SYMBOL that maps to nothing, so the clean external_gene_name must win. GENE's order
    # (clean symbol/name before the generic gene / id tokens) preserves this under substring match.
    cols = _cols("Comparison", "GeneID", "ensembl_gene_id", "external_gene_name",
                 "entrezgene_id", "logFC", "AveExpr", "t", "PValue", "B", "FDR")
    assert _pick(cols, GENE) == "external_gene_name"
    assert _pick(cols, DE_LOGFC_SYNONYMS) == "logFC"
    assert pick_significance(cols) == ("FDR", True)  # edgeR/limma FDR, never the raw PValue


def test_significance_tier_per_de_tool_convention():
    """Every DE convention must resolve to its ADJUSTED column, and report that it is adjusted.

    One case per tool because the WS3.1 regression was invisible tool-by-tool: only DESeq2 ('padj')
    was unaffected, so a DESeq2-only test passed while limma/edgeR/scanpy/Seurat silently flipped.
    """
    assert pick_significance(_cols("gene", "log2FoldChange", "pvalue", "padj")) == ("padj", True)
    assert pick_significance(_cols("gene", "logFC", "PValue", "FDR")) == ("FDR", True)
    assert pick_significance(_cols("gene", "logFC", "P.Value", "adj.P.Val")) == ("adj.P.Val", True)
    # scanpy: the raw token 'pval' substring-matches the ADJUSTED header 'pvals_adj', which is why a
    # single ordered union can never be safe — the adjusted tier must be exhausted first.
    assert pick_significance(_cols("names", "logfoldchanges", "pvals", "pvals_adj")) == ("pvals_adj", True)
    assert pick_significance(_cols("gene", "avg_log2FC", "p_val", "p_val_adj")) == ("p_val_adj", True)
    assert pick_significance(_cols("feature", "logFC", "qvalue")) == ("qvalue", True)


def test_raw_only_table_resolves_raw_and_says_so():
    # A legitimate fallback — a table with no corrected column still plots, but `adjusted` is False
    # so the axis title, the table column name and QC report a raw p instead of implying BH.
    assert pick_significance(_cols("gene", "logFC", "P.Value")) == ("P.Value", False)
    assert pick_significance(_cols("gene", "logFC")) == (None, False)
    # An adjusted header the adjusted tier has no token for is still not called raw.
    assert pick_significance(_cols("gene", "logFC", "p_value_adjusted")) == ("p_value_adjusted", True)


def test_gene_vocabulary_is_single_sourced_across_skills():
    # The gene vocabulary is no longer duplicated per skill — every DE runner imports the SAME
    # engine.columns.GENE object, so a symbol-over-id priority fix lands once and can't drift.
    # (The full six-runner identity lock lives in engine/test_vocab_drift_guard.py.)
    import skills.enrichment.run_real as enrichment
    import skills.go_graph.run_real as go_graph
    import skills.pathway.run_real as pathway
    import skills.volcano.run_real as volcano

    assert volcano.GENE is enrichment.GENE is go_graph.GENE is pathway.GENE is GENE


def test_picks_symbol_and_gene_name_variants():
    assert _pick(_cols("gene_name", "log2FC", "padj"), GENE) == "gene_name"
    assert _pick(_cols("symbol", "log2FC", "padj"), GENE) == "symbol"


def test_no_gene_column_returns_none():
    # Nothing gene-like -> None, so the runner falls back to the frame index.
    assert _pick(_cols("foo", "log2fc", "fdr"), GENE) is None


# --- gene labels are ONE draggable representation (unify-on-superior-framework) ---------------
# Ratchet: every volcano gene label — auto top-N AND gene-set highlight — must be a
# layout.annotation (individually draggable/deletable in the editor), never a frozen `text` trace.
# This guard fails loudly if a future change reintroduces a static label trace.
from skills.volcano.run import _assemble  # noqa: E402


def test_topn_labels_are_annotations_not_a_text_trace():
    up = ([2.0], [5.0], [["A", 0.001]])
    spec = _assemble(up, ([], [], []), ([], [], []), labels=[(2.0, 5.0, "A")], fc_t=1.0, y_cut=1.3, title="t")
    annos = spec["layout"].get("annotations", [])
    assert [a["text"] for a in annos] == ["A"]
    # no static text-label trace survives
    assert not any(t.get("mode") == "text" or t.get("name") == "labels" for t in spec["data"])
    # smart-connector + grabbable/deletable annotation
    a = annos[0]
    assert a["showarrow"] is True and a["captureevents"] is True


def test_highlight_keeps_markers_but_labels_are_annotations():
    hl = [(1.5, 4.0, "B")]
    spec = _assemble(([], [], []), ([], [], []), ([], [], []), labels=[], fc_t=1.0, y_cut=1.3, title="t", highlight=hl)
    # amber markers stay a trace; its label moved to annotations (no markers+text)
    hi = [t for t in spec["data"] if t.get("name") == "highlighted"]
    assert hi and hi[0]["mode"] == "markers"
    assert [a["text"] for a in spec["layout"]["annotations"]] == ["B"]


def test_no_labels_omits_annotations_key():
    # A label-less figure (the stub) stays byte-identical to its golden — no empty annotations key.
    spec = _assemble(([], [], []), ([], [], []), ([], [], []), labels=[], fc_t=1.0, y_cut=1.3, title="t")
    assert "annotations" not in spec["layout"]


def test_methods_text_drops_the_bh_claim_when_only_raw_p_was_available():
    """The prose must not out-claim the data: no corrected column -> no Benjamini-Hochberg sentence.

    The runner declares the fallback in ``layout.meta.significance`` (written only in that case, so
    every adjusted figure stays byte-identical to its golden) and the methods builder reads it.
    """
    from companions import methods
    from skills.registry import load_skill

    spec = load_skill("volcano")
    params = {"fc_threshold": 1.0, "fdr_threshold": 0.05, "top_n": 10}

    adjusted_text, adjusted_cites = methods.build_body(spec, params, figure={"layout": {}})
    assert "Benjamini-Hochberg" in adjusted_text
    assert "FDR <= 0.05" in adjusted_text

    raw_text, raw_cites = methods.build_body(
        spec, params, figure={"layout": {"meta": {"significance": "raw"}}})
    assert "Benjamini-Hochberg" not in raw_text
    assert "RAW (uncorrected)" in raw_text
    assert "does not control the false-discovery rate" in raw_text
    assert raw_cites == [] and adjusted_cites  # no BH citation for an uncorrected figure
