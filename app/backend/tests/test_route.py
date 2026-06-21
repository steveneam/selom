"""P3 — RAW-data routing: a classified DataBundle -> a registry-validated skill pipeline.

The data-side complement of the paper router. Suggestions are filtered to installed skills,
so every returned skill_id is real; an unrecognized modality returns an honest empty pipeline.
"""

from __future__ import annotations

import pandas as pd

from engine import (
    BULK_COUNTS,
    DE_RESULTS,
    METABOLOMICS,
    SC_COUNTS,
    UNKNOWN,
    DataBundle,
    route_data,
)
from engine.models import PROTEOMICS
from skills.registry import list_skill_ids

_DF = pd.DataFrame({"a": [1]})  # payload is irrelevant; routing keys on bundle.kind


def _ids(routing):
    return [s.skill_id for s in routing.steps]


def test_bulk_counts_pipeline():
    r = route_data(DataBundle(payload=_DF, kind=BULK_COUNTS))
    assert "deg" in _ids(r) and "volcano" in _ids(r)
    assert r.confident is True


def test_de_results_skips_deg():
    r = route_data(DataBundle(payload=_DF, kind=DE_RESULTS))
    ids = _ids(r)
    assert "volcano" in ids and "deg" not in ids   # already have stats; no re-analysis
    assert r.confident is True


def test_sc_counts_pipeline():
    r = route_data(DataBundle(payload=_DF, kind=SC_COUNTS))
    assert "umap_scrna" in _ids(r)
    assert r.confident is True


def test_proteomics_pipeline():
    r = route_data(DataBundle(payload=_DF, kind=PROTEOMICS))
    assert "proteomics_de" in _ids(r)
    assert r.confident is True


def test_metabolomics_is_honest_coming_soon():
    r = route_data(DataBundle(payload=_DF, kind=METABOLOMICS))
    assert r.steps == []
    assert r.confident is False
    assert "coming soon" in r.note.lower()


def test_unknown_is_honest_no_pipeline():
    r = route_data(DataBundle(payload=_DF, kind=UNKNOWN))
    assert r.steps == []
    assert r.confident is False


def test_every_suggested_skill_is_real():
    # No fabricated steps: every suggested skill_id resolves in the live registry.
    installed = set(list_skill_ids())
    for kind in (BULK_COUNTS, DE_RESULTS, SC_COUNTS, PROTEOMICS):
        r = route_data(DataBundle(payload=_DF, kind=kind))
        assert r.steps, f"{kind} should suggest a pipeline"
        assert all(s.skill_id in installed for s in r.steps)
