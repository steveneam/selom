"""Skill Keyword Index — unit + 4-ledger backtest.

The backtest uses compact, faithful TEXT fixtures (the real method-nouns + figure legends of
each paper) — NOT the gitignored PDFs — so the suite is deterministic and offline. The golden is
each ledger's hand-built feasibility map (reproduction_{dorgau,hani,jev,rpgrip1}.build_ledger):
the router must reproduce each figure's in-scope skills and out-of-scope modality verdicts.
"""

from __future__ import annotations

import pytest

from extract.routing import build_vocab, route_text
from extract.routing.index import KeywordIndex
from extract.routing.models import VocabEntry
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
