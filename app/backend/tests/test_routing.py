"""Skill Keyword Index — unit + 4-ledger backtest.

The backtest uses compact, faithful TEXT fixtures (the real method-nouns + figure legends of
each paper) — NOT the gitignored PDFs — so the suite is deterministic and offline. The golden is
each ledger's hand-built feasibility map (reproduction_{dorgau,hani,jev,rpgrip1}.build_ledger):
the router must reproduce each figure's in-scope skills and out-of-scope modality verdicts.
"""

from __future__ import annotations

import os

import pytest

import reproduction as R

from extract.routing import (
    NullVerifier,
    OperatorRouteVerifier,
    build_auto_ledger,
    build_vocab,
    figures_needing_review,
    mine_synonym_candidates,
    route_text,
    route_to_panels,
    verify_map,
)
from extract.routing.index import KeywordIndex
from extract.routing.models import RouteVerdict, VocabEntry, is_skill, skill_id
from extract.routing.route import default_index
from extract.routing.segment import segment
from extract.routing.vocab import _validate, load_synonyms, registry_entries


def _targets(route) -> set[str]:
    return {c.target for c in route.candidates}


def _paper_targets(fmap) -> set[str]:
    return {c.target for c in fmap.paper_targets}


def _fig(fmap, n: str):
    return next(r for r in fmap.figures if r.figure == n)


# --- vocabulary -------------------------------------------------------------

def test_curated_targets_all_resolve_to_live_registry():
    # the moat layer can't silently rot — every curated skill:/oos: target must be valid.
    _validate(load_synonyms())  # raises on a dangling target
    build_vocab()               # full build validates too


def test_registry_vocab_extends_per_skill():
    # adding a skill dir auto-routes its id with no synonym edit (the free-extension property).
    targets = {e.target for e in registry_entries()}
    assert "skill:integration" in targets
    assert "skill:trajectory" in targets


def test_unknown_synonym_target_raises():
    with pytest.raises(ValueError):
        _validate([VocabEntry(terms=["x"], target="skill:does_not_exist")])
    with pytest.raises(ValueError):
        _validate([VocabEntry(terms=["y"], target="oos:teleportation")])


# --- matcher / boundaries ---------------------------------------------------

def test_word_boundary_pca_not_inside_pvca():
    idx = default_index()
    hits = list(idx.find_in("we ran PVCA on the batches"))
    assert all(t != "skill:pca" for _, t, _, _ in hits)
    assert any(t == "skill:pvca" for _, t, _, _ in hits)


def test_longest_match_ssgsea_not_gsea():
    idx = default_index()
    hits = list(idx.find_in("single-sample enrichment via ssGSEA"))
    assert ("ssgsea", "skill:ssgsea") in [(term, t) for term, t, _, _ in hits]
    assert "skill:gsea" not in [t for _, t, _, _ in hits]


def test_negation_drops_the_hit():
    idx = default_index()
    assert not list(idx.find_in("we did not use Monocle for this analysis"))


# --- segmentation / refs-exclusion -----------------------------------------

def test_references_section_is_excluded():
    # Harmony named ONLY in the bibliography must not route to integration (the headline guard).
    text = (
        "Methods\n"
        "We clustered cells with Leiden and plotted a UMAP.\n"
        "References\n"
        "Korsunsky et al. Fast, sensitive integration with Harmony. Nat Methods 2019.\n"
    )
    seg = segment(text)
    assert "Harmony" in seg.refs and "Harmony" not in seg.methods
    fmap = route_text(text)
    assert "skill:integration" not in _paper_targets(fmap)
    assert "skill:umap_scrna" in _paper_targets(fmap)


def test_segment_splits_legends_per_figure():
    seg = segment(
        "Figure legends\n"
        "Figure 1. UMAP of the integrated atlas.\n"
        "Figure 2 | Spatial transcriptomics of the retina.\n"
    )
    assert set(seg.legends) == {"1", "2"}
    assert "UMAP" in seg.legends["1"]
    assert "Spatial" in seg.legends["2"]


