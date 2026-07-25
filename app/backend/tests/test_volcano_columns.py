"""volcano column detection — tolerant of real-world DE-table headers.

Real edgeR / limma / RUVseq exports name the gene column things like `GeneID`, not
just `gene`/`symbol`. These pure-function tests (no pandas) guard that detection so a
real table gets gene-symbol labels instead of falling back to the row index.

Post-A19 the runner has no picker of its own: every role goes through
``engine.columns.resolve`` (which owns normalization + the user override + the role's selection
order). Fold-change stays a substring match against ``engine.vocab``; the gene label is EXACT-tier
first (A10) so a column that merely *contains* a gene token is not mistaken for the row label.
"""

from engine.columns import normalize, pick_gene, pick_significance, resolve


def _cols(*names):
    return normalize(names)


def _gene(*names):
    """The gene label the runner would read for this header, or None (→ frame-index fallback)."""
    return resolve("gene", names)


def test_picks_geneid_from_limma_header():
    # Header from EYG_28 RUVseq/limma DE tables.
    cols = _cols("GeneID", "ensembl_gene_id", "entrezgene_id", "logFC", "AveExpr", "t", "P.Value", "B", "FDR")
    assert pick_gene(cols) == "GeneID"
    assert resolve("logFC", cols.values()) == "logFC"
    # FDR preferred over raw P.Value. Restored after WS3.1 (7440f56) inverted it: pointing selection
    # at the PRESENCE union made the raw token win for every non-DESeq2 convention, so a limma
    # volcano plotted + thresholded uncorrected p on an axis labelled "adjusted" (429 "significant"
    # genes vs 14 on the real EYG_28 export). Selection now goes through the adjusted-tier-first
    # resolver, and the flag it returns is what labels the axis/table.
    assert pick_significance(cols) == ("FDR", True)


def test_prefers_external_gene_name_over_composite_geneid():
    # biomaRt-style header (ALPK1 RO/iRPE limma export): GeneID is a composite
    # ENSG...~SYMBOL that maps to nothing, so the clean external_gene_name must win — GENE_EXACT's
    # order (clean symbol/name before the generic gene / id tokens) is what preserves that.
    cols = _cols("Comparison", "GeneID", "ensembl_gene_id", "external_gene_name",
                 "entrezgene_id", "logFC", "AveExpr", "t", "PValue", "B", "FDR")
    assert pick_gene(cols) == "external_gene_name"
    assert resolve("logFC", cols.values()) == "logFC"
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


def test_the_resolver_is_single_sourced_across_skills():
    # Neither the vocabulary NOR the matcher is duplicated per skill any more: every DE runner
    # imports the SAME engine.columns.resolve, so a selection fix lands once and can't drift (A19 —
    # WS3.1 converged the vocabulary and left six identical `_pick` copies behind).
    # (The full six-runner identity lock + the re-fork AST scan live in
    # engine/test_vocab_drift_guard.py.)
    import skills.enrichment.run_real as enrichment
    import skills.go_graph.run_real as go_graph
    import skills.pathway.run_real as pathway
    import skills.volcano.run_real as volcano

    assert volcano.resolve is enrichment.resolve is go_graph.resolve is pathway.resolve is resolve
    for mod in (volcano, enrichment, go_graph, pathway):
        assert not hasattr(mod, "_pick"), f"{mod.__name__} re-forked the matcher"


def test_picks_symbol_and_gene_name_variants():
    assert _gene("gene_name", "log2FC", "padj") == "gene_name"
    assert _gene("symbol", "log2FC", "padj") == "symbol"


def test_no_gene_column_returns_none():
    # Nothing gene-like -> None, so the runner falls back to the frame index.
    assert _gene("foo", "log2fc", "fdr") is None


# --- A10: a gene-ish column that is an ANNOTATION or a COUNT is not the row label -------------
# WS3.1 pointed gene SELECTION at the substring PRESENCE set, whose bare tokens ('gene', 'feature',
# 'names') match any header containing them. Verified live before the fix: run() on
# `gene_biotype,logFC,FDR` labelled the points 'protein_coding' / 'lncRNA' — a biotype string on the
# figure, in the top-N callouts and in the statistics table. Selection is now EXACT-tier first.

def test_annotation_column_never_wins_the_gene_label():
    # The exact header that exposed A10 -> None, so the runner falls back to the frame index.
    assert _gene("gene_biotype", "logFC", "FDR") is None
    # ...and the same table WITH a real label column resolves to the label, not the biotype.
    assert _gene("gene_biotype", "external_gene_name", "logFC", "FDR") == "external_gene_name"


def test_count_and_matrix_metadata_columns_never_win_the_gene_label():
    # The sibling hazards named in the finding: per-cell/per-sample COUNT columns and R matrix
    # metadata. All contain a bare GENE token; none is a row label.
    for header in ("n_features", "feature_count", "colnames", "n_genes", "gene_length",
                   "gene_count", "ngenes"):
        assert _gene(header, "logFC", "FDR") is None, header
    # A real corpus header: alpk1/ro_irpe/gene_lists/MitochondriaGenes_Sorted.csv is
    # `external_gene_name,GeneGroup` — the grouping column must never displace the symbol.
    assert _gene("external_gene_name", "GeneGroup") == "external_gene_name"
    assert _gene("GeneGroup", "logFC") is None


def test_exact_tier_reads_separator_and_bom_variants():
    # canon() collapses separators, so one spelling in GENE_EXACT covers them all...
    assert _gene("Gene Symbol", "logFC") == "Gene Symbol"
    assert _gene("gene.name", "logFC") == "gene.name"
    assert _gene("GENE-SYMBOL", "logFC") == "GENE-SYMBOL"
    # ...and a UTF-8 BOM left on the first header by an Excel export (live in the ALPK1 exports)
    # stops hiding the column.
    assert _gene("\ufeffexternal_gene_name", "logFC") == "\ufeffexternal_gene_name"


def test_substring_tier_still_catches_real_composite_headers():
    # Tier 2 is not gone — it is narrowed to tokens specific enough to be safe anywhere in a header.
    assert _gene("Comparison", "hgnc_symbol", "logFC") == "hgnc_symbol"
    assert _gene("Comparison", "ensembl_gene_id", "logFC") == "ensembl_gene_id"
    assert _gene("majority_protein_ids", "logFC") == "majority_protein_ids"


def test_user_override_still_wins_over_every_tier():
    # The override is honest (override-only, never fabricate): it wins when the column exists...
    cols = ("gene_biotype", "external_gene_name", "logFC", "FDR")
    assert resolve("gene", cols, {"gene": "gene_biotype"}) == "gene_biotype"
    # ...and falls back to auto-detection when it points at a column the frame does not carry.
    assert resolve("gene", cols, {"gene": "nope"}) == "external_gene_name"


def test_resolve_rejects_an_unknown_role():
    import pytest

    with pytest.raises(ValueError, match="unknown column role"):
        resolve("batch", ("gene", "logFC"))


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
