"""Figure Extraction Subsystem (R4/X1 slice-1) — text-layer-exact target extraction.

Unit tests on synthetic text (the phrasings the real papers use) + a slow, opt-in integration
test on the real JEV PDF (skipped where the file isn't present, like the gated R-oracle).
Covers: DE-count extraction (E2), the methods-digest lexicon, scope classification (guard 7),
the gated vision classifier, inconsistency capture (guard 2), and the bridge into the engine.
"""

from pathlib import Path

import pytest

import reproduction as R
from extract import (
    CaptionRuleClassifier,
    IngestedPaper,
    IngestedSupplement,
    OperatorVisionGateway,
    PaperBundle,
    PanelBox,
    VisionClassifier,
    VisionObservation,
    VisionUnavailable,
    associate_counts,
    augment_with_vision,
    build_extracted_spec,
    venn3_totals,
    classify_scope,
    extract_dataset_size,
    extract_de_counts,
    extract_methods_digest,
    find_figures_vs_methods,
    ingest_paper,
    ingest_supplement,
    segment_panels,
    to_engine_panels,
    to_golden,
)
from extract.models import GoldenTarget

# Synthetic text in the exact phrasings of the real papers (so the regexes are pinned).
MIRNA = ("From the 139 detected miRNA, 35 were differentially expressed "
         "(12 upregulated, 23 downregulated, p < 0.05, Figure 1c and Figure S1e).")
PROTEIN = ("In total, 180 proteins were found to be differentially expressed, with "
           "61 upregulated and 119 downregulated (Table S6, Figure 4e, p < 0.05).")
MARKERS = "the top 100 most differentially expressed genes in each cell type were listed."
# A single sentence where a neighbouring count (the 'top 50') must NOT become the DE total.
CONFLATION = ("The top 50 differentially expressed proteins comprised 61 upregulated and "
              "119 downregulated genes (Figure 4e, p < 0.05).")
METHODS = ("Differential expression with edgeR after TMM normalisation; a CPM < 2 filter; "
           "significance at adj. p < 0.05 and |logFC| > 1. Morley et al. reviewed it.")


# --- DE-count extraction (text-layer-exact, E2) -------------------------------


def _by_metric(targets, figure=None):
    return {t.metric: t for t in targets if figure is None or t.figure == figure}


def test_de_counts_protein_phrasing():
    t = _by_metric(extract_de_counts(PROTEIN, "p"))
    assert (t["de_total"].value, t["de_up"].value, t["de_down"].value) == (180, 61, 119)
    assert t["de_total"].confidence == 1.0 and t["de_total"].source == "figure"
    assert t["de_up"].figure == "4" and t["de_up"].panel == "e"
    assert "p < 0.05" in t["de_total"].note


def test_de_counts_mirna_phrasing():
    t = _by_metric(extract_de_counts(MIRNA, "p"))
    assert (t["de_total"].value, t["de_up"].value, t["de_down"].value) == (35, 12, 23)
    assert t["de_up"].figure == "1"  # panel letter is best-effort (1b/1c); the count is exact


def test_de_counts_skips_non_count_sentences():
    # 'top 100 most differentially expressed genes' has no up/down → not a count golden.
    assert extract_de_counts(MARKERS, "p") == []


def test_de_total_is_up_plus_down_not_a_neighbouring_count():
    # The 'top 50' heatmap count must NOT become the volcano's total; total = up + down = 180.
    t = _by_metric(extract_de_counts(CONFLATION, "p"))
    assert (t["de_total"].value, t["de_up"].value, t["de_down"].value) == (180, 61, 119)
    assert "printed total 50" in t["de_total"].note


# --- analyzed-dataset-size (n_cells) extraction (Slice 1; text-layer-exact) ---------

# The real Yoshimura phrasing (kidney-organoid multiome): the atlas size, double-anchored.
YOSHIMURA = ("These merged datasets for each time point were then aggregated together to generate "
             "an organoid differentiation multiome atlas. This resulted in 56,865 cells after "
             "filtering. For a comparison to human adult kidney, we used a merged dataset.")
# Real benchmark-paper traps (Harmony phrasings + an epidemiology %/cell-line) that must NOT extract.
HARMONY_TRAPS = ("We analyzed 15,875 cells from 8 time points of mouse and 64,373 cells from one "
                 "donor. We down-sampled to 250,000, 125,000, and 30,000 cells to benchmark "
                 "runtime. CKD affects 9.1% of the population. We used 1565 293T cells and 100 "
                 "cells per cluster as a threshold.")