def test_unmatched_surfaces_a_routed_gap():
    # a method-noun in the digest lexicon that the (custom, deliberately-gapped) index can't route
    # is surfaced as a skill-gap signal.
    gapped = KeywordIndex([VocabEntry(terms=["UMAP"], target="skill:umap_scrna")])
    fmap = route_text("Methods\nWe ran fgsea on the ranked genes and made a UMAP.\n", index=gapped)
    assert "fgsea" in fmap.unmatched_terms


# --- 4-ledger backtest ------------------------------------------------------

DORGAU = """
Methods
Single-cell RNA-seq libraries were processed with CellRanger and analysed in Seurat. After
FindVariableFeatures (2000 HVG) we performed Harmony batch correction, computed a UMAP on the
first harmony components, applied graph-based clustering, identified cluster markers with
FindMarkers, and ordered cells along pseudotime with Monocle 3. Spatial transcriptomics used 10x
Visium. Chromatin accessibility was profiled by scATAC-seq and analysed with Signac and chromVAR.
Gene regulatory networks were inferred with IPA and SCENIC+. Findings were validated by
immunofluorescence and confocal microscopy.
Figure legends
Figure 1. Integrated UMAP of the developing human retina; dotplot of marker genes from FindMarkers;
pseudotime density of progenitors; RPC trajectory inferred with Monocle 3; heatmap of genes along
pseudotime.
Figure 2 | Spatial transcriptomics (Visium) of the retina with H&E staining section.
Figure 4 | scATAC-seq differential accessibility; motif footprinting with chromVAR.
Figure 6 | Gene regulatory networks inferred with IPA and SCENIC+; regulon activity.
Figure 7 | Immunofluorescence validation; confocal microscopy of the ciliary margin.
"""


def test_backtest_dorgau():
    fmap = route_text(DORGAU, paper_id="dorgau")
    # Fig 1 = the in-scope scRNA core: Melody + trajectory + markers + umap all surface.
    f1 = _fig(fmap, "1")
    assert f1.in_scope
    assert {"skill:umap_scrna", "skill:trajectory", "skill:markers"} <= _targets(f1)
    # out-of-scope figures route to the right modality reason.
    assert _fig(fmap, "2").reason == "spatial"
    assert _fig(fmap, "4").reason == "atac"
    assert _fig(fmap, "6").reason == "grn"
    assert _fig(fmap, "7").reason == "wet_lab"
    # Melody dogfood signal: Harmony routes to the integration skill at the paper level.
    assert "skill:integration" in _paper_targets(fmap)


HANI = """
Methods
We computed cell-identity genes with Cepo, built a correlation heatmap of the statistics, and drew
box plots per cell type. Maturation was assessed by linear regression against developmental stage.
Marker expression was shown as violin plots over a UMAP of the integrated organoid atlas, and
cell type composition was quantified. Selected markers were validated by immunohistochemistry.
Figure legends
Figure 1. Stacked bar of cell type composition across datasets.
Figure 2. Correlation heatmap of Cepo statistics; box plots of expression.
Figure 3. Violin plots of marker genes; Cepo cell identity genes dotplot.
Figure 4. Scatter with linear regression against age.
Figure 6. UMAP of the integrated atlas; immunohistochemistry of retinal markers.
"""


def test_backtest_hani():
    fmap = route_text(HANI, paper_id="hani")
    assert "skill:composition" in _targets(_fig(fmap, "1"))
    assert {"skill:corr_heatmap", "skill:boxplot"} <= _targets(_fig(fmap, "2"))
    assert {"skill:violin", "skill:cepo"} <= _targets(_fig(fmap, "3"))
    assert "skill:regression" in _targets(_fig(fmap, "4"))
    assert "skill:umap_scrna" in _targets(_fig(fmap, "6"))


