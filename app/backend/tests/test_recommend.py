"""engine.recommend_params + POST /skills/{id}/recommend-params — the analyze-stage DETERMINISTIC
best-practice param recommender behind the Layer A "Auto-tune" button (docs/auto-tune/spec.md).

Asserts: the static baseline equals the skill defaults; the one curated rule (umap_scrna n_hvg → ~2000)
fires + is clamped + validated; the design params are NOT touched (no parallel path with the ingest
questionnaire); unknown skill → 404."""

import pytest
from fastapi.testclient import TestClient

from engine.recommend import RecommendContext, _clamp, recommend_params
from skills.contract import defaults, load_skill, validate_param_ranges
from main import app

client = TestClient(app)


def _by_key(recs):
    return {r.key: r for r in recs.recs}


# --- static baseline: for a skill with no curated rule, every rec == its param_spec default ----------

def test_static_baseline_equals_skill_defaults():
    recs = recommend_params("deg", RecommendContext())
    base = defaults(load_skill("deg"))
    got = _by_key(recs)
    assert set(got) == set(base)
    for key, default in base.items():
        assert got[key].value == default
        assert got[key].default == default
        assert got[key].scaled is False
        assert got[key].why == "skill default"
    assert recs.note == "These are the best-practice defaults for this skill."


def test_every_recommended_value_is_spec_valid():
    # R3 — the button never emits an out-of-range / wrong-type / bad-option knob.
    for skill_id in ("deg", "umap_scrna"):
        spec = load_skill(skill_id)
        recs = recommend_params(skill_id, RecommendContext())
        for rec in recs.recs:
            assert validate_param_ranges(spec, {rec.key: rec.value}) == []


# --- the curated rule: umap_scrna selects ~2000 highly-variable genes (default is 0 = all genes) -----

def test_umap_scrna_recommends_2000_hvg():
    recs = recommend_params("umap_scrna", RecommendContext())
    got = _by_key(recs)
    assert got["n_hvg"].value == 2000
    assert got["n_hvg"].default == 0            # the raw param_spec default
    assert got["n_hvg"].scaled is True
    assert got["n_hvg"].why                     # a non-empty plain-language reason
    # everything else for umap stays the static default (only n_hvg is curated)
    assert got["n_neighbors"].scaled is False
    assert got["n_pcs"].scaled is False
    # the summary note reflects the one scaled setting
    assert "Set 1 best-practice input" in recs.note


def test_curated_value_is_clamped_to_the_param_range():
    # A curated value beyond the spec's max is clamped, never emitted invalid (n_hvg range is [0, 10000];
    # n_neighbors range is [2, 100]).
    assert _clamp({"min": 2, "max": 100}, 2000) == 100
    assert _clamp({"min": 0, "max": 10000}, 2000) == 2000
    assert _clamp({"min": 5, "max": 50}, 1) == 5
    assert _clamp({"min": 0, "max": 100}, "auto") == "auto"   # non-numeric passes through
    assert _clamp({"min": 0, "max": 100}, True) is True       # bool passes through (not clamped)


# --- no parallel path: the DESIGN params belong to ingest; analyze must NOT re-map them --------------

def test_deg_design_params_are_not_touched_even_with_design_context():
    # The intake questionnaire (FE lib/intake/design.ts) owns reference/treatment/condition_col/sample_col.
    # A design in the context must NOT make the analyze recommender re-map them (that would be a second,
    # drifting mapper). They stay the static default. See docs/auto-tune/spec.md §Design.
    ctx = RecommendContext(
        data_kind="bulk_counts",
        design={"needs_design": True, "best_group": "__column_names__",
                "group_candidates": [{"key": "__column_names__", "label": "sample columns",
                                      "levels": [{"name": "Control", "n_replicates": 3},
                                                 {"name": "PDE6B", "n_replicates": 3}],
                                      "n_levels": 2, "reference_guess": "Control"}],
                "reference_guess": "Control", "sample_col": None},
    )
    got = _by_key(recommend_params("deg", ctx))
    for key in ("reference", "treatment", "condition_col", "sample_col"):
        assert got[key].value == ""
        assert got[key].scaled is False


def test_unknown_skill_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        recommend_params("not_a_real_skill", RecommendContext())


# --- the endpoint (wire) ----------------------------------------------------------------------------

def test_endpoint_returns_recommendations():
    r = client.post("/skills/umap_scrna/recommend-params", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["skill_id"] == "umap_scrna"
    n_hvg = next(rec for rec in body["recs"] if rec["key"] == "n_hvg")
    assert n_hvg["value"] == 2000
    assert n_hvg["scaled"] is True


def test_endpoint_forwards_data_context_without_error():
    r = client.post("/skills/deg/recommend-params",
                    json={"data_columns": ["gene", "Control_1", "PDE6B_1"],
                          "data_kind": "bulk_counts", "data_n_numeric_cols": 2})
    assert r.status_code == 200
    assert r.json()["skill_id"] == "deg"


def test_endpoint_unknown_skill_is_404():
    r = client.post("/skills/not_a_real_skill/recommend-params", json={})
    assert r.status_code == 404