def test_dataset_size_extracts_atlas_count_from_real_phrasing():
    g = extract_dataset_size(YOSHIMURA, "yoshimura")
    assert [t.value for t in g] == [56865]            # the two anchors dedup to one golden
    t = g[0]
    assert t.metric == "n_cells" and t.confidence == 1.0 and t.source == "figure"
    assert "after filtering" in t.note or "resulted in" in t.note


def test_dataset_size_is_silent_on_benchmark_and_epidemiology_traps():
    # A benchmark paper states many cell counts that are *parameters*, not the analyzed atlas;
    # an epidemiology "9.1% of the population", a "293T" cell line, and "100 cells" thresholds are
    # not dataset sizes. None has a result/QC anchor → nothing extracted (precision-first, E2).
    assert extract_dataset_size(HARMONY_TRAPS, "harmony") == []


def test_dataset_size_threshold_count_is_not_a_dataset():
    # "transcripts detected in at least 10% of cells" / "at least 3 cells" are filters, not sizes.
    assert extract_dataset_size("genes detected in at least 3 cells were kept", "p") == []


def test_dataset_size_flows_into_extracted_spec_and_engine_panel():
    spec = build_extracted_spec(None, "yoshimura", text=YOSHIMURA)
    n = [g for g in spec.goldens if g.metric == "n_cells"]
    assert n and n[0].value == 56865
    g = to_golden(n[0])
    assert isinstance(g, R.Golden) and g.value == 56865 and g.metric_type == ""  # count → strict


# --- methods digest -----------------------------------------------------------


def test_methods_digest_recovers_recipe():
    d = extract_methods_digest(METHODS)
    assert "edgeR" in d.tools
    assert "TMM" in d.normalizations
    assert any("0.05" in t for t in d.thresholds)
    assert any("CPM" in f for f in d.filters)


def test_methods_lexicon_uses_word_boundaries():
    # 'RLE' must not fire inside the author name 'Morley' (the real JEV false-positive bug).
    assert "RLE" not in extract_methods_digest(METHODS).normalizations


# --- scope classification (guard 7) -------------------------------------------


def test_scope_wet_lab_vs_transcriptomic():
    assert classify_scope("(d) PRPH2 immunostaining of retinal sections") == R.WET_LAB
    assert classify_scope("RT-qPCR validation of RHO expression") == R.WET_LAB
    assert classify_scope("Volcano plot of differentially expressed genes") == R.TRANSCRIPTOMIC


def test_scope_transcriptomic_signal_overrides_incidental_microscopy():
    # A panel that mentions 'confocal' yet plots a UMAP is transcriptomic, not wet-lab.
    assert classify_scope("UMAP of cells imaged by confocal microscopy") == R.TRANSCRIPTOMIC


# --- chart classifier (rule now; vision gated) --------------------------------


def test_caption_rule_classifier():
    c = CaptionRuleClassifier()
    assert c.classify_chart("Volcano plot of EV proteins")[0] == "volcano"
    assert c.classify_chart("Heatmap of top 50 proteins")[0] == "heatmap"
    assert c.classify_chart("Venn diagram of shared terms")[0] == "venn"
    assert c.classify_chart("a paragraph with no chart")[0] == ""


def test_vision_classifier_is_gated():
    with pytest.raises(VisionUnavailable):
        VisionClassifier().classify_chart("Volcano plot")


# --- inconsistency capture (guard 2) ------------------------------------------


def test_figures_vs_methods_inconsistency():
    # RPGRIP1: signature = 78 (results) vs 181 (methods) → capture both.
    inc = find_figures_vs_methods("signature.count", [78, 181, 78],
                                  printed_in=["results", "methods"])
    assert inc is not None and inc.kind == "figures_vs_methods"
    assert "signature.count=78" in inc.conflicting_value and "signature.count=181" in inc.conflicting_value
    # Agreeing values → no inconsistency.
    assert find_figures_vs_methods("x", [12, 12]) is None


# --- bridge into the engine ---------------------------------------------------


def test_to_golden_and_to_engine_panels():
    spec = build_extracted_spec(None, "p", text=PROTEIN + " " + METHODS)
    panels = to_engine_panels(spec)
    assert len(panels) == 1 and isinstance(panels[0], R.Panel)
    p = panels[0]
    assert p.figure == "4" and p.panel == "e" and p.scope == R.TRANSCRIPTOMIC
    metrics = {g.metric: g.value for g in p.golden}
    assert metrics == {"de_total": 180, "de_up": 61, "de_down": 119}
    # to_golden produces a real engine Golden.
    g = to_golden(GoldenTarget(paper_id="p", metric="de_up", value=61, source="figure"))
    assert isinstance(g, R.Golden) and g.value == 61