JEV = """
Methods
Differential expression of extracellular-vesicle cargo was tested with edgeR and limma-voom after
TMM normalization, summarised in volcano plots and heatmaps. Proteomes were compared by PCA. Gene
set enrichment used fgsea, and bulk cell-type composition was estimated by CIBERSORT deconvolution.
Figure legends
Figure 1. Heatmap of differentially expressed genes.
Figure 3. Volcano plot of EV miRNAs.
Figure 4. PCA of the proteomes; heatmap of cargo; volcano plot of differentially expressed proteins.
Figure 6. Stacked area of cell-type composition from deconvolution.
"""


def test_backtest_jev():
    fmap = route_text(JEV, paper_id="jev")
    assert _fig(fmap, "3").top == "skill:volcano"
    assert "skill:pca" in _targets(_fig(fmap, "4"))
    assert "skill:composition" in _targets(_fig(fmap, "6"))
    assert {"skill:deg", "skill:gsea", "skill:pca"} <= _paper_targets(fmap)


RPGRIP1 = """
Methods
Bulk differential expression was computed with edgeR, ranked genes were tested by GSEA (fgsea),
and samples were ordered by PCA. Single cells were annotated by reference-based cell type
annotation and cell type composition was compared between genotypes. Key findings were confirmed
by immunohistochemistry and RT-qPCR.
Figure legends
Figure 5. GSEA dotplot; PCA of samples; heatmap of differentially expressed genes;
immunohistochemistry; RT-qPCR validation.
Figure 6. UMAP with cell type annotation; cell type composition; GSEA terms.
"""


def test_backtest_rpgrip1():
    fmap = route_text(RPGRIP1, paper_id="rpgrip1")
    assert {"skill:deg", "skill:gsea", "skill:pca"} <= _paper_targets(fmap)
    assert "skill:gsea" in _targets(_fig(fmap, "5"))
    assert "skill:annotate" in _targets(_fig(fmap, "6"))
    # the wet-lab readouts are detected as out-of-scope somewhere in the paper.
    assert "oos:wet_lab" in _paper_targets(fmap)


# --- legend-segmentation hardening (4-layer) --------------------------------

# A garbled real-PDF caption: the marker reflows to a letter-spaced "F IG U R E " with the figure
# number stripped, inline between Results paragraphs, header-less. The figure number is recovered
# ordinally from the in-text references (the L2 recovery sweep).
GARBLED = (
    "Results\n"
    "Cells were profiled and visualised (Figure 1a) then clustered (Figure 1b).\n"
    "F IG U R E \n"
    "Integrated retinal atlas. (a) UMAP of the integrated dataset. (b) marker genes from FindMarkers.\n"
    "Pseudotime was then computed across the lineage (Figure 2a).\n"
    "F IG U R E \n"
    "Developmental lineage. (a) pseudotime trajectory inferred with Monocle 3.\n"
)


def test_garbled_letterspaced_caption_recovered_by_ordinal():
    fmap = route_text(GARBLED, paper_id="garbled")
    # both garbled captions detected; numbers recovered ordinally from the in-text Fig 1 / Fig 2 refs.
    assert {"1", "2"} <= {f.figure for f in fmap.figures}
    assert "skill:umap_scrna" in _targets(_fig(fmap, "1"))
    assert "skill:trajectory" in _targets(_fig(fmap, "2"))
    # a recovered caption is flagged recovered-tier (the AI-upsell signal), never falsely structured.
    assert _fig(fmap, "1").tier == "recovered"


def test_glyph_number_marker_tolerated():
    # some journals render the figure number in a custom font whose digit extracts as a private-use
    # glyph; the bare marker must still be recognised (number then recovered ordinally).
    from extract.routing.segment import _marker

    is_m, num, _ = _marker("F IG U R E ")
    assert is_m and num is None


# Two PRODUCTION caption forms the pypdfium2 extractor emits that the hand `_jev_text.txt` fixture did
# NOT reproduce — the s34 extraction↔recovery gap, now closed (`legend-extraction-gap-scope.md`).

