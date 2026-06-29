"""S3 proof — Ingest-stage AI helpers: set_profile / set_design / map_columns / apply_cleaning_step.

All tests run in the fast gate (``pytest -m "not slow"``).  No file I/O or live skill
deps are needed: every test calls ``validate_action`` / ``apply_plan`` directly with a
constructed ``ActionContext``.  The ``_stub_engine`` fixture is included for safety.

Per-action findings (engine-surface investigation 2026-06-29):
  set_profile      — HOOK EXISTS: profile_data(bundle, override=code) in engine/cleaning.py.
                     Effect delta: {_profile_override: code}.  S5 wires it to the run path.
  set_design       — PARTIAL HOOK: Design model + _design_path reserved key exist in engine.
                     Effect delta: design fields staged as params.  S5 wires to run path.
  map_columns      — CAPABILITY GAP (missing_column_op): databundle._LOGFC/_PVAL are
                     auto-detection synonym sets — there is no column-override/remap hook.
  apply_cleaning_step — CAPABILITY GAP (validation_blocked): plan_cleaning has no step-
                     enable/skip parameter; CleaningStep carries no 'enabled' field.
"""

from __future__ import annotations

import pytest

from ai import gaps as g
from ai.execute import apply_plan, validate_action
from ai.models import Action, ActionContext, ActionPlan


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _stub_engine(monkeypatch):
    """Keep heavy skill deps from loading if handlers are changed later."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


@pytest.fixture(autouse=True)
def _clear_gaps():
    """Prevent gap-store bleed between tests."""
    g.reset()
    yield
    g.reset()


# ---------------------------------------------------------------------------
# Registry / Literal completeness — S3 additions are present in all three places
# ---------------------------------------------------------------------------

def test_registry_includes_s3_actions():
    """ACTION_REGISTRY, ACTION_TYPES tuple, and ActionType Literal all carry S3 types.

    Three-way equality must still hold after the S3 additions (the structure guard
    asserts this at CI time; this test also catches it in the targeted run).
    """
    from typing import get_args
    from ai import models, registry

    s3_actions = {"set_profile", "set_design", "map_columns", "apply_cleaning_step"}

    assert s3_actions.issubset(set(registry.ACTION_REGISTRY)), (
        f"S3 action(s) missing from ACTION_REGISTRY: "
        f"{s3_actions - set(registry.ACTION_REGISTRY)}"
    )
    assert s3_actions.issubset(set(models.ACTION_TYPES)), (
        f"S3 action(s) missing from ACTION_TYPES: "
        f"{s3_actions - set(models.ACTION_TYPES)}"
    )
    assert s3_actions.issubset(set(get_args(models.ActionType))), (
        f"S3 action(s) missing from ActionType Literal: "
        f"{s3_actions - set(get_args(models.ActionType))}"
    )
    # Three-way equality still holds (mirrors the structure guard assertion).
    assert set(registry.ACTION_REGISTRY) == set(models.ACTION_TYPES)
    assert set(models.ACTION_TYPES) == set(get_args(models.ActionType))


# ---------------------------------------------------------------------------
# set_profile — maps to existing engine hook profile_data(override=...)
# ---------------------------------------------------------------------------

def test_set_profile_valid_kind_code_validates_ok():
    """A recognised Kind code (de_results) is accepted and effect carries _profile_override."""
    ctx = ActionContext(stage="ingest")
    action = Action(type="set_profile", target="", payload={"value": "de_results"})

    outcome = validate_action(action, ctx)
    assert outcome.ok, f"Expected ok=True for 'de_results', got errors: {outcome.errors}"

    from ai import registry as reg
    effect = reg.get("set_profile").apply(action, ctx)
    assert effect == {"params": {"_profile_override": "de_results"}}


def test_set_profile_erg_code_validates_ok():
    """'erg' is accepted — it is a valid profile code even though it is not a Kind constant."""
    ctx = ActionContext(stage="ingest")
    action = Action(type="set_profile", target="", payload={"value": "erg"})

    outcome = validate_action(action, ctx)
    assert outcome.ok, f"Expected ok=True for 'erg', got errors: {outcome.errors}"


def test_set_profile_all_kind_codes_validate_ok():
    """Every entry in engine.models.ALL_KINDS is a valid set_profile value."""
    from engine.models import ALL_KINDS

    ctx = ActionContext(stage="ingest")
    for code in ALL_KINDS:
        action = Action(type="set_profile", target="", payload={"value": code})
        outcome = validate_action(action, ctx)
        assert outcome.ok, f"Kind code {code!r} should validate ok; errors: {outcome.errors}"


def test_set_profile_unknown_code_emits_gap():
    """An unrecognised code → rejected with gap(validation_blocked)."""
    ctx = ActionContext(stage="ingest")
    action = Action(type="set_profile", target="", payload={"value": "magic_modality_xyz"})

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "validation_blocked"
    assert outcome.gap.stage == "ingest"


def test_set_profile_candidate_from_capability_surface():
    """A code present in ctx.capability_surface['candidates'] is accepted.

    Callers pass the live DataProfile's candidates dict via capability_surface so
    the validator can check "is this one of the profile's actual candidates" without
    needing the bundle in the ActionContext.
    """
    ctx = ActionContext(
        stage="ingest",
        capability_surface={"candidates": [{"code": "erg", "label": "ERG / electrophysiology"}]},
    )
    action = Action(type="set_profile", target="", payload={"value": "erg"})

    outcome = validate_action(action, ctx)
    assert outcome.ok, f"A candidate code from capability_surface should be accepted: {outcome.errors}"


def test_set_profile_staged_in_apply_plan():
    """set_profile flows through apply_plan → status=staged + staged_params has _profile_override."""
    ctx = ActionContext(stage="ingest")
    plan = ActionPlan(
        goal="set data type to DE results",
        actions=[Action(type="set_profile", target="", payload={"value": "de_results"})],
    )

    turn = apply_plan(plan, ctx)

    assert len(turn.results) == 1
    result = turn.results[0]
    assert result.status == "staged", f"Expected staged, got {result.status!r}"
    assert turn.staged_params == {"_profile_override": "de_results"}


def test_set_profile_missing_value_key():
    """payload without 'value' is rejected cleanly (no gap — malformed payload)."""
    ctx = ActionContext(stage="ingest")
    action = Action(type="set_profile", target="", payload={})

    outcome = validate_action(action, ctx)
    assert not outcome.ok
    assert "value" in outcome.errors[0]


# ---------------------------------------------------------------------------
# set_design — partial engine hook (Design model + _design_path mechanism)
# ---------------------------------------------------------------------------

def test_set_design_valid_columns_validates_ok():
    """condition and batch columns exist in data_columns → validates ok."""
    ctx = ActionContext(
        stage="ingest",
        data_columns=["sample", "condition", "batch", "gene1", "gene2"],
    )
    action = Action(
        type="set_design",
        target="",
        payload={"condition": "condition", "control": "WT", "treatment": "KO", "batch": "batch"},
    )

    outcome = validate_action(action, ctx)
    assert outcome.ok, f"Expected ok=True, got errors: {outcome.errors}"


def test_set_design_missing_condition_column():
    """condition column absent from data_columns → rejected with gap(validation_blocked)."""
    ctx = ActionContext(
        stage="ingest",
        data_columns=["sample", "gene1", "gene2"],
    )
    action = Action(
        type="set_design",
        target="",
        payload={"condition": "group", "control": "WT", "treatment": "KO"},
    )

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "validation_blocked"
    assert "group" in outcome.errors[0]


def test_set_design_missing_batch_column():
    """batch column absent from data_columns → rejected with gap(validation_blocked)."""
    ctx = ActionContext(
        stage="ingest",
        data_columns=["sample", "condition"],
    )
    action = Action(
        type="set_design",
        target="",
        payload={"condition": "condition", "batch": "nonexistent_batch"},
    )

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "validation_blocked"
    assert "nonexistent_batch" in outcome.errors[0]


def test_set_design_no_data_columns_skips_column_check():
    """When data_columns is None the column check is skipped — no false-negative block."""
    ctx = ActionContext(stage="ingest")  # data_columns=None by default
    action = Action(
        type="set_design",
        target="",
        payload={"condition": "any_col", "control": "WT", "treatment": "KO"},
    )

    outcome = validate_action(action, ctx)
    assert outcome.ok, (
        f"Without data_columns the column check must be skipped; errors: {outcome.errors}"
    )


def test_set_design_effect_carries_design_fields():
    """apply stages condition/control/treatment/batch as params."""
    from ai import registry as reg

    ctx = ActionContext(stage="ingest", data_columns=["condition", "batch"])
    action = Action(
        type="set_design",
        target="",
        payload={"condition": "condition", "control": "WT", "treatment": "KO", "batch": "batch"},
    )

    effect = reg.get("set_design").apply(action, ctx)
    params = effect["params"]
    assert params["condition"] == "condition"
    assert params["control"] == "WT"
    assert params["treatment"] == "KO"
    assert params["batch"] == "batch"


def test_set_design_optional_batch_omitted():
    """batch is optional — apply omits it if not in the payload."""
    from ai import registry as reg

    ctx = ActionContext(stage="ingest", data_columns=["condition"])
    action = Action(
        type="set_design",
        target="",
        payload={"condition": "condition", "control": "WT", "treatment": "KO"},
    )

    effect = reg.get("set_design").apply(action, ctx)
    assert "batch" not in effect["params"]


def test_set_design_missing_condition_payload():
    """payload without 'condition' is rejected cleanly."""
    ctx = ActionContext(stage="ingest", data_columns=["x"])
    action = Action(type="set_design", target="", payload={"batch": "x"})

    outcome = validate_action(action, ctx)
    assert not outcome.ok
    assert "condition" in outcome.errors[0]


def test_set_design_staged_in_apply_plan():
    """set_design flows through apply_plan → status=staged + staged_params has design fields."""
    ctx = ActionContext(stage="ingest", data_columns=["condition"])
    plan = ActionPlan(
        goal="set condition column to 'condition'",
        actions=[Action(
            type="set_design",
            target="",
            payload={"condition": "condition", "control": "WT", "treatment": "KO"},
        )],
    )

    turn = apply_plan(plan, ctx)

    assert len(turn.results) == 1
    assert turn.results[0].status == "staged"
    assert turn.staged_params["condition"] == "condition"
    assert turn.staged_params["control"] == "WT"


# ---------------------------------------------------------------------------
# map_columns — HONEST CAPABILITY GAP (unmet=missing_column_op)
#
# Engine finding: databundle._LOGFC / _PVAL are auto-detection synonym SETS only.
# There is no API to say "treat column X as column Y".  The gap surfaces the backlog.
# ---------------------------------------------------------------------------

def test_map_columns_emits_capability_gap():
    """map_columns is registered but always produces a CapabilityGap(missing_column_op).

    The gap records the intended mapping so the frequency-ranked backlog captures demand
    for an explicit column-override hook on the ingest surface.
    """
    ctx = ActionContext(stage="ingest")
    action = Action(
        type="map_columns",
        target="",
        payload={"logFC": "log2FoldChange", "pval": "padj"},
    )

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "missing_column_op"
    assert outcome.gap.stage == "ingest"
    assert outcome.gap.intent == "map_columns"


def test_map_columns_status_is_gap_in_apply_plan():
    """apply_plan sets status='gap' (backlog candidate) for missing_column_op gaps."""
    ctx = ActionContext(stage="ingest")
    plan = ActionPlan(
        goal="rename logFC column",
        actions=[Action(type="map_columns", target="", payload={"logFC": "log2FoldChange"})],
    )

    turn = apply_plan(plan, ctx)

    assert len(turn.results) == 1
    assert turn.results[0].status == "gap"
    assert len(turn.gaps) == 1
    assert turn.gaps[0].unmet == "missing_column_op"
    # Gap is recorded in the gap store.
    recorded = g.list_gaps()
    assert len(recorded) == 1
    assert recorded[0]["gap"].unmet == "missing_column_op"


def test_map_columns_gap_deduped_on_recurrence():
    """Recurring map_columns gaps increment count, not entries."""
    ctx = ActionContext(stage="ingest")
    plan = ActionPlan(
        goal="rename logFC",
        actions=[Action(type="map_columns", target="", payload={"logFC": "log2FoldChange"})],
    )

    apply_plan(plan, ctx)
    apply_plan(plan, ctx)

    recorded = g.list_gaps()
    assert len(recorded) == 1
    assert recorded[0]["count"] == 2


# ---------------------------------------------------------------------------
# apply_cleaning_step — HONEST CAPABILITY GAP (unmet=validation_blocked)
#
# Engine finding: plan_cleaning(bundle, *, profile=None) has no skip_steps/include_steps
# param.  CleaningStep has no 'enabled' field.  Intent coherent, but engine cannot
# effect or validate it.
# ---------------------------------------------------------------------------

def test_apply_cleaning_step_emits_capability_gap():
    """apply_cleaning_step is registered but always produces a CapabilityGap(validation_blocked).

    The intent (skip step filter_genes) is coherent; the engine cannot effect it
    (plan_cleaning has no step-toggle hook), so the gap is validation_blocked.
    """
    ctx = ActionContext(stage="ingest")
    action = Action(
        type="apply_cleaning_step",
        target="",
        payload={"step_id": "filter_genes", "enabled": False},
    )

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "validation_blocked"
    assert outcome.gap.stage == "ingest"
    assert outcome.gap.intent == "apply_cleaning_step"


def test_apply_cleaning_step_status_is_rejected_in_apply_plan():
    """apply_plan sets status='rejected' for validation_blocked gaps (coherent but blocked)."""
    ctx = ActionContext(stage="ingest")
    plan = ActionPlan(
        goal="skip the gene-filter step",
        actions=[Action(
            type="apply_cleaning_step",
            target="",
            payload={"step_id": "filter_genes", "enabled": False},
        )],
    )

    turn = apply_plan(plan, ctx)

    assert len(turn.results) == 1
    assert turn.results[0].status == "rejected"
    assert len(turn.gaps) == 1
    assert turn.gaps[0].unmet == "validation_blocked"


def test_apply_cleaning_step_gap_recorded_and_deduped():
    """Recurring apply_cleaning_step gaps dedup in the gap store."""
    ctx = ActionContext(stage="ingest")
    plan = ActionPlan(
        goal="skip normalize step",
        actions=[Action(
            type="apply_cleaning_step",
            target="",
            payload={"step_id": "normalize"},
        )],
    )

    apply_plan(plan, ctx)
    apply_plan(plan, ctx)

    recorded = g.list_gaps()
    assert len(recorded) == 1
    assert recorded[0]["gap"].unmet == "validation_blocked"
    assert recorded[0]["count"] == 2


# ---------------------------------------------------------------------------
# ActionContext.data_columns is backward-compatible
# ---------------------------------------------------------------------------

def test_action_context_data_columns_defaults_none():
    """ActionContext.data_columns=None by default — existing callers need no changes."""
    ctx = ActionContext(stage="analyze", skill_id="volcano")
    assert ctx.data_columns is None


def test_action_context_accepts_data_columns():
    """ActionContext accepts a list of column names for ingest-stage validators."""
    ctx = ActionContext(stage="ingest", data_columns=["gene", "logFC", "padj"])
    assert ctx.data_columns == ["gene", "logFC", "padj"]
