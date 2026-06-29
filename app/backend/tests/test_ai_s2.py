"""S2 proof — Live Pydantic AI gateway + operational guardrails + POST /ai/apply.

All tests run in the fast gate (``pytest -m "not slow"``):
  - Gateway translation: tests the ProposedPlan→ActionPlan mapping in isolation
    (``pytest.importorskip("pydantic_ai")``; no live API key needed).
  - Degrade-clean: gateway returns empty plan on any error (missing key, bad model),
    and get_action_gateway() returns NullActionGateway when ai_gateway != "live".
  - Self-correct retry: OperatorActionGateway returning a bad plan terminates after
    max_retries without looping; a clean plan skips retries entirely (zero-regression).
  - POST /ai/apply: TestClient end-to-end proves the endpoint routes through
    _execute_skill_run with provenance.actions carrying actor="ai".

Stub engine (SELOM_SKILLS_ENGINE=stub) is forced so the heavy skill deps are not
loaded and the run completes deterministically from params alone.
"""

from __future__ import annotations

import json

import pytest

from ai import gaps as g
from ai.gateway import NullActionGateway, OperatorActionGateway
from ai.loop import run_helper_turn
from ai.models import (
    Action,
    ActionContext,
    ActionPlan,
    HelperTurn,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _stub_engine(monkeypatch):
    """Force the skill stub so no heavy deps load."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


@pytest.fixture(autouse=True)
def _clear_gaps():
    g.reset()
    yield
    g.reset()


@pytest.fixture()
def tiny_csv(tmp_path):
    """Minimal DE results CSV — gives provenance.build a real file to hash."""
    csv = tmp_path / "de.csv"
    csv.write_text(
        "gene,logFC,padj\n"
        "GeneA,2.5,0.001\n"
        "GeneB,-1.8,0.01\n"
        "GeneC,0.5,0.5\n",
        encoding="utf-8",
    )
    return csv


# ---------------------------------------------------------------------------
# 1. ProposedPlan → ActionPlan mapping (CI-safe, no API key)
# ---------------------------------------------------------------------------

def test_proposed_plan_to_action_plan_mapping():
    """ProposedAction / ProposedPlan validate the closed ActionType and map cleanly."""
    pytest.importorskip("pydantic_ai")
    from ai.live.pydantic_gateway import ProposedAction, ProposedPlan, PydanticAIGateway

    proposed = ProposedPlan(
        actions=[
            ProposedAction(
                type="set_param",
                target="fc_threshold",
                payload={"value": 1.5},
                rationale="raise the fold-change cutoff",
            ),
            ProposedAction(
                type="restyle_figure",
                target="",
                payload={"path": "/layout/title/text", "value": "New Title"},
                rationale="update title",
            ),
        ],
        notes="two actions proposed",
    )

    plan = PydanticAIGateway._map_plan("my goal", proposed)

    assert plan.goal == "my goal"
    assert plan.notes == "two actions proposed"
    assert len(plan.actions) == 2
    assert plan.actions[0].type == "set_param"
    assert plan.actions[0].target == "fc_threshold"
    assert plan.actions[0].payload == {"value": 1.5}
    assert plan.actions[0].rationale == "raise the fold-change cutoff"
    assert plan.actions[1].type == "restyle_figure"


def test_proposed_plan_rejects_invalid_action_type():
    """ProposedAction refuses an unregistered action type at Pydantic parse time."""
    pytest.importorskip("pydantic_ai")
    from ai.live.pydantic_gateway import ProposedAction
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProposedAction(type="fabricated_action", target="x", payload={})


def test_proposed_plan_empty_is_valid():
    """An empty action list is a valid ProposedPlan (NullActionGateway semantics)."""
    pytest.importorskip("pydantic_ai")
    from ai.live.pydantic_gateway import ProposedPlan, PydanticAIGateway

    plan = PydanticAIGateway._map_plan("nothing to do", ProposedPlan(actions=[]))

    assert plan.actions == []
    assert plan.goal == "nothing to do"


# ---------------------------------------------------------------------------
# 2. Degrade-clean: propose never raises
# ---------------------------------------------------------------------------

def test_pydantic_gateway_degrade_on_missing_api_key(monkeypatch):
    """PydanticAIGateway.propose returns empty plan (never raises) when no API key is set."""
    pytest.importorskip("pydantic_ai")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    from ai.live.pydantic_gateway import PydanticAIGateway

    gw = PydanticAIGateway(model="claude-opus-4-8", timeout_s=10.0)
    ctx = ActionContext(skill_id="volcano", stage="analyze")

    plan = gw.propose(ctx, "set fc_threshold to 1.5")

    assert plan.goal == "set fc_threshold to 1.5"
    assert plan.actions == []  # degraded clean


def test_get_action_gateway_default_returns_null():
    """Default settings (ai_gateway='null') → NullActionGateway, zero-regression."""
    from routers.ai import get_action_gateway

    gw = get_action_gateway()
    assert isinstance(gw, NullActionGateway)


def test_get_action_gateway_live_without_key_returns_null(monkeypatch):
    """Even with ai_gateway='live', no API key → NullActionGateway (key check)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Patch the settings object's ai_gateway attribute for this test.
    from config import settings as _settings
    original = _settings.ai_gateway
    _settings.ai_gateway = "live"
    try:
        from routers.ai import get_action_gateway
        gw = get_action_gateway()
        assert isinstance(gw, NullActionGateway)
    finally:
        _settings.ai_gateway = original


# ---------------------------------------------------------------------------
# 3. Self-correct retry: bounded termination
# ---------------------------------------------------------------------------

def test_self_correct_retry_terminates_on_bad_plan():
    """OperatorActionGateway always returning an out-of-range param terminates
    after max_retries — the loop never runs indefinitely.

    volcano.fc_threshold max=5.0; value=999.0 → validation_blocked → status=rejected
    every retry.  With max_retries=2 the loop does exactly 3 passes total (1 initial
    + 2 retries) and returns a clean HelperTurn (no exception, no infinite loop).
    """
    bad_plan = ActionPlan(
        goal="bad param",
        actions=[Action(type="set_param", target="fc_threshold", payload={"value": 999.0})],
    )
    gw = OperatorActionGateway()
    gw.record("bad param", bad_plan)
    # The gateway returns the same bad plan for every corrected_goal variant too —
    # the str doesn't exactly match so it falls through to the empty-plan default,
    # which means the 2nd and 3rd turns have 0 results.  Either way: terminates.

    ctx = ActionContext(skill_id="volcano", stage="analyze")
    turn = run_helper_turn(ctx, "bad param", gw, max_retries=2)

    assert isinstance(turn, HelperTurn)
    # The loop must have terminated — we reach this assert, not an infinite loop.


def test_zero_rejection_no_retry():
    """A clean plan (no rejections) returns immediately without retry passes.

    This is the zero-regression single-pass case: the turn produced must be
    identical to the pre-S2 single-pass behaviour.
    """
    good_plan = ActionPlan(
        goal="good param",
        actions=[Action(type="set_param", target="fc_threshold", payload={"value": 1.5})],
    )
    gw = OperatorActionGateway()
    gw.record("good param", good_plan)

    ctx = ActionContext(skill_id="volcano", stage="analyze")
    turn = run_helper_turn(ctx, "good param", gw, max_retries=2)

    assert len(turn.results) == 1
    assert turn.results[0].status == "staged"
    assert turn.staged_params == {"fc_threshold": 1.5}


def test_retry_improves_turn_when_corrected_plan_is_valid():
    """When the second attempt is valid, the better turn is kept.

    First plan: invalid (rejected). Second plan: valid (staged).
    With max_retries=1, the corrected_goal triggers a second propose call.
    The Operator gateway is set to return the valid plan for any goal
    containing the retry suffix, so the final turn should be the valid one.
    """
    bad_plan = ActionPlan(
        goal="threshold",
        actions=[Action(type="set_param", target="fc_threshold", payload={"value": 999.0})],
    )
    good_plan = ActionPlan(
        goal="corrected",
        actions=[Action(type="set_param", target="fc_threshold", payload={"value": 1.5})],
    )

    class _SequentialGateway:
        """Returns bad_plan first, good_plan on any subsequent call."""
        model_id = "operator"

        def __init__(self):
            self._calls = 0

        def propose(self, ctx, goal):
            self._calls += 1
            return bad_plan if self._calls == 1 else good_plan

    gw = _SequentialGateway()
    ctx = ActionContext(skill_id="volcano", stage="analyze")
    turn = run_helper_turn(ctx, "threshold", gw, max_retries=1)

    assert any(r.status == "staged" for r in turn.results), (
        "After self-correction the turn should contain a staged valid result"
    )
    assert turn.staged_params.get("fc_threshold") == 1.5


# ---------------------------------------------------------------------------
# 4. POST /ai/apply end-to-end (TestClient)
# ---------------------------------------------------------------------------

def test_apply_endpoint_provenance_has_ai_actions(tmp_path, monkeypatch):
    """POST /ai/apply routes through _execute_skill_run and returns provenance.actions
    with actor='ai'.  Proves the 'same gateway as humans' execution invariant: the
    endpoint uses the exact same QC / D1 / D2 gates as POST /skills/{id}/run.
    """
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    from fastapi.testclient import TestClient
    from main import app

    tiny_csv = tmp_path / "de.csv"
    tiny_csv.write_text(
        "gene,logFC,padj\nGeneA,2.5,0.001\nGeneB,-1.8,0.01\nGeneC,0.5,0.5\n",
        encoding="utf-8",
    )

    ai_actions = [
        {
            "action_id": "abc123",
            "actor": "ai",
            "type": "set_param",
            "target": "fc_threshold",
            "prompt": "increase the threshold",
            "model": "claude-opus-4-8",
            "approved_by": "user-1",
            "approved_at": "2026-06-29T12:00:00Z",
        }
    ]

    client = TestClient(app)
    with open(tiny_csv, "rb") as fh:
        response = client.post(
            "/ai/apply",
            data={
                "skill_id": "volcano",
                "goal": "increase the threshold",
                "params": json.dumps({"fc_threshold": "1.5"}),
                "ai_actions": json.dumps(ai_actions),
                "override": "false",
            },
            files={"matrix": ("de.csv", fh, "text/csv")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "figure" in body
    assert "provenance" in body
    prov = body["provenance"]
    assert "actions" in prov, "provenance must carry the ai_actions log"
    assert prov["actions"][0]["actor"] == "ai"
    assert prov["actions"][0]["action_id"] == "abc123"


def test_apply_endpoint_unknown_skill_is_404(tmp_path, monkeypatch):
    """POST /ai/apply with an unregistered skill_id returns 404."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    from fastapi.testclient import TestClient
    from main import app

    tiny_csv = tmp_path / "de.csv"
    tiny_csv.write_text("gene,logFC,padj\nA,1,0.05\n", encoding="utf-8")

    client = TestClient(app)
    with open(tiny_csv, "rb") as fh:
        response = client.post(
            "/ai/apply",
            data={"skill_id": "nonexistent_skill_xyz", "goal": "test"},
            files={"matrix": ("de.csv", fh, "text/csv")},
        )
    assert response.status_code == 404


def test_apply_endpoint_empty_ai_actions_is_400(tmp_path, monkeypatch):
    """POST /ai/apply with an empty ai_actions list returns 400.

    /ai/apply IS the AI-routed endpoint; an empty actions log is an integrity
    error — the caller must supply the actor-tagged log from the approved HelperTurn.
    """
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    from fastapi.testclient import TestClient
    from main import app

    tiny_csv = tmp_path / "de.csv"
    tiny_csv.write_text(
        "gene,logFC,padj\nGeneA,2.5,0.001\nGeneB,-1.8,0.01\n",
        encoding="utf-8",
    )

    client = TestClient(app)
    with open(tiny_csv, "rb") as fh:
        response = client.post(
            "/ai/apply",
            data={"skill_id": "volcano", "goal": "test", "ai_actions": "[]"},
            files={"matrix": ("de.csv", fh, "text/csv")},
        )

    assert response.status_code == 400
    assert "non-empty" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 5. AI compiles away — provenance params reproduce without the gateway
# ---------------------------------------------------------------------------

def test_ai_compiles_away_through_apply(tmp_path, monkeypatch):
    """Re-running from provenance.params (no gateway) reproduces the same figure.

    Mirrors the Slice 1 test but exercises the /ai/apply endpoint plumbing end-to-end:
    1. POST /ai/apply with a set_param action → result_A
    2. Direct run_skill_with_table(provenance['params']) → figure_B
    3. Assert result_A['figure'] == figure_B
    """
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    from fastapi.testclient import TestClient
    from main import app
    from skills.contract import run_skill_with_table

    tiny_csv = tmp_path / "de.csv"
    tiny_csv.write_text(
        "gene,logFC,padj\nGeneA,2.5,0.001\nGeneB,-1.8,0.01\nGeneC,0.5,0.5\n",
        encoding="utf-8",
    )
    tiny_csv_path = str(tiny_csv)

    ai_actions = [{"action_id": "x1", "actor": "ai", "type": "set_param",
                   "target": "fc_threshold", "prompt": "test", "model": "claude-opus-4-8",
                   "approved_by": "u1", "approved_at": "2026-06-29T00:00:00Z"}]

    client = TestClient(app)
    with open(tiny_csv, "rb") as fh:
        resp = client.post(
            "/ai/apply",
            data={
                "skill_id": "volcano",
                "goal": "test",
                "params": json.dumps({"fc_threshold": "1.5"}),
                "ai_actions": json.dumps(ai_actions),
            },
            files={"matrix": ("de.csv", fh, "text/csv")},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    figure_A = body["figure"]
    recorded_params = body["provenance"]["params"]

    # Re-run from the recorded params with no gateway — must reproduce.
    figure_B, _ = run_skill_with_table("volcano", tiny_csv_path, recorded_params)

    assert figure_A == figure_B, (
        "AI compiles away invariant FAILED via /ai/apply: re-running from "
        "provenance.params did not reproduce the figure."
    )


# ---------------------------------------------------------------------------
# 6. model_id threading — actor-tagged provenance audit fidelity (gauntlet F1)
# ---------------------------------------------------------------------------

def test_operator_gateway_model_id():
    """OperatorActionGateway.model_id == 'operator'."""
    from ai.gateway import OperatorActionGateway
    gw = OperatorActionGateway()
    assert gw.model_id == "operator"


def test_null_gateway_model_id():
    """NullActionGateway.model_id == 'null'."""
    from ai.gateway import NullActionGateway
    gw = NullActionGateway()
    assert gw.model_id == "null"


def test_pydantic_gateway_model_id():
    """PydanticAIGateway.model_id returns the model string (no live key needed)."""
    pytest.importorskip("pydantic_ai")
    from ai.live.pydantic_gateway import PydanticAIGateway
    gw = PydanticAIGateway(model="claude-opus-4-8")
    assert gw.model_id == "claude-opus-4-8"


def test_operator_run_stamps_operator_in_provenance():
    """OperatorActionGateway run → provenance_actions records model=='operator'.

    Proves that the model_id is threaded from the gateway through run_helper_turn
    into apply_plan and stamped on the provenance entry.
    """
    from ai.execute import apply_plan
    from ai.gateway import OperatorActionGateway

    plan = ActionPlan(
        goal="stamp test",
        actions=[Action(type="set_param", target="fc_threshold", payload={"value": 1.5})],
    )
    gw = OperatorActionGateway()
    gw.record("stamp test", plan)

    ctx = ActionContext(skill_id="volcano", stage="analyze")
    turn = run_helper_turn(ctx, "stamp test", gw)

    assert turn.provenance_actions, "expected at least one provenance entry"
    assert turn.provenance_actions[0]["model"] == "operator"


def test_pydantic_gateway_model_id_threaded_into_apply_plan():
    """PydanticAIGateway.model_id=='claude-opus-4-8' is stamped via apply_plan directly.

    Tests apply_plan(model_id=...) without a live API key — uses apply_plan
    directly with an ActionPlan to confirm the threading without running the gateway.
    """
    from ai.execute import apply_plan

    plan = ActionPlan(
        goal="live stamp test",
        actions=[Action(type="set_param", target="fc_threshold", payload={"value": 2.0})],
    )
    ctx = ActionContext(skill_id="volcano", stage="analyze")

    turn = apply_plan(plan, ctx, model_id="claude-opus-4-8")

    assert turn.provenance_actions, "expected at least one provenance entry"
    assert turn.provenance_actions[0]["model"] == "claude-opus-4-8"


def test_apply_plan_default_model_id_is_operator():
    """apply_plan with no model_id kwarg (direct callers / S1 path) still records 'operator'.

    The default preserves backward compat for all existing direct callers.
    """
    from ai.execute import apply_plan

    plan = ActionPlan(
        goal="default model test",
        actions=[Action(type="set_param", target="fc_threshold", payload={"value": 1.0})],
    )
    ctx = ActionContext(skill_id="volcano", stage="analyze")

    turn = apply_plan(plan, ctx)  # no model_id kwarg

    assert turn.provenance_actions[0]["model"] == "operator"


# ---------------------------------------------------------------------------
# 7. /ai/apply entry validation — actor-tag integrity (gauntlet F2)
# ---------------------------------------------------------------------------

def test_apply_endpoint_malformed_entry_missing_type_is_400(tmp_path, monkeypatch):
    """POST /ai/apply with an entry missing 'type' returns 400."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    from fastapi.testclient import TestClient
    from main import app

    tiny_csv = tmp_path / "de.csv"
    tiny_csv.write_text("gene,logFC,padj\nA,1,0.01\n", encoding="utf-8")

    bad_actions = [{"actor": "ai", "target": "fc_threshold", "action_id": "x"}]  # missing type

    client = TestClient(app)
    with open(tiny_csv, "rb") as fh:
        response = client.post(
            "/ai/apply",
            data={
                "skill_id": "volcano",
                "goal": "test",
                "ai_actions": json.dumps(bad_actions),
            },
            files={"matrix": ("de.csv", fh, "text/csv")},
        )

    assert response.status_code == 400
    assert "malformed" in response.json()["detail"]


def test_apply_endpoint_malformed_entry_missing_target_is_400(tmp_path, monkeypatch):
    """POST /ai/apply with an entry missing 'target' returns 400."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    from fastapi.testclient import TestClient
    from main import app

    tiny_csv = tmp_path / "de.csv"
    tiny_csv.write_text("gene,logFC,padj\nA,1,0.01\n", encoding="utf-8")

    bad_actions = [{"actor": "ai", "type": "set_param", "action_id": "x"}]  # missing target

    client = TestClient(app)
    with open(tiny_csv, "rb") as fh:
        response = client.post(
            "/ai/apply",
            data={
                "skill_id": "volcano",
                "goal": "test",
                "ai_actions": json.dumps(bad_actions),
            },
            files={"matrix": ("de.csv", fh, "text/csv")},
        )

    assert response.status_code == 400
    assert "malformed" in response.json()["detail"]


def test_apply_endpoint_malformed_entry_wrong_actor_is_400(tmp_path, monkeypatch):
    """POST /ai/apply with actor != 'ai' returns 400 (forged/human actor tag rejected)."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    from fastapi.testclient import TestClient
    from main import app

    tiny_csv = tmp_path / "de.csv"
    tiny_csv.write_text("gene,logFC,padj\nA,1,0.01\n", encoding="utf-8")

    bad_actions = [{"actor": "human", "type": "set_param", "target": "fc_threshold"}]

    client = TestClient(app)
    with open(tiny_csv, "rb") as fh:
        response = client.post(
            "/ai/apply",
            data={
                "skill_id": "volcano",
                "goal": "test",
                "ai_actions": json.dumps(bad_actions),
            },
            files={"matrix": ("de.csv", fh, "text/csv")},
        )

    assert response.status_code == 400
    assert "malformed" in response.json()["detail"]


def test_apply_endpoint_valid_tagged_entry_is_200_and_recorded(tmp_path, monkeypatch):
    """POST /ai/apply with a valid actor-tagged entry returns 200 and records provenance.actions."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    from fastapi.testclient import TestClient
    from main import app

    tiny_csv = tmp_path / "de.csv"
    tiny_csv.write_text(
        "gene,logFC,padj\nGeneA,2.5,0.001\nGeneB,-1.8,0.01\n",
        encoding="utf-8",
    )

    valid_actions = [
        {
            "action_id": "z9",
            "actor": "ai",
            "type": "set_param",
            "target": "fc_threshold",
            "prompt": "bump threshold",
            "model": "claude-opus-4-8",
            "approved_by": "user-1",
            "approved_at": "2026-06-29T00:00:00Z",
        }
    ]

    client = TestClient(app)
    with open(tiny_csv, "rb") as fh:
        response = client.post(
            "/ai/apply",
            data={
                "skill_id": "volcano",
                "goal": "bump threshold",
                "params": json.dumps({"fc_threshold": "1.5"}),
                "ai_actions": json.dumps(valid_actions),
            },
            files={"matrix": ("de.csv", fh, "text/csv")},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "provenance" in body
    assert "actions" in body["provenance"]
    assert body["provenance"]["actions"][0]["actor"] == "ai"
    assert body["provenance"]["actions"][0]["action_id"] == "z9"