# (1) Wiley/JEV: the marker word is intact but the figure NUMBER is a private-use-area font glyph and
# the caption text is INLINE on the same long line. Number recovered ordinally from the in-text refs.
GLYPH_INLINE = (
    "Results\n"
    "Cells were clustered and a UMAP drawn (Figure 1a), then pseudotime computed (Figure 2a).\n"
    f"FIGURE {chr(0xF6DC)} Integrated retinal atlas. (a) UMAP of the integrated dataset. "
    "(b) marker genes from FindMarkers.\n"
    f"FIGURE {chr(0xF63A)} Developmental lineage. (a) pseudotime trajectory inferred with Monocle 3.\n"
)


def test_inline_glyph_caption_recovered():
    fmap = route_text(GLYPH_INLINE, paper_id="glyph")
    assert {"1", "2"} <= {f.figure for f in fmap.figures}
    assert "skill:umap_scrna" in _targets(_fig(fmap, "1"))
    assert "skill:trajectory" in _targets(_fig(fmap, "2"))
    # an unmappable-glyph number is recovered ordinally -> recovered-tier (the AI-upsell signal).
    assert _fig(fmap, "1").tier == "recovered"


# (2) bioRxiv/preprint: a line-numbered manuscript — every line carries a manuscript line-number that
# breaks the ^figure anchor. The clean "Fig. N." caption is recovered by stripping the prefix.
LINENO_MANUSCRIPT = (
    "304 Figure legends\n"
    "305 Fig. 1. Pseudotime trajectory of rod photoreceptors during dark adaptation.\n"
    "306 (A) UMAP visualization of re-clustered rod subpopulations. (B) Slingshot pseudotime.\n"
    "314 Fig. 2. Lineage 1 exhibits enriched MYC programs.\n"
    "315 (A) enrichment analysis of transcription factors. (B-E) violin plots of Hallmark scores.\n"
)


def test_line_numbered_manuscript_caption_recovered():
    fmap = route_text(LINENO_MANUSCRIPT, paper_id="manuscript")
    assert {"1", "2"} <= {f.figure for f in fmap.figures}
    assert "skill:trajectory" in _targets(_fig(fmap, "1"))
    assert "skill:violin" in _targets(_fig(fmap, "2"))
    # a clean numbered caption (after de-numbering) is structured-tier, not recovery.
    assert _fig(fmap, "1").tier == "structured"


def _fake_refs(n: int) -> str:
    return "\n".join(
        f"Author{i}, A. B., & Body, C. D. ({2000 + i}). A study of things number {i}. "
        f"Journal of Things, {i}, {i * 10}. https://doi.org/10.1000/x{i}"
        for i in range(n)
    )


def test_headerless_reference_tail_excluded():
    # No "References" header — but a citation-dense tail must still be detected and excluded, so a
    # tool named ONLY in the bibliography (Harmony) does not route to integration (the headline guard).
    front = "\n".join(
        ["Methods", "We clustered cells with Leiden and made a UMAP."]
        + [f"Analysis step {i} was performed and the outcome recorded carefully." for i in range(12)]
        + ["Discussion", "Our findings align with prior literature on the subject."]
    )
    text = (front + "\n" + _fake_refs(12) + "\n"
            "Korsunsky, I., et al. (2019). Fast integration with Harmony. Nat Methods, 16, 1289. "
            "https://doi.org/10.1038/y\n")
    seg = segment(text)
    assert "Harmony" in seg.refs and "Harmony" not in seg.methods
    fmap = route_text(text)
    assert "skill:integration" not in _paper_targets(fmap)
    assert "skill:umap_scrna" in _paper_targets(fmap)


def test_relaxed_match_recovers_surface_variants():
    # exact vocab has "heatmap" / "differential expression"; the paper writes "heat map" /
    # "differentially expressed" — the L3 token-canonical pass closes the surface-form gap.
    fmap = route_text("Methods\nWe drew a heat map and tested differentially expressed transcripts.\n")
    assert "heatmap" in fmap.skills
    assert "deg" in fmap.skills


def test_forward_figure_attribution_prefers_following_ref():
    # figures are cited AFTER the claim ("…volcano plot (Figure 4e)"); the term must attach to the
    # following figure, not the previous sentence's figure.
    text = "Results\nWe computed a PCA (Figure 3a). The data are a volcano plot (Figure 4e).\n"
    fmap = route_text(text)
    assert "skill:volcano" in _targets(_fig(fmap, "4"))
    f3 = next((r for r in fmap.figures if r.figure == "3"), None)
    assert f3 is None or "skill:volcano" not in _targets(f3)


