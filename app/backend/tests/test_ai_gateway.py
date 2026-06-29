"""S1 proof — Action Gateway spine (pure, no live LLM).

Tests use real skills (volcano) and the stub engine (SELOM_SKILLS_ENGINE=stub) so
they run in the fast gate (``pytest -m "not slow"``) with no heavy deps.  The stub
produces a deterministic figure from params alone, which is ideal for the "AI
compiles away" reproduction invariant.

Skill choice rationale:
  volcano — fast stub + real numeric param_spec (fc_threshold float 0–5) + in STUB_NATIVE
  (skills/contract.py STUB_NATIVE set).  A 6-row CSV is created in tmp_path so
  provenance.build can hash a real file, even though the stub ignores data_path.

All gap-store tests call ``gaps.reset()`` in a fixture to prevent cross-test bleed.
"""

from __future__ import annotations

import pytest

from ai import gaps as g
from ai.execute import apply_plan, commit_recompute, validate_action
from ai.gateway import NullActionGateway, OperatorActionGateway
from ai.loop import run_helper_turn
from ai.models import (
    Action,
    ActionContext,
    ActionPlan,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _stub_engine(monkeypatch):
    """Force the volcano stub so the test runs fast with no pandas I/O."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


@pytest.fixture(autouse=True)
def _clear_gaps():
    """Prevent gap-store bleed between tests."""
    g.reset()
    yield
    g.reset()


@pytest.fixture()
def tiny_csv(tmp_path):
    """Minimal 6-row DE results CSV — gives provenance.build a real file to hash.

    The volcano stub ignores data_path, so content is irrelevant for figure
    correctness; any non-empty file satisfies sha256_file.
    """
    csv = tmp_path / "de.csv"
    csv.write_text(
        "gene,logFC,padj\n"
        "GeneA,2.5,0.001\n"
        "GeneB,-1.8,0.01\n"
        "GeneC,0.5,0.5\n"
        "GeneD,3.0,0.0001\n"
        "GeneE,-0.3,0.8\n"
        "GeneF,1.2,0.05\n",
        encoding="utf-8",
    )
    return csv


# ---------------------------------------------------------------------------
# Registry + Literal completeness
# ---------------------------------------------------------------------------

def test_registry_matches_literal():
    """ACTION_REGISTRY keys == ACTION_TYPES tuple == ActionType Literal members.

    Overlaps with the structure guard but lives here too so a standalone test run
    also catches the mismatch.
    """
    from typing import get_args
    from ai import models, registry

    assert set(registry.ACTION_REGISTRY) == set(models.ACTION_TYPES)
    assert set(models.ACTION_TYPES) == set(get_args(models.ActionType))


# ---------------------------------------------------------------------------
# set_param validates via the core (Requirement 3)
# ---------------------------------------------------------------------------

def test_set_param_validates_via_core():
    """An AI-proposed set_param goes through the exact same validate_param_ranges
    that a human HTTP request goes through — no parallel path.

    volcano.fc_threshold: float, min=0.0, max=5.0 (from skills/volcano/skill.json).
    """
    ctx = ActionContext(skill_id="volcano", stage="analyze")

    # Valid value inside range → ok
    action_ok = Action(type="set_param", target="fc_threshold", payload={"value": 2.0})
    outcome = validate_action(action_ok, ctx)
    assert outcome.ok, f"Expected ok=True, got errors: {outcome.errors}"

    # Out-of-range value → refused, gap=validation_blocked
    action_bad = Action(type="set_param", target="fc_threshold", payload={"value": 99.0})
    outcome_bad = validate_action(action_bad, ctx)
    assert not outcome_bad.ok
    assert outcome_bad.errors
    assert outcome_bad.gap is not None
    assert outcome_bad.gap.unmet == "validation_blocked"
    assert outcome_bad.gap.skill_id == "volcano"


def test_unknown_param_emits_gap():
    """A set_param targeting a non-existent param → param_not_in_spec gap, recorded."""
    ctx = ActionContext(skill_id="volcano", stage="analyze")
    action = Action(type="set_param", target="not_a_real_param", payload={"value": 1})

    outcome = validate_action(action, ctx)

    assert not outcome.ok
    assert outcome.gap is not None
    assert outcome.gap.unmet == "param_not_in_spec"

    # apply_plan (not validate_action) is the caller that records; simulate that path.
    g.record(outcome.gap)
    recorded = g.list_gaps()
    assert len(recorded) == 1
    assert recorded[0]["gap"].unmet == "param_not_in_spec"


# ---------------------------------------------------------------------------
# Cosmetic vs recompute split + figure threading
# ---------------------------------------------------------------------------

def test_cosmetic_applies_recompute_stages():
    """restyle_figure → status=applied + mutated figure_spec.
    set_param → status=staged + staged_params populated.
    """
    figure_spec = {"layout": {"title": {"text": "x"}}}
    ctx = ActionContext(skill_id="volcano", stage="analyze", figure_spec=figure_spec)

    plan = ActionPlan(
        goal="restyle and set param",
        actions=[
            Action(
                type="restyle_figure",
                target="layout.title.text",
                payload={"path": "/layout/title/text", "value": "New Title"},
            ),
            Action(
                type="set_param",
                target="fc_threshold",
                payload={"value": 1.5},
            ),
        ],
    )

    turn = apply_plan(plan, ctx)

    # Cosmetic applied immediately
    cosmetic_result = next(r for r in turn.results if r.type == "restyle_figure")
    assert cosmetic_result.status == "applied"
    # figure_spec updated in the turn
    assert turn.figure_spec is not None
    assert turn.figure_spec["layout"]["title"]["text"] == "New Title"

    # Recompute staged
    recompute_result = next(r for r in turn.results if r.type == "set_param")
    assert recompute_result.status == "staged"
    assert turn.staged_params == {"fc_threshold": 1.5}


# ---------------------------------------------------------------------------
# The key invariant: AI compiles away
# ---------------------------------------------------------------------------

def test_ai_compiles_away(tiny_csv):
    """THE load-bearing invariant: re-running from recorded provenance params with
    zero AI in the loop produces the byte-identical figure.

    Sequence:
      1. OperatorActionGateway proposes set_param(fc_threshold=1.5).
      2. run_helper_turn validates + stages it.
      3. commit_recompute merges base+staged, runs the skill (stub), builds provenance.
      4. Direct run_skill_with_table call with provenance["params"] — NO gateway.
      5. Assert figure_A == figure_B.

    AI chose fc_threshold=1.5; the param — not the AI — is what executes.  The
    reproducibility score never depends on the gateway being available.
    """
    from skills.contract import run_skill_with_table

    skill_id = "volcano"
    base_params: dict = {}

    # Operator-recorded plan (CI-safe, no LLM).
    plan = ActionPlan(
        goal="increase fc threshold",
        actions=[Action(type="set_param", target="fc_threshold", payload={"value": 1.5})],
    )
    gw = OperatorActionGateway()
    gw.record("increase fc threshold", plan)

    ctx = ActionContext(skill_id=skill_id, params=base_params)
    turn = run_helper_turn(ctx, "increase fc threshold", gw)

    assert turn.staged_params == {"fc_threshold": 1.5}, (
        f"Expected staged_params to carry fc_threshold=1.5, got {turn.staged_params}"
    )

    # Step 3 — deterministic execution with the staged params.
    result = commit_recompute(
        skill_id,
        str(tiny_csv),
        base_params,
        turn.staged_params,
        goal="increase fc threshold",
        runner=run_skill_with_table,
        provenance_actions=turn.provenance_actions,
    )
    figure_A = result["figure"]

    # Step 4 — reproduce from recorded params, zero AI in the loop.
    figure_B, _ = run_skill_with_table(skill_id, str(tiny_csv), result["params"])

    assert figure_A == figure_B, (
        "AI compiles away invariant FAILED: re-running from provenance params did not "
        "reproduce the figure.  AI may be on the execution critical path."
    )

    # Provenance records actor=ai with prompt.
    assert result["provenance"].get("actions") is not None
    assert result["provenance"]["actions"][0]["actor"] == "ai"
    assert result["provenance"]["actions"][0]["prompt"] == "increase fc threshold"


# ---------------------------------------------------------------------------
# Zero-regression fallback
# ---------------------------------------------------------------------------

def test_null_gateway_zero_regression():
    """NullActionGateway → empty plan, no results, no staged params, no gaps.

    The run_helper_turn return with the null gateway must be indistinguishable
    from the pre-spec behaviour: nothing is proposed, nothing is staged, and no
    gaps are recorded (because no capabilities were attempted).
    """
    ctx = ActionContext(skill_id="volcano", stage="analyze")
    turn = run_helper_turn(ctx, "do something", NullActionGateway())

    assert turn.plan.actions == []
    assert turn.results == []
    assert turn.staged_params == {}
    assert turn.gaps == []
    assert g.list_gaps() == []


# ---------------------------------------------------------------------------
# Gap dedup + recurrence
# ---------------------------------------------------------------------------

def test_gap_dedup_recurrence():
    """The same coherent gap recorded twice increments count, not entries."""
    ctx = ActionContext(skill_id="volcano", stage="analyze")
    action = Action(type="set_param", target="not_a_real_param", payload={"value": 1})

    # Record via apply_plan (the normal production path).
    plan = ActionPlan(goal="test gap", actions=[action])
    apply_plan(plan, ctx)
    apply_plan(plan, ctx)

    recorded = g.list_gaps()
    assert len(recorded) == 1, (
        f"Expected 1 deduped gap entry, got {len(recorded)}: {recorded}"
    )
    assert recorded[0]["count"] == 2, (
        f"Expected count=2 for a recurring gap, got {recorded[0]['count']}"
    )


# ---------------------------------------------------------------------------
# Gap log is review-only (Requirement 12 integrity boundary)
# ---------------------------------------------------------------------------

def test_gap_log_does_not_mutate_registry():
    """Recording a gap must not alter ACTION_REGISTRY or any validation rule.

    After applying a plan with an unknown action type (producing a no_such_action
    gap), ACTION_REGISTRY must still be byte-identical to before the call.
    """
    from ai import registry

    keys_before = set(registry.ACTION_REGISTRY)

    # Trigger a no_such_action gap by passing an unknown type directly.
    from ai.models import CapabilityGap
    from ai.gaps import context_hash

    gap = CapabilityGap(
        stage="analyze",
        intent="fantasy_action",
        unmet="no_such_action",
        attempted={},
        context_hash=context_hash("analyze", "fantasy_action", "no_such_action", None),
        skill_id=None,
    )
    g.record(gap)
    g.record(gap)

    keys_after = set(registry.ACTION_REGISTRY)
    assert keys_before == keys_after, (
        "Gap recording mutated ACTION_REGISTRY — the gap log must be review-only."
    )


# ---------------------------------------------------------------------------
# Gauntlet findings (2026-06-29): cosmetic path allowlist + fail-soft apply
# ---------------------------------------------------------------------------

def test_cosmetic_path_allowlist_blocks_data_and_contract():
    """A cosmetic action may only restyle presentation. A JSON-pointer into plotted data or the
    meta.selom contract is REJECTED (the gauntlet-found backdoor) — it must go through recompute,
    where the change is recorded in provenance params ("AI compiles away")."""
    figure_spec = {
        "data": [{"y": [1, 2, 3], "marker": {"color": "red"}}],
        "layout": {"title": {"text": "x"}, "meta": {"selom": {"skill": "volcano"}}},
    }
    ctx = ActionContext(skill_id="volcano", stage="analyze", figure_spec=figure_spec)

    for bad in ("/data", "/data/0", "/data/0/y", "/layout/meta/selom", "/layout/meta/selom/skill"):
        action = Action(type="restyle_figure", target="x", payload={"path": bad, "value": [666]})
        outcome = validate_action(action, ctx)
        assert not outcome.ok, f"{bad!r} should be rejected as a cosmetic target (data/contract)"

    for ok_path in ("/layout/title/text", "/data/0/marker/color", "/data/0/name"):
        action = Action(type="restyle_figure", target="x", payload={"path": ok_path, "value": "z"})
        outcome = validate_action(action, ctx)
        assert outcome.ok, f"{ok_path!r} should be an allowed cosmetic target: {outcome.errors}"


def test_apply_plan_fails_soft_on_apply_raise():
    """A validated action that raises at apply time degrades to status='rejected' — apply_plan
    never lets an uncaught exception escape (the core never crashes on a proposal)."""
    # Action 1 turns /layout/title into a string; action 2 validates against the ORIGINAL spec
    # (title still a dict) but raises at apply against the threaded spec.
    figure_spec = {"layout": {"title": {"text": "x"}}}
    ctx = ActionContext(skill_id="volcano", stage="analyze", figure_spec=figure_spec)
    plan = ActionPlan(goal="break it", actions=[
        Action(type="restyle_figure", target="t", payload={"path": "/layout/title", "value": "flat"}),
        Action(type="restyle_figure", target="t", payload={"path": "/layout/title/text", "value": "y"}),
    ])

    turn = apply_plan(plan, ctx)  # must not raise

    statuses = [r.status for r in turn.results]
    assert "rejected" in statuses, f"expected a soft 'rejected' on the apply-time raise, got {statuses}"


def test_set_param_requires_value():
    """A set_param with no 'value' in payload is rejected at validate (closes the
    payload.get vs payload[] asymmetry → no KeyError at apply)."""
    ctx = ActionContext(skill_id="volcano", stage="analyze")
    action = Action(type="set_param", target="fc_threshold", payload={})
    outcome = validate_action(action, ctx)
    assert not outcome.ok
    assert outcome.errors