def test_build_extracted_spec_assembles_bundle():
    spec = build_extracted_spec(None, "jev", text=MIRNA + " " + PROTEIN + " " + METHODS)
    assert spec.paper_id == "jev"
    assert spec.methods and "edgeR" in spec.methods[0].tools
    totals = {g.value for g in spec.goldens if g.metric == "de_total"}
    assert {35, 180} <= totals
    assert spec.panels  # one coarse panel draft per distinct (figure, panel)


# --- X1 slice-2: vision layer (Claude as gateway, replayed → CI-safe) ---------


def test_operator_gateway_observe_replays_and_degrades():
    gw = OperatorVisionGateway({"5a": VisionObservation(panel_key="5a", chart_form="volcano",
                                                        counts={"signature": 181})})
    assert gw.observe("5a").chart_form == "volcano"
    with pytest.raises(VisionUnavailable):  # unrecorded panel → degrade cleanly
        gw.observe("9z")


def test_vision_classifier_wires_behind_the_existing_seam():
    # The operator gateway drops in behind the slice-1 VisionClassifier (sub-spec open-Q#2).
    gw = OperatorVisionGateway({"4e": VisionObservation(panel_key="4e", chart_form="volcano",
                                                        confidence=0.95)})
    form, conf = VisionClassifier(gw).classify_chart("4e")
    assert form == "volcano" and conf == 0.95
    with pytest.raises(VisionUnavailable):
        VisionClassifier(gw).classify_chart("nope")


def test_associate_counts_marks_vision_confidence_and_source():
    obs = VisionObservation(panel_key="5a", counts={"signature": 181}, confidence=0.9)
    g = associate_counts(obs, "rpgrip1")[0]
    assert g.metric == "signature" and g.value == 181
    assert g.figure == "5" and g.panel == "a"
    assert g.source == "figure" and g.confidence == 0.9  # vision-only, not text-layer-exact 1.0


def test_augment_with_vision_recovers_a_count_the_text_reader_missed():
    # RPGRIP1's "signature" count is stated graphically; slice-1's DE-count reader returns nothing.
    spec = build_extracted_spec(None, "rpgrip1",
                                text="Figure 5a shows the rod signature gene set.")
    assert not [g for g in spec.goldens if g.metric == "signature"]  # text reader is silent
    gw = OperatorVisionGateway({"5a": VisionObservation(
        panel_key="5a", chart_form="volcano", counts={"signature": 181}, confidence=0.9)})
    enriched = augment_with_vision(spec, gw, keys=["5a"])
    sig = [g for g in enriched.goldens if g.metric == "signature"]
    assert sig and sig[0].value == 181 and sig[0].confidence == 0.9
    # the empty slice-1 chart_form for 5a is now filled from vision
    assert any(d.key == "5a" and d.chart_form == "volcano" for d in enriched.panels)


def test_augment_with_vision_does_not_duplicate_existing_goldens():
    spec = build_extracted_spec(None, "p", text=PROTEIN)  # already has de_total/up/down for 4e
    gw = OperatorVisionGateway({"4e": VisionObservation(panel_key="4e", counts={"de_total": 999})})
    enriched = augment_with_vision(spec, gw, keys=["4e"])
    totals = [g for g in enriched.goldens if g.panel_key == "4e" and g.metric == "de_total"]
    assert len(totals) == 1 and totals[0].value == 180  # text-layer value kept, vision not dupd


def test_venn3_totals_reconstructs_rpgrip1_fig6e_targets():
    # The real Fig 6E Venn read off the raster (Claude-as-gateway): unique 27/52/10, pairwise
    # 13/10/2, all-three 52. The text states only the unique + all-three; the pairwise overlaps
    # are pixel-only. Reconstructing per-set totals gives the paper's GO-term targets 102/119/74.
    tot = venn3_totals(a=27, b=52, c=10, ab=13, ac=10, bc=2, abc=52)
    assert (tot["A"], tot["B"], tot["C"]) == (102, 119, 74)  # Rod-1/2/3 GSEA-panel targets
    assert tot["total"] == 166