def test_tier_structured_for_clean_caption():
    clean = route_text("Figure legends\nFigure 1. UMAP of the integrated retinal atlas.\n")
    assert _fig(clean, "1").tier == "structured"


def test_repeated_term_does_not_inflate_score():
    once = route_text("Figure legends\nFigure 1. Volcano plot of the data.\n")
    thrice = route_text("Figure legends\nFigure 1. Volcano plot, volcano plot and a volcano plot.\n")
    s_once = next(c.score for c in _fig(once, "1").candidates if c.target == "skill:volcano")
    s_many = next(c.score for c in _fig(thrice, "1").candidates if c.target == "skill:volcano")
    assert s_once == s_many


def test_paper_inventory_lists_deduped_skills_and_oos():
    fmap = route_text(DORGAU, paper_id="dorgau")
    assert {"integration", "trajectory", "markers", "umap_scrna"} <= set(fmap.skills)
    assert {"spatial", "atac", "grn", "wet_lab"} <= set(fmap.out_of_scope)
    assert len(fmap.skills) == len(set(fmap.skills))  # the inventory is deduped


_JEV_TEXT = r"D:/selom-data/_jev_text.txt"


@pytest.mark.skipif(not os.path.exists(_JEV_TEXT), reason="real JEV PDF text not staged")
def test_real_jev_inventory_recall_and_tiers():
    fmap = route_text(open(_JEV_TEXT, encoding="utf-8").read(), paper_id="jev")
    # L3 core deliverable — the ledger's in-scope skills are all surfaced in the paper inventory.
    ledger = {"deg", "volcano", "pca", "heatmap", "composition", "umap_scrna", "markers", "trajectory"}
    assert ledger <= set(fmap.skills)
    assert "wet_lab" in fmap.out_of_scope
    # all eight garbled captions recovered, every figure flagged recovered-tier (the AI-upsell signal).
    assert len(fmap.figures) == 8
    assert fmap.tier_summary["recovered"] == 8 and fmap.tier_summary["structured"] == 0


# --- engine wiring (fast-follow #1): figure->skill map into the reproduction engine ----------

# The auto-map is a SUGGESTION skeleton at figure granularity (no fabricated sub-panel letters),
# so the golden is per-figure OVERLAP with the hand ledger's skills — not an exact panel match: the
# router legitimately surfaces a chart-form alternative (a "heatmap of DE genes" -> heatmap) where
# the hand author chose the more specific analysis skill (deg / pseudotime_genes). What must hold:
# every in-scope figure's suggestions overlap the hand skills, no real skill is dropped, and a
# purely out-of-scope figure maps to the right engine scope.


def _hand_map(build_ledger):
    """Per-figure hand-encoded in-scope skill sets + out-of-scope scopes from a real ledger."""
    skills: dict[str, set[str]] = {}
    oos: dict[str, set[str]] = {}
    for p in build_ledger().panels:
        if p.scope in R.OUT_OF_SCOPE_SCOPES:
            oos.setdefault(p.figure, set()).add(p.scope)
        elif p.skill_id:
            skills.setdefault(p.figure, set()).add(p.skill_id)
    return skills, oos


@pytest.mark.parametrize("text,module_name", [
    (DORGAU, "reproduction.papers.dorgau"), (HANI, "reproduction.papers.hani"),
    (JEV, "reproduction.papers.jev"), (RPGRIP1, "reproduction.papers.rpgrip1"),
])
def test_auto_map_matches_hand_ledger_per_figure(text, module_name):
    import importlib

    hand_skills, hand_oos = _hand_map(importlib.import_module(module_name).build_ledger)
    led = build_auto_ledger(text, paper_id=module_name)
    fmap = route_text(text, paper_id=module_name)
    for panel in led.panels:
        fig = panel.figure
        if panel.skill_id:  # in-scope figure: its suggestion set must overlap the hand skills
            fr = next(f for f in fmap.figures if f.figure == fig)
            auto_skills = {skill_id(c.target) for c in fr.candidates if is_skill(c.target)}
            if fig in hand_skills:
                assert auto_skills & hand_skills[fig], (fig, auto_skills, hand_skills[fig])
        else:               # purely out-of-scope figure: the mapped scope must match the ledger
            assert fig in hand_oos and panel.scope in hand_oos[fig], (fig, panel.scope)


