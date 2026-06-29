"""ActionGateway Protocol + implementations (Slice 1 — no live LLM).

AI proposes, never originates a mutation.  The gateway is a subroutine of the
deterministic loop (``ai.loop.run_helper_turn``); the deterministic core is never
on the AI's critical path.  A live ``PydanticAIGateway`` slots in behind this
Protocol in Slice 2 without touching the loop or the registry.

Mirrors the ``RouteVerifier`` / ``VisionGateway`` discipline (``extract/routing/
verify.py``, ``extract/vision.py``): a typed Protocol with an always-available
no-op default and a replayable operator stand-in for CI-safe testing.

S4 extension: the ``explain`` method supports the informational helper path
(``POST /ai/explain``).  It is NOT a mutation — it produces explanatory text grounded
in deterministic data passed by the caller (scorecard / sweep space) and never goes
through the action registry or ``apply_plan``.  With ``NullActionGateway`` the
fallback is a short deterministic summary of the passed data; with the live gateway
it is AI-generated text grounded in the same data.  Degrade-clean in both directions.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ai.models import ActionContext, ActionPlan


# ---------------------------------------------------------------------------
# Deterministic fallbacks for explain (used by Null + Operator gateways).
# ---------------------------------------------------------------------------

def _deterministic_explain(request_type: str, data: dict, goal: str) -> str:
    """Build a deterministic explanation from the caller-supplied data.

    Grounded entirely in the ``data`` dict passed by the caller (a scorecard or a
    sweep-space dict) — never fabricated.  Used as the fallback when no live
    gateway is available and as the TestModel stand-in in CI.
    """
    if request_type == "explain_score":
        sc = data.get("scorecard") or {}
        score = sc.get("score", "n/a")
        tier = sc.get("tier", "unknown")
        panels = sc.get("panels", [])
        n_panels = len(panels) if isinstance(panels, list) else sc.get("panel_count", 0)
        return (
            f"Score: {score}/100 (tier: {tier}). "
            f"{n_panels} panel(s) scored. "
            "Improve by supplying data that matches the paper's figures more closely."
        )
    if request_type == "propose_sweep":
        sw = data.get("sweep_space") or {}
        if not sw:
            return (
                "No sweep space provided — specify parameters and their ranges to sweep."
            )
        params = list(sw.keys())
        return (
            f"Consider sweeping: {', '.join(params)}. "
            "Focus on parameters with the widest impact range first."
        )
    return "unavailable"


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class ActionGateway(Protocol):
    """The AI write-path seam.

    ``propose`` returns an ActionPlan drawn from the closed ACTION_REGISTRY.
    ``explain`` returns grounded explanatory text (NOT a mutation — not an action).
    A gateway that returns an empty plan / a deterministic string (the default) leaves
    every existing behaviour unchanged (zero-regression guarantee).
    """

    def propose(self, context: ActionContext, goal: str) -> ActionPlan: ...

    def explain(self, request_type: str, data: dict, goal: str) -> str:
        """Return grounded explanatory text for an informational helper request.

        ``request_type`` is one of ``"explain_score"`` / ``"propose_sweep"``.
        ``data`` carries the deterministic artifacts grounding the explanation
        (scorecard dict, sweep-space dict).  Must never fabricate data values.
        Degrade-clean: an unavailable gateway returns a deterministic fallback.
        """
        ...


# ---------------------------------------------------------------------------
# Null gateway (always-available default)
# ---------------------------------------------------------------------------

class NullActionGateway:
    """The always-available default: no gateway, empty plan / deterministic text.

    With NullActionGateway as the active gateway, ``run_helper_turn`` returns a
    HelperTurn with no actions, no staged params, and no gaps — identical to
    pre-spec behaviour (the offline / degraded-gracefully guarantee).

    ``explain`` returns a short deterministic summary grounded in the passed data
    so the informational endpoint degrades gracefully rather than returning nothing.
    """

    def propose(self, context: ActionContext, goal: str) -> ActionPlan:
        return ActionPlan(goal=goal, actions=[])

    def explain(self, request_type: str, data: dict, goal: str) -> str:
        return _deterministic_explain(request_type, data, goal)


# ---------------------------------------------------------------------------
# Operator gateway (CI-safe replay stand-in)
# ---------------------------------------------------------------------------

class OperatorActionGateway:
    """Claude-as-gateway dev/dogfood stand-in: replays operator-recorded ActionPlans.

    Plans are keyed by goal string.  A goal with no recorded plan returns an empty
    plan (NullActionGateway semantics) — the seam never fabricates an action.
    Use ``record`` to build up the replay set before passing this to the loop.

    ``record_explanation`` / ``explain`` mirror the same replay discipline for
    informational helper requests (``POST /ai/explain``): a recorded text is
    returned; unrecorded goals fall back to the deterministic summary.

    This is the CI-safe, LLM-free implementation used in tests; it lets the entire
    propose→validate→stage/apply loop and the informational path run deterministically.
    """

    def __init__(
        self,
        plans: dict[str, ActionPlan] | list[ActionPlan] | None = None,
    ) -> None:
        items = plans.values() if isinstance(plans, dict) else (plans or [])
        self._plans: dict[str, ActionPlan] = {p.goal: p for p in items}
        self._explanations: dict[str, str] = {}

    def record(self, goal: str, plan: ActionPlan) -> None:
        """Add or replace a plan for ``goal`` (used as the operator works through a run)."""
        self._plans[goal] = plan

    def record_explanation(self, request_type: str, goal: str, text: str) -> None:
        """Add or replace an explanation for the given request_type + goal pair."""
        self._explanations[f"{request_type}:{goal}"] = text

    def propose(self, context: ActionContext, goal: str) -> ActionPlan:
        return self._plans.get(goal, ActionPlan(goal=goal, actions=[]))

    def explain(self, request_type: str, data: dict, goal: str) -> str:
        key = f"{request_type}:{goal}"
        return self._explanations.get(key, _deterministic_explain(request_type, data, goal))
