"""S3 proof — Ingest-stage AI helpers: set_profile / set_design / map_columns / apply_cleaning_step.

All tests run in the fast gate (``pytest -m "not slow"``).  No file I/O or live skill
deps are needed: every test calls ``validate_action`` / ``apply_plan`` directly with a
constructed ``ActionContext``.  The ``_stub_engine`` fixture is included for safety.

Per-action state (map_columns / apply_cleaning_step flipped gap→wired 2026-06-30, P1 ingest hooks):
  set_profile      — HOOK EXISTS: profile_data(bundle, override=code) in engine/cleaning.py.
                     Effect delta: {_profile_override: code}.
  set_design       — PARTIAL HOOK: Design model + _design_path reserved key exist in engine.
                     Effect delta: design fields staged as params.
  map_columns      — WIRED: engine.columns column-override; stages {_column_override: {role: column}}
                     (roles logFC/pval/gene); honoured at D1/D2/the runner + recorded → reproducible.
  apply_cleaning_step — WIRED (param-backed): a step in engine.cleaning.STEP_PARAM (normalize→
                     normalize) compiles to a set_param effect; a non-backed step → honest gap.
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
# map_columns — WIRED (P1 ingest hook): engine.columns column-override.
#
# A {role: column} map (roles logFC/pval/gene, disjoint from set_design) that wins over
# synonym auto-detection; staged as {_column_override: map} and recorded → reproducible.
# ---------------------------------------------------------------------------

def test_map_columns_valid_mapping_validates_ok():
    """A {role: column} map whose columns exist in the data validates ok."""
    ctx = ActionContext(
        stage="ingest",
        data_columns=["GeneName", "FoldChange_custom", "padj"],
    )
    action = Action(
        type="map_columns", target="",
        payload={"logFC": "FoldChange_custom", "pval": "padj", "gene": "GeneName"},
    )

    outcome = validate_action(action, ctx)
    assert outcome.ok, f"Expected ok=True, got errors: {outcome.errors}"


def test_map_columns_effect_stages_column_override():
    """apply stages {_column_override: {role: column}} — the reserved param the run path reads."""
    from ai import registry as reg

    ctx = ActionContext(stage="ingest", data_columns=["FC_custom", "padj"])
    action = Action(type="map_columns", target="", payload={"logFC": "FC_custom", "pval": "padj"})

    effect = reg.get("map_columns").apply(action, ctx)
    assert effect == {"params": {"_column_override": {"logFC": "FC_custom", "pval": "padj"}}}


def test_map_columns_staged_in_apply_plan():
    """map_columns flows through apply_plan → status=staged + staged_params has _column_override."""
    ctx = ActionContext(stage="ingest", data_columns=["FC_custom", "padj"])
    plan = ActionPlan(
        goal="treat FC_custom as logFC",
        actions=[Action(type="map_columns", target="",
                        payload={"logFC": "FC_custom", "pval": "padj"})],
    )

    turn = apply_plan(plan, ctx)

    assert len(turn.results) == 1
    assert turn.results[0].status == "staged", f"got {turn.results[0].status!r}"
    assert turn.staged_params == {"_column_override": {"logFC": "FC_custom", "pval": "padj"}}
    assert not turn.gaps


def test_map_columns_missing_column_rejected_with_gap():
    """A mapped column absent from data_columns → rejected with gap(validation_blocked).

    Override-only: it never fabricates a column. Mirrors set_design's missing-column behaviour.
    """
    ctx = ActionContext(stage="ingest", data_columns=["gene", "padj"])
    action = Action(type="map_columns", target="", payload={"logFC": "nonexistent_fc"})

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "validation_blocked"
    assert "nonexistent_fc" in outcome.errors[0]


def test_map_columns_unknown_role_rejected_no_gap():
    """A non-overridable role (e.g. condition/batch — set_design owns those) → clean reject, no gap."""
    ctx = ActionContext(stage="ingest", data_columns=["batch", "padj"])
    action = Action(type="map_columns", target="", payload={"batch": "batch"})

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is None
    assert "batch" in outcome.errors[0]


def test_map_columns_no_data_columns_skips_check():
    """When data_columns is None the existence check is skipped — no false-negative block."""
    ctx = ActionContext(stage="ingest")  # data_columns=None
    action = Action(type="map_columns", target="", payload={"logFC": "any_fc", "pval": "any_p"})

    outcome = validate_action(action, ctx)
    assert outcome.ok, f"Without data_columns the existence check must be skipped: {outcome.errors}"


def test_map_columns_empty_payload_rejected():
    """An empty payload is rejected cleanly (no map to apply)."""
    ctx = ActionContext(stage="ingest", data_columns=["x"])
    outcome = validate_action(Action(type="map_columns", target="", payload={}), ctx)
    assert not outcome.ok
    assert outcome.gap is None


# ---------------------------------------------------------------------------
# apply_cleaning_step — WIRED (P1 ingest hook, param-backed).
#
# A step in engine.cleaning.STEP_PARAM (normalize → the 'normalize' skill param) compiles to a
# set_param effect via validate_param_ranges; a non-param-backed step → honest gap(validation_blocked).
# ---------------------------------------------------------------------------

def test_apply_cleaning_step_normalize_validates_ok():
    """The normalize step on a skill that declares a 'normalize' param validates ok."""
    ctx = ActionContext(stage="ingest", skill_id="deg")
    action = Action(type="apply_cleaning_step", target="",
                    payload={"step_id": "normalize", "enabled": False})

    outcome = validate_action(action, ctx)
    assert outcome.ok, f"Expected ok=True, got errors: {outcome.errors}"


def test_apply_cleaning_step_effect_stages_controlling_param():
    """apply stages the controlling skill param (disable → normalize=False) — a real recompute param."""
    from ai import registry as reg

    ctx = ActionContext(stage="ingest", skill_id="deg")
    action = Action(type="apply_cleaning_step", target="",
                    payload={"step_id": "normalize", "enabled": False})

    effect = reg.get("apply_cleaning_step").apply(action, ctx)
    assert effect == {"params": {"normalize": False}}


def test_apply_cleaning_step_staged_in_apply_plan():
    """apply_cleaning_step flows through apply_plan → status=staged + staged_params has the param."""
    ctx = ActionContext(stage="ingest", skill_id="umap_scrna")
    plan = ActionPlan(
        goal="skip normalization (data is already normalized)",
        actions=[Action(type="apply_cleaning_step", target="",
                        payload={"step_id": "normalize", "enabled": False})],
    )

    turn = apply_plan(plan, ctx)

    assert len(turn.results) == 1
    assert turn.results[0].status == "staged", f"got {turn.results[0].status!r}"
    assert turn.staged_params == {"normalize": False}
    assert not turn.gaps


def test_apply_cleaning_step_non_param_backed_step_gap():
    """A hard-coded step with no backing param (filter_genes) → honest gap(validation_blocked)."""
    ctx = ActionContext(stage="ingest", skill_id="deg")
    action = Action(type="apply_cleaning_step", target="",
                    payload={"step_id": "filter_genes", "enabled": False})

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "validation_blocked"
    assert "filter_genes" in outcome.errors[0]


def test_apply_cleaning_step_no_active_skill_gap():
    """No active skill (skill_id=None) → gap(validation_blocked): the step's param needs a skill."""
    ctx = ActionContext(stage="ingest")  # skill_id=None
    action = Action(type="apply_cleaning_step", target="", payload={"step_id": "normalize"})

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "validation_blocked"


def test_apply_cleaning_step_skill_without_param_gap():
    """A skill that doesn't declare the step's param (volcano has no 'normalize') → honest gap."""
    ctx = ActionContext(stage="analyze", skill_id="volcano")
    action = Action(type="apply_cleaning_step", target="",
                    payload={"step_id": "normalize", "enabled": False})

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "validation_blocked"
    assert "normalize" in outcome.errors[0]


def test_apply_cleaning_step_missing_step_id_rejected():
    """payload without 'step_id' is rejected cleanly (no gap — malformed)."""
    ctx = ActionContext(stage="ingest", skill_id="deg")
    outcome = validate_action(Action(type="apply_cleaning_step", target="", payload={}), ctx)
    assert not outcome.ok
    assert outcome.gap is None


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