def test_mixed_figure_keeps_in_scope_skill_not_dropped():
    # RPGRIP1 Fig 5 = GSEA/PCA/DE analysis + IHC/qPCR validation in ONE figure. The two wet-lab
    # terms out-score each single skill, but the figure must stay IN-SCOPE (the reproducible skills
    # are not dropped) with the co-present out-of-scope readout merely noted (the bug this guards).
    f5 = next(p for p in build_auto_ledger(RPGRIP1, paper_id="rpgrip1").panels if p.figure == "5")
    assert f5.skill_id in {"deg", "gsea", "pca", "heatmap"}
    assert f5.scope == R.TRANSCRIPTOMIC
    assert "wet_lab" in f5.note


def test_route_to_panels_one_panel_per_figure_unique_keys():
    panels = route_to_panels(route_text(DORGAU, paper_id="dorgau"))
    keys = [p.key for p in panels]
    assert len(keys) == len(set(keys))  # unique keys: one panel per figure, no engine shadowing
    assert {p.figure for p in panels} == {f.figure for f in route_text(DORGAU).figures}


def test_build_auto_ledger_drives_through_scorecard():
    led = build_auto_ledger(DORGAU, paper_id="dorgau")
    # the L3 paper-level inventory rides on the auto Paper.
    assert set(led.paper.methods_digest["skills"]) >= {"trajectory", "markers", "umap_scrna"}
    assert set(led.paper.methods_digest["out_of_scope"]) >= {"spatial", "atac", "grn", "wet_lab"}
    sc = R.build_scorecard(led)
    assert sc.n_panels == len(led.panels)
    assert sc.n_in_scope == 1  # only Fig 1 in-scope; spatial/atac/grn/wet-lab greyed/excluded


_DE_TEXT = ("Results\nWe identified 180 differentially expressed genes, with 61 upregulated and "
            "119 downregulated at p < 0.05 (Figure 4e), summarised as a volcano plot.\n")


def test_to_engine_panels_stamps_skill_id_only_with_feasibility():
    from extract.golden import build_extracted_spec, to_engine_panels

    spec = build_extracted_spec(None, "demo", text=_DE_TEXT)
    plain = to_engine_panels(spec)  # no feasibility -> unchanged (skill_id stays None)
    assert [p.key for p in plain] == ["4e"] and plain[0].skill_id is None
    stamped = to_engine_panels(spec, feasibility=route_text(_DE_TEXT, paper_id="demo"))
    assert stamped[0].skill_id == "deg" and stamped[0].scope == R.TRANSCRIPTOMIC


@pytest.mark.skipif(not os.path.exists(_JEV_TEXT), reason="real JEV PDF text not staged")
def test_real_jev_auto_ledger_skeleton():
    led = build_auto_ledger(open(_JEV_TEXT, encoding="utf-8").read(), paper_id="jev")
    inventory = set(led.paper.methods_digest["skills"])
    in_scope_panels = [p for p in led.panels if p.skill_id]
    assert in_scope_panels                                       # runnable figure panels exist
    assert all(p.skill_id in inventory for p in in_scope_panels)  # no skill invented off-inventory
    assert "wet_lab" in led.paper.methods_digest["out_of_scope"]


# --- L4 AI-verify + synonym-mining seam (fast-follow #2) --------------------

# The AI tier is gated + off the critical path: route_text() never calls it; verify_map() is an
# opt-in post-pass that only ever REFINES the deterministic figures (recovered/low-confidence ones),
# and the curated synonyms.json is never auto-written. Tested with a stand-in verifier, no live LLM.