def test_vision_recovers_fig6e_venn_the_text_reader_cannot():
    # Regression for the live dogfood: slice-1's DE-count reader is silent on the Fig 6E GO-term
    # sentence (wrong vocabulary); the replayed vision observation recovers the pixel-only overlaps.
    six_e = ("We identified 52 enriched GO terms common to all 3 rod subtypes, with 27, 52, and 10 "
             "terms unique to Rod-1, 2, and 3, respectively (Figure 6E).")
    spec = build_extracted_spec(None, "rpgrip1", text=six_e)
    assert extract_de_counts(six_e, "rpgrip1") == []           # text reader: nothing
    gw = OperatorVisionGateway({"6e": VisionObservation(
        panel_key="6e", chart_form="venn", confidence=0.97,
        counts={"venn_rod1_rod2": 13, "venn_rod1_rod3": 10, "venn_rod2_rod3": 2})})
    enriched = augment_with_vision(spec, gw, keys=["6e"])
    pairwise = {g.metric: g.value for g in enriched.goldens if g.metric.startswith("venn_")}
    assert pairwise == {"venn_rod1_rod2": 13, "venn_rod1_rod3": 10, "venn_rod2_rod3": 2}


def test_segment_panels_manual_assist():
    gw = OperatorVisionGateway({"6d": VisionObservation(panel_key="6d", chart_form="stacked_bar",
                                                        confidence=0.85)})
    boxes = [PanelBox(figure="6", panel="d", caption="composition of cell types"),
             PanelBox(figure="6", panel="e", caption="PRPH2 immunostaining of retina")]
    drafts = segment_panels("rpgrip1", boxes, gw)
    by_key = {d.key: d for d in drafts}
    assert by_key["6d"].chart_form == "stacked_bar"             # filled from the gateway
    assert by_key["6e"].scope == R.WET_LAB                      # scope from caption (guard 7)
    assert by_key["6e"].chart_form == ""                       # no observation → left for rule reader


# --- E7: two-input intake (main + N supplements, format-plural) ---------------


def _bundle(main_text: str, supp_text: str) -> PaperBundle:
    """A PaperBundle with no files — a main PDF + one PDF supplement (extended methods)."""
    return PaperBundle(
        paper_id="p",
        main=IngestedPaper(path="main.pdf", n_pages=1, text=main_text),
        supplements=[IngestedSupplement(path="mmc1.pdf", kind="pdf", role="methods", text=supp_text)],
    )


def test_bundle_text_is_main_plus_pdf_supplements():
    b = _bundle(PROTEIN, METHODS)
    assert PROTEIN in b.text and METHODS in b.text  # corpus = main + supplement


def test_build_extracted_spec_over_bundle_counts_from_main_methods_from_corpus():
    # The DE counts live in the main figures; the recipe lives in the supplement's extended methods.
    spec = build_extracted_spec(_bundle(PROTEIN, METHODS), "p")
    totals = {g.value for g in spec.goldens if g.metric == "de_total"}
    assert totals == {180}                       # counts recovered from the MAIN paper
    assert "edgeR" in spec.methods[0].tools      # recipe recovered from the SUPPLEMENT
    assert "TMM" in spec.methods[0].normalizations


def test_ingest_supplement_csv_inventories_table(tmp_path):
    # Hani ships csv supplements (JEV ships xlsx) — the contract must read both.
    csv = tmp_path / "mmc2.csv"
    csv.write_text("gene,Rod,Cone,Muller\nRHO,1,0,0\nOPN1SW,0,1,0\n", encoding="utf-8")
    s = ingest_supplement(csv, role="tables")
    assert s.kind == "csv" and s.role == "tables"
    assert s.sheets == {"mmc2": ["gene", "Rod", "Cone", "Muller"]}


def test_ingest_supplement_unknown_type_is_recorded_not_crashed(tmp_path):
    odd = tmp_path / "readme.txt"
    odd.write_text("notes", encoding="utf-8")
    s = ingest_supplement(odd)
    assert s.kind == "unknown" and "unrecognised" in s.note


def test_paper_bundle_find_table_locates_golden_sheet_by_name():
    b = PaperBundle(
        main=IngestedPaper(path="m.pdf", n_pages=1, text=""),
        supplements=[IngestedSupplement(path="s001.xlsx", kind="xlsx",
                                        sheets={"ST2": ["miRNA"], "ST6": ["Protein"]})],
    )
    assert b.find_table("st6") == ("s001.xlsx", "ST6")   # case-insensitive
    assert b.find_table("ST99") is None


# --- integration: the real JEV PDF (slow, opt-in; skipped if absent) ----------

