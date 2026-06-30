"""Live Vercel AI Gateway client + operator-recordings seam + gateway selection.

All network is stubbed with ``httpx.MockTransport`` (no real calls, no credit). Covers:
- ``VercelAIGateway.explain`` / ``.propose`` happy path + degrade-clean (error/timeout/bad JSON)
- retry on a retryable status, bounded prompt (no plotted data arrays cross the wire)
- ``OperatorActionGateway.from_recordings`` (the canned demo engine) + per-input keying
- the bundled ``ai/recordings/explain.json`` integrity (the 3 showcase papers light up)
- ``get_action_gateway()`` mode selection (null | operator | gateway | live)

Spec: docs/ai-gateway-wiring/spec.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ai.gateway import (
    NullActionGateway,
    OperatorActionGateway,
    _deterministic_explain,
)
from ai.live.vercel_gateway import VercelAIGateway
from ai.models import ActionContext


def _completion(content: str, status: int = 200) -> httpx.Response:
    """An OpenAI-compatible chat-completion response carrying ``content``."""
    return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})


def _gateway(handler, **kw) -> VercelAIGateway:
    """A VercelAIGateway wired to a MockTransport handler; no real sleeps."""
    args = dict(
        api_key="vck_test",
        model="meta/llama-3.3-70b",
        base_url="https://ai-gateway.vercel.sh/v1",
        provider_order=["groq", "bedrock"],
        max_tokens=400,
        timeout_s=5.0,
        transport=httpx.MockTransport(handler),
        sleep=lambda _s: None,
    )
    args.update(kw)
    return VercelAIGateway(**args)


# ---------------------------------------------------------------------------
# VercelAIGateway.explain
# ---------------------------------------------------------------------------

def test_vercel_explain_returns_model_text():
    gw = _gateway(lambda req: _completion("The score is high because every panel matched."))
    data = {"scorecard": {"score": 96, "tier": "verified"}}

    text = gw.explain("explain_score", data, "explain the score")

    assert text == "The score is high because every panel matched."
    # Distinct from the deterministic summary → the endpoint will label it source="ai".
    assert text != _deterministic_explain("explain_score", data, "explain the score")


def test_vercel_explain_degrades_on_api_error():
    """A persistent 500 → deterministic fallback, no raise."""
    gw = _gateway(lambda req: _completion("nope", status=500))
    data = {"scorecard": {"score": 63, "tier": "deposit-faithful"}}

    text = gw.explain("explain_score", data, "g")

    assert text == _deterministic_explain("explain_score", data, "g")
    assert "63" in text


def test_vercel_explain_empty_completion_falls_back():
    """An empty model completion is a degrade, not an answer → deterministic fallback."""
    gw = _gateway(lambda req: _completion("   "))
    data = {"scorecard": {"score": 50, "tier": "low"}}

    text = gw.explain("explain_score", data, "g")
    assert text == _deterministic_explain("explain_score", data, "g")


def test_vercel_explain_degrades_on_transport_error():
    def boom(req):
        raise httpx.ConnectError("down")

    gw = _gateway(boom)
    data = {"scorecard": {"score": 70, "tier": "partial"}}
    assert gw.explain("explain_score", data, "g") == _deterministic_explain(
        "explain_score", data, "g"
    )


# ---------------------------------------------------------------------------
# VercelAIGateway.propose
# ---------------------------------------------------------------------------

def test_vercel_propose_parses_validated_plan():
    plan_json = json.dumps(
        {
            "actions": [
                {
                    "type": "set_param",
                    "target": "fc_threshold",
                    "payload": {"value": 1.5},
                    "rationale": "widen the call",
                }
            ],
            "notes": "one tweak",
        }
    )
    gw = _gateway(lambda req: _completion(plan_json))
    ctx = ActionContext(stage="analyze", skill_id=None, params={"fc_threshold": 1.0})

    plan = gw.propose(ctx, "raise fold-change")

    assert plan.goal == "raise fold-change"
    assert len(plan.actions) == 1
    assert plan.actions[0].type == "set_param"
    assert plan.actions[0].target == "fc_threshold"
    assert plan.actions[0].payload == {"value": 1.5}
    assert plan.notes == "one tweak"


def test_vercel_propose_tolerates_fenced_json():
    """Markdown fences / surrounding prose around the JSON object are stripped."""
    fenced = "Here you go:\n```json\n" + json.dumps({"actions": [], "notes": "n/a"}) + "\n```"
    gw = _gateway(lambda req: _completion(fenced))
    plan = gw.propose(ActionContext(stage="analyze"), "g")
    assert plan.actions == []
    assert plan.notes == "n/a"


def test_vercel_propose_bad_json_degrades_to_empty_plan():
    gw = _gateway(lambda req: _completion("not json at all"))
    plan = gw.propose(ActionContext(stage="analyze"), "g")
    assert plan.actions == []


def test_vercel_propose_invalid_action_type_degrades():
    """An action type outside the closed vocabulary fails ProposedPlan validation → empty plan."""
    bad = json.dumps({"actions": [{"type": "rm_rf", "target": "x"}], "notes": ""})
    gw = _gateway(lambda req: _completion(bad))
    plan = gw.propose(ActionContext(stage="analyze"), "g")
    assert plan.actions == []


# ---------------------------------------------------------------------------
# transport behaviour: retry + bounded prompt
# ---------------------------------------------------------------------------

def test_vercel_retries_on_retryable_status_then_succeeds():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] == 1:
            return _completion("rate limited", status=429)
        return _completion("ok after retry")

    gw = _gateway(handler)
    assert gw.explain("explain_score", {"scorecard": {"score": 1}}, "g") == "ok after retry"
    assert calls["n"] == 2


def test_vercel_propose_prompt_never_carries_plotted_data_arrays():
    """The bounded prompt sends figure SHAPE only — never the plotted data arrays."""
    seen = {"body": b""}

    def handler(req):
        seen["body"] = req.content
        return _completion(json.dumps({"actions": [], "notes": ""}))

    gw = _gateway(handler)
    ctx = ActionContext(
        stage="output",
        skill_id=None,
        figure_spec={"data": [{"x": [11, 22, 33], "y": [44, 55, 66]}], "layout": {"title": {}}},
    )
    gw.propose(ctx, "restyle it")

    body = seen["body"].decode("utf-8")
    assert "data_trace_count" in body  # shape summary present
    assert "44" not in body and "55" not in body  # plotted values absent
    assert "[11, 22, 33]" not in body


def test_vercel_model_id_is_the_configured_model():
    gw = _gateway(lambda req: _completion("x"), model="openai/gpt-4o")
    assert gw.model_id == "openai/gpt-4o"  # provider-agnostic: stamped into provenance


# ---------------------------------------------------------------------------
# OperatorActionGateway.from_recordings — the canned demo engine
# ---------------------------------------------------------------------------

_RECORDINGS = Path(__file__).resolve().parents[1] / "ai" / "recordings" / "explain.json"


def test_recordings_file_is_well_formed():
    doc = json.loads(_RECORDINGS.read_text(encoding="utf-8"))
    keys = set()
    for entry in doc["explanations"]:
        assert entry["request_type"] and entry["key"] and entry["text"]
        keys.add((entry["request_type"], entry["key"]))
    # The 3 showcase papers' explain_score all light up.
    for slug in ("rpgrip1", "jev", "hani"):
        assert ("explain_score", slug) in keys


@pytest.mark.parametrize("slug", ["rpgrip1", "jev", "hani"])
def test_operator_lights_up_showcase_paper(slug):
    gw = OperatorActionGateway.from_recordings(str(_RECORDINGS))
    data = {"scorecard": {"paper_id": slug, "score": 90, "tier": "verified"}}

    text = gw.explain("explain_score", data, goal="")

    # Recorded prose, distinct from the deterministic fallback → endpoint labels it source="ai".
    assert len(text) > 80
    assert text != _deterministic_explain("explain_score", data, "")


def test_operator_unknown_paper_degrades_to_deterministic():
    gw = OperatorActionGateway.from_recordings(str(_RECORDINGS))
    data = {"scorecard": {"paper_id": "not-a-paper", "score": 42, "tier": "low"}}

    text = gw.explain("explain_score", data, goal="")
    assert text == _deterministic_explain("explain_score", data, "")
    assert "42" in text


def test_operator_from_missing_recordings_is_empty_not_raising():
    gw = OperatorActionGateway.from_recordings("/no/such/file.json")
    data = {"scorecard": {"paper_id": "rpgrip1", "score": 7, "tier": "x"}}
    # No recordings loaded → deterministic fallback (Null semantics), never raises.
    assert gw.explain("explain_score", data, "") == _deterministic_explain(
        "explain_score", data, ""
    )


def test_operator_legacy_goal_keying_still_resolves():
    """Back-compat: the programmatic record_explanation (goal-keyed) path still works."""
    gw = OperatorActionGateway.from_recordings(str(_RECORDINGS))
    gw.record_explanation("explain_score", "my-goal", "goal-keyed text")
    # data has no paper_id → input key is None → falls through to the goal key.
    assert gw.explain("explain_score", {}, "my-goal") == "goal-keyed text"


def test_operator_input_key_wins_over_goal_key():
    """When both an input key and a goal key are recorded, the per-input key takes precedence."""
    gw = OperatorActionGateway.from_recordings(str(_RECORDINGS))
    gw.record_explanation("explain_score", "rpgrip1", "GOAL-KEYED")  # goal == "rpgrip1"
    data = {"scorecard": {"paper_id": "jev"}}
    # input key jev resolves to the recorded jev text, not the goal-keyed "rpgrip1" entry.
    text = gw.explain("explain_score", data, goal="rpgrip1")
    assert text != "GOAL-KEYED"
    assert "86/100" in text  # the jev recording


# ---------------------------------------------------------------------------
# get_action_gateway() mode selection
# ---------------------------------------------------------------------------

def _set_mode(monkeypatch, **fields):
    from config import settings

    for k, v in fields.items():
        monkeypatch.setattr(settings, k, v)


def test_select_operator_mode(monkeypatch):
    from routers.ai import get_action_gateway

    _set_mode(monkeypatch, ai_gateway="operator")
    assert isinstance(get_action_gateway(), OperatorActionGateway)


def test_select_gateway_mode_with_key(monkeypatch):
    from routers.ai import get_action_gateway

    _set_mode(monkeypatch, ai_gateway="gateway", ai_gateway_api_key="vck_x")
    gw = get_action_gateway()
    assert isinstance(gw, VercelAIGateway)
    assert gw.model_id  # the configured model


def test_select_gateway_mode_without_key_falls_back_to_null(monkeypatch):
    from routers.ai import get_action_gateway

    _set_mode(monkeypatch, ai_gateway="gateway", ai_gateway_api_key=None)
    assert isinstance(get_action_gateway(), NullActionGateway)


def test_select_default_is_null(monkeypatch):
    from routers.ai import get_action_gateway

    _set_mode(monkeypatch, ai_gateway="null")
    assert isinstance(get_action_gateway(), NullActionGateway)


def test_select_live_mode_without_anthropic_key_falls_back(monkeypatch):
    from routers.ai import get_action_gateway

    _set_mode(monkeypatch, ai_gateway="live")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_action_gateway(), NullActionGateway)
