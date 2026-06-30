"""S4 proof — CapabilityGap aggregation + persistence, select_skill, and informational helpers.

All tests run in the fast gate (``pytest -m "not slow"``).  No live LLM, no heavy file
I/O beyond tmp_path for JsonlGapStore persistence tests.

Part A — Gap persistence + aggregation + categorization + GET /ai/gaps
Part B — select_skill: P3 route action with compat.fit gating
Part C — explain_score / propose_sweep: informational path, degrade-clean, NOT actions

Fixtures:
  _stub_engine   — forces SELOM_SKILLS_ENGINE=stub (autouse)
  _reset_gaps    — resets the module-level gap store to a fresh InMemoryGapStore before
                   and after each test (autouse) — prevents bleed between tests and
                   between tests that override the store.
"""

from __future__ import annotations

import pytest

from ai import gaps as g
from ai.gap_store import InMemoryGapStore, JsonlGapStore, _derive_category
from ai.execute import apply_plan, validate_action
from ai.gateway import NullActionGateway, OperatorActionGateway
from ai.models import Action, ActionContext, ActionPlan, CapabilityGap


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _stub_engine(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


@pytest.fixture(autouse=True)
def _reset_gaps():
    """Reset to a fresh InMemoryGapStore before and after every test."""
    g._set_store_for_test(InMemoryGapStore())
    yield
    g._set_store_for_test(InMemoryGapStore())


# ============================================================================
# PART A — CapabilityGap aggregation + persistence + GET /ai/gaps
# ============================================================================

# ---------------------------------------------------------------------------
# A1 — derive_category normalizes map_columns + apply_cleaning_step
# ---------------------------------------------------------------------------

def test_category_map_columns_is_engine_capability_missing():
    """map_columns (unmet=missing_column_op) → engine_capability_missing."""
    gap = CapabilityGap(
        stage="ingest", intent="map_columns", unmet="missing_column_op",
        attempted={}, context_hash="aaa", skill_id=None,
    )
    assert _derive_category(gap) == "engine_capability_missing"


def test_category_apply_cleaning_step_is_engine_capability_missing():
    """apply_cleaning_step (unmet=validation_blocked) → engine_capability_missing.

    This is the key normalization: both gap codes map to the same backlog category,
    distinct from param_blocked (which also uses validation_blocked for real params).
    """
    gap = CapabilityGap(
        stage="ingest", intent="apply_cleaning_step", unmet="validation_blocked",
        attempted={}, context_hash="bbb", skill_id=None,
    )
    assert _derive_category(gap) == "engine_capability_missing"


def test_category_set_param_validation_blocked_is_param_blocked():
    """set_param (unmet=validation_blocked) → param_blocked, NOT engine_capability_missing.

    The normalization distinguishes between 'engine has no hook' (apply_cleaning_step)
    and 'engine has the hook but the value is out of range' (set_param).
    """
    gap = CapabilityGap(
        stage="analyze", intent="set_param", unmet="validation_blocked",
        attempted={}, context_hash="ccc", skill_id="volcano",
    )
    assert _derive_category(gap) == "param_blocked"


def test_category_param_not_in_spec_is_param_blocked():
    gap = CapabilityGap(
        stage="analyze", intent="set_param", unmet="param_not_in_spec",
        attempted={}, context_hash="ddd", skill_id="volcano",
    )
    assert _derive_category(gap) == "param_blocked"


def test_category_unsupported_filter_is_param_blocked():
    gap = CapabilityGap(
        stage="analyze", intent="add_filter", unmet="unsupported_filter",
        attempted={}, context_hash="eee", skill_id="volcano",
    )
    assert _derive_category(gap) == "param_blocked"


def test_category_no_such_action_is_unknown_action():
    gap = CapabilityGap(
        stage="analyze", intent="fantasy_op", unmet="no_such_action",
        attempted={}, context_hash="fff", skill_id=None,
    )
    assert _derive_category(gap) == "unknown_action"


def test_category_no_fitting_skill():
    gap = CapabilityGap(
        stage="route", intent="select_skill", unmet="no_fitting_skill",
        attempted={}, context_hash="ggg", skill_id=None,
    )
    assert _derive_category(gap) == "no_fitting_skill"


# ---------------------------------------------------------------------------
# A2 — InMemoryGapStore dedup + count + category
# ---------------------------------------------------------------------------

def test_inmemory_store_record_dedup_and_category():
    """InMemoryGapStore: dedup by context_hash, count increments, category present."""
    store = InMemoryGapStore()
    gap = CapabilityGap(
        stage="ingest", intent="map_columns", unmet="missing_column_op",
        attempted={"k": "v"}, context_hash="h001", skill_id=None,
    )
    store.record(gap)
    store.record(gap)

    entries = store.list_gaps()
    assert len(entries) == 1
    assert entries[0]["count"] == 2
    assert entries[0]["category"] == "engine_capability_missing"
    assert entries[0]["gap"].unmet == "missing_column_op"


def test_inmemory_store_sorted_by_count_desc():
    """list_gaps returns entries sorted by count descending."""
    store = InMemoryGapStore()
    gap_a = CapabilityGap(
        stage="analyze", intent="set_param", unmet="validation_blocked",
        attempted={}, context_hash="aa", skill_id="volcano",
    )
    gap_b = CapabilityGap(
        stage="ingest", intent="map_columns", unmet="missing_column_op",
        attempted={}, context_hash="bb", skill_id=None,
    )
    store.record(gap_a)
    store.record(gap_b)
    store.record(gap_b)  # gap_b appears twice

    entries = store.list_gaps()
    assert entries[0]["count"] == 2  # gap_b first (higher count)
    assert entries[1]["count"] == 1


def test_inmemory_store_reset():
    store = InMemoryGapStore()
    gap = CapabilityGap(
        stage="analyze", intent="set_param", unmet="param_not_in_spec",
        attempted={}, context_hash="r01", skill_id=None,
    )
    store.record(gap)
    store.reset()
    assert store.list_gaps() == []


# ---------------------------------------------------------------------------
# A3 — JsonlGapStore persistence ("restart simulation")
# ---------------------------------------------------------------------------

def test_jsonl_store_persists_across_instances(tmp_path):
    """Records written by one JsonlGapStore instance are readable by a new instance.

    This is the 'restart simulation': a new store instance (simulating a fresh
    process start) reads the persisted gaps from the JSONL file.
    """
    path = tmp_path / "gaps.jsonl"
    gap = CapabilityGap(
        stage="ingest", intent="map_columns", unmet="missing_column_op",
        attempted={"logFC": "log2FoldChange"}, context_hash="p001", skill_id=None,
    )

    store1 = JsonlGapStore(path)
    store1.record(gap)
    store1.record(gap)  # count should be 2

    # Simulate restart — create a brand-new instance pointing at the same file.
    store2 = JsonlGapStore(path)
    entries = store2.list_gaps()

    assert len(entries) == 1, "dedup by context_hash: one entry, not two"
    assert entries[0]["count"] == 2
    assert entries[0]["category"] == "engine_capability_missing"
    assert entries[0]["gap"].unmet == "missing_column_op"


def test_jsonl_store_empty_before_any_record(tmp_path):
    store = JsonlGapStore(tmp_path / "gaps.jsonl")
    assert store.list_gaps() == []


def test_jsonl_store_reset_clears_file(tmp_path):
    path = tmp_path / "gaps.jsonl"
    store = JsonlGapStore(path)
    gap = CapabilityGap(
        stage="ingest", intent="map_columns", unmet="missing_column_op",
        attempted={}, context_hash="r02", skill_id=None,
    )
    store.record(gap)
    store.reset()

    assert not path.exists() or path.stat().st_size == 0, "reset should remove or empty the file"
    assert store.list_gaps() == []


def test_jsonl_store_multi_kind_aggregation(tmp_path):
    """Different context_hashes → separate entries; category derived correctly for each."""
    path = tmp_path / "gaps.jsonl"
    store = JsonlGapStore(path)

    g1 = CapabilityGap(
        stage="ingest", intent="map_columns", unmet="missing_column_op",
        attempted={}, context_hash="x1", skill_id=None,
    )
    g2 = CapabilityGap(
        stage="ingest", intent="apply_cleaning_step", unmet="validation_blocked",
        attempted={}, context_hash="x2", skill_id=None,
    )
    store.record(g1)
    store.record(g1)
    store.record(g2)

    entries = store.list_gaps()
    assert len(entries) == 2
    categories = {e["category"] for e in entries}
    # Both engine-capability gaps → same category
    assert categories == {"engine_capability_missing"}
    counts = sorted(e["count"] for e in entries)
    assert counts == [1, 2]


# ---------------------------------------------------------------------------
# A4 — Module-level delegate + GET /ai/gaps
# ---------------------------------------------------------------------------

def test_module_delegate_record_list_reset():
    """Module-level record/list_gaps/reset delegate to the active store correctly."""
    from ai.gaps import context_hash as ch

    gap = CapabilityGap(
        stage="analyze", intent="set_param", unmet="param_not_in_spec",
        attempted={}, context_hash=ch("analyze", "set_param", "param_not_in_spec", "volcano"),
        skill_id="volcano",
    )
    g.record(gap)
    g.record(gap)

    entries = g.list_gaps()
    assert len(entries) == 1
    assert entries[0]["count"] == 2
    assert entries[0]["category"] == "param_blocked"

    g.reset()
    assert g.list_gaps() == []


def test_gaps_endpoint_returns_ranked_categorized_backlog():
    """GET /ai/gaps returns ranked list with required fields; review-only (no registry mutation)."""
    from ai import registry
    from ai.gaps import context_hash as ch

    # Record two different gap types.
    g1 = CapabilityGap(
        stage="ingest", intent="map_columns", unmet="missing_column_op",
        attempted={"a": 1}, context_hash=ch("ingest", "map_columns", "missing_column_op", None),
        skill_id=None,
    )
    g2 = CapabilityGap(
        stage="analyze", intent="set_param", unmet="param_not_in_spec",
        attempted={"b": 2},
        context_hash=ch("analyze", "set_param", "param_not_in_spec", "volcano"),
        skill_id="volcano",
    )
    g.record(g1)
    g.record(g1)  # count=2
    g.record(g2)  # count=1

    # Inline what the endpoint does (avoids heavy TestClient/app setup in the fast gate).
    from routers.ai import get_gaps

    keys_before = set(registry.ACTION_REGISTRY)
    result = get_gaps()
    keys_after = set(registry.ACTION_REGISTRY)

    # Review-only: registry unchanged.
    assert keys_before == keys_after, "GET /ai/gaps must not mutate ACTION_REGISTRY"

    # Ranked: highest count first.
    assert len(result) == 2
    assert result[0]["count"] == 2
    assert result[1]["count"] == 1

    # Required fields present.
    required_keys = {"context_hash", "stage", "unmet", "category", "skill_id", "count", "sample_attempt"}
    for entry in result:
        assert required_keys.issubset(entry.keys()), f"Missing keys: {required_keys - entry.keys()}"

    # Category correct for map_columns.
    mc_entry = next(e for e in result if e["unmet"] == "missing_column_op")
    assert mc_entry["category"] == "engine_capability_missing"

    sp_entry = next(e for e in result if e["unmet"] == "param_not_in_spec")
    assert sp_entry["category"] == "param_blocked"


def test_gaps_endpoint_never_mutates_registry():
    """Calling GET /ai/gaps multiple times leaves ACTION_REGISTRY byte-identical."""
    from ai import registry
    from routers.ai import get_gaps

    keys_before = set(registry.ACTION_REGISTRY)
    for _ in range(5):
        get_gaps()
    keys_after = set(registry.ACTION_REGISTRY)
    assert keys_before == keys_after


# ============================================================================
# PART B — select_skill (P3 route action)
# ============================================================================

def test_select_skill_in_action_types_and_literal():
    """select_skill is registered in ACTION_TYPES, ActionType Literal, and ACTION_REGISTRY.

    The structure guard enforces this triple-consistency at CI time; this test
    also catches it in the targeted S4 run.
    """
    from typing import get_args
    from ai import models, registry

    assert "select_skill" in models.ACTION_TYPES
    assert "select_skill" in get_args(models.ActionType)
    assert "select_skill" in registry.ACTION_REGISTRY

    # Triple-consistency still holds.
    assert set(registry.ACTION_REGISTRY) == set(models.ACTION_TYPES)
    assert set(models.ACTION_TYPES) == set(get_args(models.ActionType))


def test_select_skill_valid_registered_skill_validates_ok():
    """A skill that is in the registry and has no data_fit incompatibility → ok.

    volcano is in STUB_NATIVE so it resolves even in stub mode.
    """
    ctx = ActionContext(stage="route", skill_id=None, data_fit=None)
    action = Action(type="select_skill", target="volcano", payload={"skill_id": "volcano"})

    outcome = validate_action(action, ctx)
    assert outcome.ok, f"Expected ok=True for registered skill 'volcano'; errors: {outcome.errors}"


def test_select_skill_apply_stages_selected_skill():
    """_apply_select_skill stages _selected_skill in the params delta."""
    from ai import registry as reg

    ctx = ActionContext(stage="route")
    action = Action(type="select_skill", target="volcano", payload={"skill_id": "volcano"})

    effect = reg.get("select_skill").apply(action, ctx)
    assert effect == {"params": {"_selected_skill": "volcano"}}


def test_select_skill_staged_via_apply_plan():
    """select_skill flows through apply_plan → status=staged, staged_params populated."""
    ctx = ActionContext(stage="route", data_fit=None)
    plan = ActionPlan(
        goal="switch to volcano",
        actions=[Action(type="select_skill", target="volcano", payload={"skill_id": "volcano"})],
    )

    turn = apply_plan(plan, ctx)

    assert len(turn.results) == 1
    result = turn.results[0]
    assert result.status == "staged", f"Expected staged, got {result.status!r}"
    assert turn.staged_params == {"_selected_skill": "volcano"}


def test_select_skill_unregistered_skill_emits_no_fitting_skill_gap():
    """A skill not in the registry → rejected with gap(no_fitting_skill)."""
    ctx = ActionContext(stage="route", data_fit=None)
    action = Action(type="select_skill", target="", payload={"skill_id": "nonexistent_skill_xyz"})

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "no_fitting_skill"


def test_select_skill_incompatible_data_emits_gap():
    """When data_fit shows a sc_matrix file and the target is a table skill → gap(no_fitting_skill).

    Simulates the compat gate: a single-cell matrix (SC_COUNTS kind) is a certain
    mismatch for volcano (which needs a DE table).
    """
    from engine.models import SC_COUNTS

    data_fit = {
        "path": "/fake/data.h5ad",
        "filename": "data.h5ad",
        "kind": SC_COUNTS,  # a matrix kind
        "score": 90,
        "qc_ok": True,
        "compatible": True,
    }
    ctx = ActionContext(stage="route", data_fit=data_fit, data_columns=[])
    action = Action(type="select_skill", target="volcano", payload={"skill_id": "volcano"})

    outcome = validate_action(action, ctx)

    # SC_COUNTS vs volcano (table skill) → certain mismatch → gap
    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "no_fitting_skill"


def test_select_skill_compatible_data_validates_ok():
    """When data_fit shows a DE table and the target is volcano → validates ok."""
    from engine.models import DE_RESULTS

    data_fit = {
        "path": "/fake/de.csv",
        "filename": "de.csv",
        "kind": DE_RESULTS,  # a table kind that fits volcano
        "score": 85,
        "qc_ok": True,
        "compatible": True,
    }
    # Provide columns so the L1 schema check can confirm the fit.
    ctx = ActionContext(
        stage="route",
        data_fit=data_fit,
        data_columns=["gene", "logFC", "padj"],
    )
    action = Action(type="select_skill", target="volcano", payload={"skill_id": "volcano"})

    outcome = validate_action(action, ctx)
    assert outcome.ok, f"Expected ok=True for DE_RESULTS data vs volcano; errors: {outcome.errors}"


def test_select_skill_missing_skill_id_in_payload():
    """A select_skill with no skill_id in payload or target → rejected (malformed)."""
    ctx = ActionContext(stage="route", data_fit=None)
    action = Action(type="select_skill", target="", payload={})

    outcome = validate_action(action, ctx)
    assert not outcome.ok
    assert "skill_id" in outcome.errors[0]


def test_select_skill_gap_recorded_and_categorized():
    """An incompatible select_skill records a gap with category=no_fitting_skill."""
    from engine.models import SC_COUNTS

    data_fit = {"kind": SC_COUNTS, "score": 90, "qc_ok": True, "compatible": True, "path": ""}
    ctx = ActionContext(stage="route", data_fit=data_fit, data_columns=[])
    plan = ActionPlan(
        goal="switch to volcano",
        actions=[Action(type="select_skill", target="volcano", payload={"skill_id": "volcano"})],
    )

    turn = apply_plan(plan, ctx)

    # The result should be "gap" (no_fitting_skill is not validation_blocked)
    assert len(turn.results) == 1
    result = turn.results[0]
    assert result.status == "gap", f"Expected status='gap', got {result.status!r}"
    assert len(turn.gaps) == 1
    assert turn.gaps[0].unmet == "no_fitting_skill"

    # Verify it was recorded in the gap store and categorized correctly.
    recorded = g.list_gaps()
    assert len(recorded) == 1
    assert recorded[0]["category"] == "no_fitting_skill"


# ============================================================================
# PART C — explain_score / propose_sweep (informational path, NOT actions)
# ============================================================================

def test_explain_score_not_in_action_types():
    """explain_score is NOT in ACTION_TYPES — it is an informational helper, not a mutation."""
    from typing import get_args
    from ai import models

    assert "explain_score" not in models.ACTION_TYPES
    assert "explain_score" not in get_args(models.ActionType)


def test_propose_sweep_not_in_action_types():
    """propose_sweep is NOT in ACTION_TYPES — it is an informational helper, not a mutation."""
    from typing import get_args
    from ai import models

    assert "propose_sweep" not in models.ACTION_TYPES
    assert "propose_sweep" not in get_args(models.ActionType)


def test_null_gateway_explain_score_degrade_clean():
    """NullActionGateway.explain with explain_score → deterministic non-empty string, no raise."""
    gw = NullActionGateway()
    scorecard = {"score": 72, "tier": "Partial", "panels": [{"id": "fig1a"}, {"id": "fig1b"}]}

    result = gw.explain("explain_score", {"scorecard": scorecard}, "explain the score")

    assert isinstance(result, str)
    assert len(result) > 0, "degrade-clean: should return a non-empty fallback string"
    # Grounded: should reference the score from the scorecard.
    assert "72" in result


def test_null_gateway_propose_sweep_degrade_clean():
    """NullActionGateway.explain with propose_sweep → deterministic non-empty string."""
    gw = NullActionGateway()
    sweep_space = {"fc_threshold": {"min": 0.5, "max": 3.0}, "pval_threshold": {"min": 0.01, "max": 0.1}}

    result = gw.explain("propose_sweep", {"sweep_space": sweep_space}, "what to sweep")

    assert isinstance(result, str)
    assert len(result) > 0
    # Grounded in the sweep space — at least one param name should appear.
    assert any(param in result for param in ("fc_threshold", "pval_threshold"))


def test_null_gateway_explain_unavailable_request():
    """An unrecognised request_type → 'unavailable' (never raises)."""
    gw = NullActionGateway()
    result = gw.explain("totally_unknown_type", {}, "")
    assert result == "unavailable"


def test_operator_gateway_explain_replays_recorded():
    """OperatorActionGateway replays a recorded explanation for the request_type + goal pair."""
    gw = OperatorActionGateway()
    gw.record_explanation("explain_score", "my goal", "Score is 80 because panels A and B match.")

    result = gw.explain("explain_score", {}, "my goal")
    assert result == "Score is 80 because panels A and B match."


def test_operator_gateway_explain_falls_back_for_unrecorded():
    """OperatorActionGateway falls back to deterministic for unrecorded request + goal."""
    gw = OperatorActionGateway()
    sc = {"score": 55, "tier": "Low", "panels": []}
    result = gw.explain("explain_score", {"scorecard": sc}, "some unrecorded goal")

    assert isinstance(result, str)
    assert "55" in result  # grounded in the scorecard


def test_explain_endpoint_with_null_gateway_returns_structured_response():
    """POST /ai/explain with NullActionGateway → {request, text, source=deterministic}."""
    from routers.ai import explain, ExplainRequest

    req = ExplainRequest(
        request="explain_score",
        goal="explain the score",
        scorecard={"score": 81, "tier": "High", "panels": [{"id": "fig3a"}]},
    )

    resp = explain(req)

    assert resp["request"] == "explain_score"
    assert isinstance(resp["text"], str) and len(resp["text"]) > 0
    assert resp["source"] == "deterministic"  # NullActionGateway is the default
    assert "81" in resp["text"]


def test_explain_endpoint_propose_sweep_returns_structured_response():
    """POST /ai/explain for propose_sweep → structured response with grounded text."""
    from routers.ai import explain, ExplainRequest

    req = ExplainRequest(
        request="propose_sweep",
        goal="which params to sweep",
        sweep_space={"fc_threshold": {"min": 0.5, "max": 3.0}},
    )

    resp = explain(req)

    assert resp["request"] == "propose_sweep"
    assert isinstance(resp["text"], str) and len(resp["text"]) > 0
    assert resp["source"] == "deterministic"
    assert "fc_threshold" in resp["text"]


def test_explain_does_not_record_to_gap_store():
    """Calling /ai/explain never records a CapabilityGap (informational, not a mutation)."""
    from routers.ai import explain, ExplainRequest

    req = ExplainRequest(
        request="explain_score",
        goal="explain",
        scorecard={"score": 60, "tier": "Partial", "panels": []},
    )

    explain(req)

    assert g.list_gaps() == [], "explain must not record any gaps (informational path)"


def test_explain_does_not_go_through_apply_plan():
    """Calling /ai/explain does not produce any ActionResult (not a mutation plan)."""
    # The informational path returns text, not an ActionPlan. Verify by checking
    # that the response has no 'actions' or 'results' field (those are mutation path).
    from routers.ai import explain, ExplainRequest

    req = ExplainRequest(request="propose_sweep", goal="sweep", sweep_space={"x": {}})
    resp = explain(req)

    assert "actions" not in resp
    assert "results" not in resp
    assert "staged_params" not in resp


def test_rank_sweep_space_orders_numeric_then_select_then_switch():
    """The grounded recommender ranks numeric > select > switch, breadth desc, caps at 3."""
    from ai.gateway import rank_sweep_space

    sweep_space = {
        "a_switch": {"type": "switch"},
        "b_select": {"type": "select", "options": ["x", "y", "z"]},
        "c_wide": {"type": "range", "min": 0.0, "max": 10.0, "step": 0.1},   # ~100 steps
        "d_narrow": {"type": "range", "min": 0.0, "max": 1.0, "step": 0.5},  # ~2 steps
    }
    ranked = rank_sweep_space(sweep_space)

    assert [s["param"] for s in ranked] == ["c_wide", "d_narrow", "b_select"], (
        "numeric (by breadth) first, then select, switch drops off the top-3 cap"
    )
    assert "100 steps" in ranked[0]["reason"]
    assert ranked[2]["reason"] == "3 options"


def test_rank_sweep_space_infers_kind_and_degrades_clean():
    """Missing ``type`` is inferred from min/max (numeric); junk input never raises."""
    from ai.gateway import rank_sweep_space

    assert rank_sweep_space(None) == []
    assert rank_sweep_space({}) == []
    # min/max with no declared type → inferred numeric (ranks above an empty knob).
    ranked = rank_sweep_space({"inferred": {"min": 0.01, "max": 0.1}, "empty": {}})
    assert ranked[0]["param"] == "inferred"
    assert ranked[1]["reason"] == "no declared range"
    # Uses a friendly label when provided.
    labelled = rank_sweep_space({"k": {"type": "switch", "label": "Clean traces"}})
    assert labelled[0]["label"] == "Clean traces"


def test_explain_endpoint_propose_sweep_returns_ranked_suggestions():
    """POST /ai/explain for propose_sweep carries the structured ranking the UI preselects from."""
    from routers.ai import explain, ExplainRequest

    req = ExplainRequest(
        request="propose_sweep",
        goal="which params to sweep",
        sweep_space={
            "resolution": {"type": "range", "min": 0.1, "max": 2.0, "step": 0.1},
            "cluster": {"type": "select", "options": ["none", "row", "column", "both"]},
        },
    )
    resp = explain(req)

    assert resp["suggestions"][0]["param"] == "resolution"  # numeric ranks first
    assert {s["param"] for s in resp["suggestions"]} == {"resolution", "cluster"}
    assert "resolution" in resp["text"] or "Cluster" in resp["text"]


def test_explain_endpoint_explain_score_has_empty_suggestions():
    """explain_score carries no sweep suggestions (the field is propose_sweep-only)."""
    from routers.ai import explain, ExplainRequest

    resp = explain(
        ExplainRequest(
            request="explain_score",
            scorecard={"score": 72, "tier": "reproduced", "selom_confidence": 88, "panel_count": 8},
        )
    )
    assert resp["suggestions"] == []
    assert "88" in resp["text"]  # the enriched text surfaces Selom confidence
    assert "8 panel(s)" in resp["text"]  # a scalar panel_count (not a panels[] list) still counts


class _StubGateway:
    """A non-Null gateway stand-in whose explain output we control (no live key needed)."""

    model_id = "test-live"

    def __init__(self, text_fn):
        self._text_fn = text_fn

    def propose(self, context, goal):  # pragma: no cover - explain path only
        from ai.models import ActionPlan

        return ActionPlan(goal=goal, actions=[])

    def explain(self, request_type, data, goal):
        return self._text_fn(request_type, data, goal)


def test_explain_source_deterministic_when_live_gateway_falls_back(monkeypatch):
    """A live gateway that degrades to the deterministic fallback is labelled source='deterministic'.

    The ✨ "AI" badge must never claim AI produced text the model didn't (it degrades to the
    byte-identical `_deterministic_explain` on timeout/error). Source is stamped by what was
    actually produced, not the gateway class.
    """
    from routers import ai as ai_router
    from ai.gateway import _deterministic_explain

    fallback_gw = _StubGateway(lambda rt, data, goal: _deterministic_explain(rt, data, goal))
    monkeypatch.setattr(ai_router, "get_action_gateway", lambda: fallback_gw)

    resp = ai_router.explain(
        ai_router.ExplainRequest(request="explain_score", scorecard={"score": 50, "tier": "Low", "panel_count": 3})
    )
    assert resp["source"] == "deterministic"  # fell back → NOT ✨ AI


def test_explain_source_ai_when_live_gateway_produces_text(monkeypatch):
    """A live gateway returning genuine model text is labelled source='ai'."""
    from routers import ai as ai_router

    live_gw = _StubGateway(lambda rt, data, goal: "A bespoke model explanation grounded in the data.")
    monkeypatch.setattr(ai_router, "get_action_gateway", lambda: live_gw)

    resp = ai_router.explain(
        ai_router.ExplainRequest(request="explain_score", scorecard={"score": 50, "tier": "Low", "panel_count": 3})
    )
    assert resp["source"] == "ai"


def test_knob_metrics_handles_every_paramfield_type():
    """Pin the cross-lane FE ParamField['type'] → ranker bucket mapping (an unguarded string contract).

    Mirror of lib/catalog/params.ts ParamField['type'] = range|number|text|switch|select. A new FE
    type lands in the breadth-0 'no declared range' bucket and ranks last; this asserts the known set
    so a mapping change (or a newly added type the ranker should understand) trips here, not silently.
    """
    from ai.gateway import _knob_metrics

    spec = {"min": 0, "max": 10, "step": 1, "options": ["a", "b"]}
    kinds = {t: _knob_metrics(spec, t)[2] for t in ("range", "number", "select", "switch", "text")}
    assert kinds == {"range": 3, "number": 3, "select": 2, "switch": 1, "text": 0}


# ============================================================================
# PART D — Registry/Literal completeness still passes with select_skill added
# ============================================================================

def test_registry_literal_completeness_with_select_skill():
    """ACTION_REGISTRY, ACTION_TYPES, and ActionType Literal are all identical.

    Mirrors the structure guard assertion — caught in the targeted run too.
    """
    from typing import get_args
    from ai import models, registry

    registry_keys = set(registry.ACTION_REGISTRY)
    types_tuple = set(models.ACTION_TYPES)
    literal_members = set(get_args(models.ActionType))

    assert registry_keys == types_tuple, (
        f"Registry {sorted(registry_keys)} ≠ ACTION_TYPES {sorted(types_tuple)}"
    )
    assert types_tuple == literal_members, (
        f"ACTION_TYPES {sorted(types_tuple)} ≠ ActionType Literal {sorted(literal_members)}"
    )
    # select_skill is present in all three.
    assert "select_skill" in registry_keys
    assert "select_skill" in types_tuple
    assert "select_skill" in literal_members


# ============================================================================
# PART E — Slice 2: data-aware /ai/propose wiring + gsea numeric-count fix
# ============================================================================

class _CaptureGateway:
    """A non-Null gateway that captures the ActionContext propose() built, returns an empty plan."""

    model_id = "test-capture"

    def __init__(self):
        self.ctx = None

    def propose(self, context, goal):
        self.ctx = context
        return ActionPlan(goal=goal, actions=[])

    def explain(self, request_type, data, goal):  # pragma: no cover - propose path only
        return ""


class _SelectSkillGateway:
    """Proposes a single select_skill action toward ``target`` — exercises the route gate via propose()."""

    model_id = "test-select"

    def __init__(self, target):
        self._target = target

    def propose(self, context, goal):
        return ActionPlan(
            goal=goal,
            actions=[Action(type="select_skill", target=self._target, payload={"skill_id": self._target})],
        )

    def explain(self, request_type, data, goal):  # pragma: no cover - propose path only
        return ""


def test_propose_populates_data_fit_from_request(monkeypatch):
    """propose() threads data_columns/data_kind/data_n_numeric_cols into ctx.data_fit (R2).

    The verdict is NOT in the request — only the description; propose() builds the data_fit dict
    the route gate then scores via engine.compat.fit.
    """
    from engine.models import DE_RESULTS
    from routers import ai as ai_router

    cap = _CaptureGateway()
    monkeypatch.setattr(ai_router, "get_action_gateway", lambda: cap)

    ai_router.propose(ai_router.ProposeRequest(
        stage="route", goal="make a volcano",
        data_columns=["gene", "logFC", "padj"], data_kind=DE_RESULTS, data_n_numeric_cols=2,
    ))
    assert cap.ctx is not None
    assert cap.ctx.data_columns == ["gene", "logFC", "padj"]
    assert cap.ctx.data_fit is not None
    assert cap.ctx.data_fit["kind"] == DE_RESULTS
    assert cap.ctx.data_fit["n_numeric_cols"] == 2


def test_propose_without_data_context_leaves_data_fit_none(monkeypatch):
    """No data context → ctx.data_fit stays None (zero-regression; the analyze composer path)."""
    from routers import ai as ai_router

    cap = _CaptureGateway()
    monkeypatch.setattr(ai_router, "get_action_gateway", lambda: cap)
    ai_router.propose(ai_router.ProposeRequest(stage="analyze", goal="tidy the figure"))
    assert cap.ctx.data_fit is None
    assert cap.ctx.data_columns is None


def test_propose_data_aware_route_gate_fires_on_mismatch(monkeypatch):
    """End-to-end through propose(): a select_skill toward a table skill on a single-cell matrix →
    no_fitting_skill gap (R3 — the route gate is reachable once data_fit is populated)."""
    from engine.models import SC_COUNTS
    from routers import ai as ai_router

    monkeypatch.setattr(ai_router, "get_action_gateway", lambda: _SelectSkillGateway("volcano"))
    turn = ai_router.propose(ai_router.ProposeRequest(
        stage="route", goal="run a volcano",
        data_columns=[], data_kind=SC_COUNTS, data_n_numeric_cols=0,
    ))
    assert turn["results"][0]["status"] == "gap"
    assert any(gp["unmet"] == "no_fitting_skill" for gp in turn["gaps"])


def test_propose_data_aware_route_gate_passes_on_fit(monkeypatch):
    """A select_skill toward volcano on a DE table with the right columns → staged, no gap (R3)."""
    from engine.models import DE_RESULTS
    from routers import ai as ai_router

    monkeypatch.setattr(ai_router, "get_action_gateway", lambda: _SelectSkillGateway("volcano"))
    turn = ai_router.propose(ai_router.ProposeRequest(
        stage="route", goal="run a volcano",
        data_columns=["gene", "logFC", "padj"], data_kind=DE_RESULTS, data_n_numeric_cols=2,
    ))
    assert turn["results"][0]["status"] == "staged"
    assert turn["gaps"] == []


def test_select_skill_gsea_not_false_gated_with_numeric_count():
    """gsea needs a gene col + ≥1 numeric score. With the real numeric count provided, a ranked
    gene list validates ok (R4 — the old n_numeric_cols=0 hardcode would have falsely gated it)."""
    from engine.models import DE_RESULTS

    data_fit = {"kind": DE_RESULTS, "n_numeric_cols": 2, "score": 85, "qc_ok": True}
    ctx = ActionContext(stage="route", data_fit=data_fit, data_columns=["gene", "score"])
    action = Action(type="select_skill", target="gsea", payload={"skill_id": "gsea"})
    outcome = validate_action(action, ctx)
    assert outcome.ok, f"gsea should fit a gene+score table; errors: {outcome.errors}"


def test_select_skill_gsea_satisfies_numeric_when_count_unknown():
    """When the numeric count is unknown (None), the gsea numeric sub-check is satisfied from the
    column list rather than falsely tripped (R4 — don't gate on what we didn't measure)."""
    from engine.models import DE_RESULTS

    data_fit = {"kind": DE_RESULTS, "n_numeric_cols": None, "score": 85, "qc_ok": True}
    ctx = ActionContext(stage="route", data_fit=data_fit, data_columns=["gene", "score"])
    action = Action(type="select_skill", target="gsea", payload={"skill_id": "gsea"})
    outcome = validate_action(action, ctx)
    assert outcome.ok, f"unknown numeric count must not false-gate gsea; errors: {outcome.errors}"