class _OverrideVerifier:
    """A fake L4 verifier that overrides every flagged figure to a fixed target (stand-in for the
    gated Claude-as-gateway adjudicator)."""

    def __init__(self, target: str):
        self.target = target

    def verify_figure(self, figure):
        return RouteVerdict(figure=figure.figure, verdict="override", target=self.target,
                            confidence=0.95, note="fake adjudication")


def test_verify_null_is_a_noop():
    fmap = route_text(JEV, paper_id="jev")
    assert verify_map(fmap, NullVerifier()) == fmap  # deterministic core returned unchanged


def test_verify_override_applies_only_to_flagged_and_is_attributed():
    fmap = route_text(JEV, paper_id="jev")
    flagged = {fr.figure for fr in figures_needing_review(fmap)}
    assert flagged, "expected at least one low-confidence/recovered figure to adjudicate"
    out = verify_map(fmap, _OverrideVerifier("skill:volcano"))
    for fr in out.figures:
        before = _fig(fmap, fr.figure)
        if fr.figure in flagged:
            assert fr.ai is not None and fr.ai.verdict == "override"
            assert fr.top == "skill:volcano" and fr.confidence == 0.95
        else:  # an unflagged (structured, confident) figure is never touched
            assert fr.ai is None and fr.top == before.top


def test_figures_needing_review_skips_clean_structured_figure():
    clean = route_text("Figure legends\nFigure 1. Volcano plot of the data.\n")
    assert figures_needing_review(clean) == []  # structured + single confident candidate


def test_operator_route_verifier_replays_recorded_and_skips_unrecorded():
    fmap = route_text(JEV, paper_id="jev")
    fig = figures_needing_review(fmap)[0].figure
    op = OperatorRouteVerifier([RouteVerdict(figure=fig, verdict="confirm", target="skill:deg",
                                             confidence=0.9)])
    out = verify_map(fmap, op)
    assert _fig(out, fig).ai is not None and _fig(out, fig).ai.verdict == "confirm"
    # a flagged figure with no recorded verdict keeps the deterministic route (no fabrication).
    others = [f.figure for f in figures_needing_review(fmap) if f.figure != fig]
    for o in others:
        assert _fig(out, o).ai is None


def test_mine_synonym_candidates_surfaces_gap_without_writing_moat():
    from extract.routing.vocab import load_synonyms

    before = load_synonyms()
    gapped = KeywordIndex([VocabEntry(terms=["UMAP"], target="skill:umap_scrna"),
                           VocabEntry(terms=["edgeR", "differential expression"], target="skill:deg")])
    text = "Methods\nWe ran fgsea after edgeR differential expression and a UMAP.\n"
    fmap = route_text(text, index=gapped)
    assert "fgsea" in fmap.unmatched_terms and not fmap.synonym_candidates
    mined = mine_synonym_candidates(text, fmap, index=gapped)
    cand = next(c for c in mined.synonym_candidates if c.term == "fgsea")
    assert "skill:deg" in cand.co_targets  # co-mentioned routed skill surfaced for review
    assert load_synonyms() == before        # the curated moat was NOT auto-written


@pytest.mark.skipif(not os.path.exists(_JEV_TEXT), reason="real JEV PDF text not staged")
def test_real_jev_all_recovered_figures_flagged_for_review():
    fmap = route_text(open(_JEV_TEXT, encoding="utf-8").read(), paper_id="jev")
    # every recovered-tier figure (the real JEV had 8) is offered to the paid L4 tier.
    assert len(figures_needing_review(fmap)) == fmap.tier_summary["recovered"] == 8


# --- endpoint ---------------------------------------------------------------

def test_route_endpoint_returns_feasibility_map():
    from fastapi.testclient import TestClient

    from main import app

    resp = TestClient(app).post("/papers/route", json={"text": DORGAU, "paper_id": "dorgau"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["paper_id"] == "dorgau"
    reasons = {f["reason"] for f in body["figures"] if not f["in_scope"]}
    assert {"spatial", "atac", "grn", "wet_lab"} <= reasons
