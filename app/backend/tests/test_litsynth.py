"""lit-synthesizer Phase A — the deterministic multi-skill methods synthesizer."""

import pytest

import litsynth
from companions import methods
from litsynth.citations import CANONICAL_REFS, citations_for
from skills.contract import load_skill


def test_compose_orders_paragraphs_and_leads_with_intro():
    section = litsynth.compose_methods(
        [
            {"skill_id": "deg", "order": 2, "params": {"top_n": "25"}},
            {"skill_id": "umap_scrna", "order": 1},
        ],
        "scrna",
    )
    # Explicit order wins over input position: umap (1) before deg (2).
    assert section.skill_ids == ["umap_scrna", "deg"]
    assert section.intro.startswith("Single-cell RNA-seq")
    # First paragraph IS the umap body, verbatim (single source of truth).
    assert section.paragraphs[0] == methods.build_body(load_skill("umap_scrna"), {})[0]
    # Resolved params are quoted in the deg paragraph.
    assert "top 25 genes" in section.paragraphs[1]
    # The joined text leads with the intro and ends with ONE consolidated attribution.
    assert section.text.startswith(section.intro)
    assert "All analyses were performed using Selom" in section.text
    assert section.text.rstrip().endswith(".")
    # No per-paragraph attribution leaked into the story.
    assert "Analysis was performed using Selom (skill" not in section.text


def test_citations_deduped_first_seen_order():
    section = litsynth.compose_methods(
        [
            {"skill_id": "umap_scrna"},   # SCANPY, UMAP
            {"skill_id": "cluster"},      # SCANPY, LEIDEN, SILHOUETTE
            {"skill_id": "deg"},          # SCANPY, PYDESEQ2, DESEQ2, BH
        ],
        "scrna",
    )
    # Nothing duplicated; SCANPY appears once, in its first-seen position.
    assert len(section.citations) == len(set(section.citations))
    assert section.citations[0] == methods.SCANPY
    assert section.citations.count(methods.SCANPY) == 1
    # Cross-skill order preserved.
    assert section.citations.index(methods.UMAP) < section.citations.index(methods.LEIDEN)


def test_dataset_descriptor_leads_intro():
    section = litsynth.compose_methods(
        [{"skill_id": "volcano"}], "bulk", dataset="The pbmc3k dataset"
    )
    assert section.intro.startswith("The pbmc3k dataset. Bulk RNA-seq")
    assert section.text.startswith("The pbmc3k dataset. Bulk RNA-seq")


def test_unknown_modality_degrades_to_generic_intro():
    section = litsynth.compose_methods([{"skill_id": "volcano"}], "mystery-omics")
    assert section.intro == "The data were analyzed as follows."
    assert section.modality == "mystery-omics"


def test_single_run_parity_with_build_body():
    # A one-skill story's paragraph and citations ARE methods.build_body.
    spec = load_skill("volcano")
    params = {"fc_threshold": "1.5"}
    section = litsynth.compose_methods([{"skill_id": "volcano", "params": params}], "bulk")
    assert section.paragraphs == [methods.build_body(spec, params)[0]]
    assert section.citations == methods.build_body(spec, params)[1]


def test_build_output_unchanged_by_refactor():
    # The single-figure build() still == body + the standard attribution sentence.
    spec = load_skill("deg")
    body, cites = methods.build_body(spec, {"top_n": "10"})
    out = methods.build(spec, {"top_n": "10"})
    assert out["text"] == f"{body} Analysis was performed using Selom (skill 'deg' v{spec.version})."
    assert out["citations"] == cites


def test_unknown_skill_raises_clean_value_error():
    with pytest.raises(ValueError, match="unknown skill"):
        litsynth.compose_methods([{"skill_id": "does-not-exist"}], "bulk")


def test_empty_runs_rejected():
    with pytest.raises(ValueError):
        litsynth.compose_methods([], "bulk")


def test_citations_for_single_sources_methods():
    assert citations_for("deg", {"top_n": "10"}) == methods.build_body(load_skill("deg"), {"top_n": "10"})[1]
    # The canonical refs are re-exported (not copied) from methods.py.
    assert CANONICAL_REFS["SCANPY"] == methods.SCANPY
    assert "SMYTH" in CANONICAL_REFS
