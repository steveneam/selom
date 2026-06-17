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
    VisionClassifier,
    VisionUnavailable,
    build_extracted_spec,
    classify_scope,
    extract_de_counts,
    extract_methods_digest,
    find_figures_vs_methods,
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


# --- integration: the real JEV PDF (slow, opt-in; skipped if absent) ----------

DATA = Path("C:/Users/seamegdool/Desktop/Claude code and website tips/Data")
JEV_PDF = DATA / "Adrian" / "JEV2-12-12393.pdf"
RPGRIP1_PDF = DATA / "THL" / "mmc1.pdf"  # RPGRIP1 (Loi) main paper + supplement, combined


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
