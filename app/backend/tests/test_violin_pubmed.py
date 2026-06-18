"""Violin known/novel marker annotation (Kim 2023 Fig 3A/B).

The annotation wires two shipped pieces — the ``violin`` skill and lit-synth's PubMed
lookup — into a "known vs novel marker" split. The query-building and figure-annotation are
pure (tested here without a network); the live esearch is exercised by a skipif test that
needs the NCBI key in the environment.
"""

import os

import pytest

from skills.violin.run import (
    KNOWN_COLOR,
    NOVEL_COLOR,
    annotate_pubmed,
    pubmed_query,
)


def _violin_spec():
    return {
        "data": [
            {"type": "violin", "name": "cluster 0", "y": [0.1, 0.2, 0.3]},
            {"type": "violin", "name": "cluster 1", "y": [1.1, 1.2, 1.3]},
        ],
        "layout": {"title": {"text": "RHO expression by leiden"}},
    }


# --- query building -----------------------------------------------------------


def test_pubmed_query_builds_title_abstract_term():
    assert pubmed_query("RHO") == "RHO[Title/Abstract]"
    assert pubmed_query("  GNAT1 ") == "GNAT1[Title/Abstract]"


def test_pubmed_query_ands_context():
    assert pubmed_query("RHO", "retina") == "RHO[Title/Abstract] AND retina[Title/Abstract]"


def test_pubmed_query_blank_gene_is_blank():
    assert pubmed_query("") == "" and pubmed_query("   ", "retina") == ""


# --- annotation overlay -------------------------------------------------------


def test_known_marker_tints_blue_and_badges():
    spec = annotate_pubmed(_violin_spec(), "RHO", 12431, known_min=5)
    annot = spec["layout"]["annotations"][0]
    assert "known marker" in annot["text"]
    assert "12,431 PubMed hits" in annot["text"]  # thousands-grouped
    assert annot["font"]["color"] == KNOWN_COLOR
    # every violin tinted by the bucket colour
    assert all(tr["fillcolor"] == KNOWN_COLOR for tr in spec["data"])


def test_novel_marker_tints_accent():
    spec = annotate_pubmed(_violin_spec(), "NOVELX", 2, known_min=5)
    annot = spec["layout"]["annotations"][0]
    assert "novel marker" in annot["text"]
    assert annot["font"]["color"] == NOVEL_COLOR
    assert all(tr["fillcolor"] == NOVEL_COLOR for tr in spec["data"])


def test_threshold_boundary_is_inclusive():
    # exactly known_min hits => known (>=)
    spec = annotate_pubmed(_violin_spec(), "EDGE", 5, known_min=5)
    assert "known marker" in spec["layout"]["annotations"][0]["text"]


def test_context_appears_in_badge():
    spec = annotate_pubmed(_violin_spec(), "RHO", 40, known_min=5, context="retina")
    assert "in retina" in spec["layout"]["annotations"][0]["text"]


def test_degraded_lookup_leaves_spec_untouched():
    before = _violin_spec()
    after = annotate_pubmed(before, "RHO", None, known_min=5)
    # count=None (offline/degraded) => no annotation, no colour change — figure still renders.
    assert "annotations" not in after["layout"]
    assert all("fillcolor" not in tr for tr in after["data"])


# --- live: real PubMed counts (skipped without the NCBI key) ------------------


@pytest.mark.skipif(
    not os.environ.get("SELOM_NCBI_API_KEY"),
    reason="needs SELOM_NCBI_API_KEY (owner machine / live network)",
)
def test_live_pubmed_count_splits_known_from_novel():
    from litsynth import lookup

    # RHO (rhodopsin) is a heavily-studied retinal marker -> thousands of hits (known).
    known = lookup.pubmed_count(pubmed_query("RHO", "retina"))
    assert known["degraded"] is False
    assert known["count"] is not None and known["count"] >= 5