DATA = Path("C:/Users/seamegdool/Desktop/Claude code and website tips/Data")
JEV_PDF = DATA / "Adrian" / "JEV2-12-12393.pdf"
JEV_XLSX = DATA / "Adrian" / "JEV2-12-12393-s001.xlsx"
RPGRIP1_PDF = DATA / "THL" / "mmc1.pdf"  # RPGRIP1 (Loi) main paper + supplement, combined
HANI_MAIN = DATA / "Hani" / "1-s2.0-S2213671122005914-main.pdf"
HANI_SUPPS = [
    (DATA / "Hani" / "1-s2.0-S2213671122005914-mmc1.pdf", "methods"),
    (DATA / "Hani" / "1-s2.0-S2213671122005914-mmc2.csv", "tables"),
]


@pytest.mark.skipif(not JEV_PDF.exists(), reason="JEV PDF not present (owner machine only)")
def test_integration_jev_pdf_recovers_printed_counts():
    from extract import ingest_pdf

    spec = build_extracted_spec(ingest_pdf(JEV_PDF), "jev")
    # The two headline DE-count groups the paper prints (matches reproduction_jev's goldens).
    de = {(g.figure, g.metric): g.value for g in spec.goldens}
    assert de[("1", "de_total")] == 35 and de[("1", "de_up")] == 12 and de[("1", "de_down")] == 23
    assert de[("4", "de_total")] == 180 and de[("4", "de_up")] == 61 and de[("4", "de_down")] == 119
    # Methods digest recovers the real recipe from the STAR methods.
    tools = spec.methods[0].tools
    assert {"edgeR", "limma", "fgsea"} <= set(tools)
    assert "TMM" in spec.methods[0].normalizations


@pytest.mark.skipif(not RPGRIP1_PDF.exists(), reason="RPGRIP1 PDF not present (owner machine only)")
def test_integration_rpgrip1_methods_digest_generalizes_cross_paper():
    # Cross-paper proof: the methods-digest lexicon recovers the RPGRIP1 recipe from a DIFFERENT
    # paper's PDF (edgeR/fgsea/Cepo/GLM-PCA/Louvain + TMM) — matching reproduction_rpgrip1's digest.
    # (Its DE counts use bespoke "signature" wording, not "N differentially expressed (up/down)",
    # so the slice-1 count reader is silent here — the vision/semantic layer, X1 slice-2, owns that.)
    from extract import ingest_pdf

    spec = build_extracted_spec(ingest_pdf(RPGRIP1_PDF), "rpgrip1")
    tools = set(spec.methods[0].tools)
    assert {"edgeR", "fgsea", "Cepo", "GLM-PCA", "Louvain"} <= tools
    assert "TMM" in spec.methods[0].normalizations


@pytest.mark.skipif(not (JEV_PDF.exists() and JEV_XLSX.exists()),
                    reason="JEV main+supplement not present (owner machine only)")
def test_integration_jev_two_input_intake_main_pdf_plus_xlsx():
    # E7: main PDF (figures/counts) + a SEPARATE xlsx supplement (the golden tables ST2/ST6).
    bundle = ingest_paper(JEV_PDF, [(JEV_XLSX, "tables")], paper_id="jev")
    assert bundle.main.n_pages > 0 and bundle.supplements[0].kind == "xlsx"
    # The supplement carries the deposited golden tables, findable by name without a full read.
    assert bundle.find_table("ST6") is not None and bundle.find_table("ST2") is not None
    # The DE counts still come from the main paper's figures.
    spec = build_extracted_spec(bundle, "jev")
    de = {(g.figure, g.metric): g.value for g in spec.goldens}
    assert de[("4", "de_total")] == 180 and de[("1", "de_total")] == 35


@pytest.mark.skipif(not HANI_MAIN.exists(),
                    reason="Hani main not present (owner machine only)")
def test_integration_hani_two_input_intake_main_pdf_plus_csv():
    # E7 cross-format: Hani ships csv supplements (not xlsx) + a separate methods PDF.
    supps = [s for s in HANI_SUPPS if s[0].exists()]
    bundle = ingest_paper(HANI_MAIN, supps, paper_id="hani")
    assert bundle.main.n_pages > 0
    kinds = {s.kind for s in bundle.supplements}
    assert "csv" in kinds  # the mmc2 Cepo marker matrix is a csv supplement
    # The methods digest reads the whole corpus (main + the methods-PDF supplement).
    spec = build_extracted_spec(bundle, "hani")
    assert spec.methods[0].tools  # a recipe is recovered from the corpus
