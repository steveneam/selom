"""ActionGateway Protocol + implementations (Slice 1 — no live LLM).

AI proposes, never originates a mutation.  The gateway is a subroutine of the
deterministic loop (``ai.loop.run_helper_turn``); the deterministic core is never
on the AI's critical path.  A live ``PydanticAIGateway`` slots in behind this
Protocol in Slice 2 without touching the loop or the registry.

Mirrors the ``RouteVerifier`` / ``VisionGateway`` discipline (``extract/routing/
verify.py``, ``extract/vision.py``): a typed Protocol with an always-available
no-op default and a replayable operator stand-in for CI-safe testing.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ai.models import ActionContext, ActionPlan


@runtime_checkable
class ActionGateway(Protocol):
    """The AI write-path seam.

    ``propose`` returns an ActionPlan drawn from the closed ACTION_REGISTRY.
    It only ever *proposes* — it never applies, validates, or reads state
    directly.  A gateway that returns an empty plan (the default) leaves
    every existing behaviour unchanged (zero-regression guarantee).
    """

    def propose(self, context: ActionContext, goal: str) -> ActionPlan: ...


class NullActionGateway:
    """The always-available default: no gateway, empty plan every time.

    With NullActionGateway as the active gateway, ``run_helper_turn`` returns a
    HelperTurn with no actions, no staged params, and no gaps — identical to
    pre-spec behaviour (the offline / degraded-gracefully guarantee).
    """

    def propose(self, context: ActionContext, goal: str) -> ActionPlan:
        return ActionPlan(goal=goal, actions=[])


class OperatorActionGateway:
    """Claude-as-gateway dev/dogfood stand-in: replays operator-recorded ActionPlans.

    Plans are keyed by goal string.  A goal with no recorded plan returns an empty
    plan (NullActionGateway semantics) — the seam never fabricates an action.
    Use ``record`` to build up the replay set before passing this to the loop.

    This is the CI-safe, LLM-free implementation used in Slice 1 tests; it lets
    the entire propose→validate→stage/apply loop run deterministically.
    """

    def __init__(
        self,
        plans: dict[str, ActionPlan] | list[ActionPlan] | None = None,
    ) -> None:
        items = plans.values() if isinstance(plans, dict) else (plans or [])
        self._plans: dict[str, ActionPlan] = {p.goal: p for p in items}

    def record(self, goal: str, plan: ActionPlan) -> None:
        """Add or replace a plan for ``goal`` (used as the operator works through a run)."""
        self._plans[goal] = plan

    def propose(self, context: ActionContext, goal: str) -> ActionPlan:
        return self._plans.get(goal, ActionPlan(goal=goal, actions=[]))
