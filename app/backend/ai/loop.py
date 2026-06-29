"""Bounded propose→validate→(stage|apply)→observe driver (Slice 1 + Slice 2).

The loop is deterministic code; the AI is a subroutine.  It terminates on a
deterministic condition (schema valid / user approves / max turns), never on
the AI's self-declared "done" alone (Requirement 9).

Slice 2 extends with ≤max_retries self-correction passes: if an initial
apply_plan leaves rejected actions and retries remain, the gateway is called
again with the rejection errors appended to the goal context.  The loop is
strictly bounded by count — a Null/Operator gateway that returns the same plan
each time will hit at most max_retries iterations before terminating; it never
loops indefinitely regardless of gateway behaviour.
"""

from __future__ import annotations

from ai.execute import apply_plan
from ai.gateway import ActionGateway
from ai.models import ActionContext, HelperTurn


def run_helper_turn(
    ctx: ActionContext,
    goal: str,
    gateway: ActionGateway,
    *,
    max_retries: int = 2,
) -> HelperTurn:
    """Run one propose→validate→(stage|apply) pass with ≤max_retries self-correction.

    ``gateway.propose`` is the only AI call in this function; everything else is
    deterministic.  With a ``NullActionGateway`` the plan is empty and the
    returned ``HelperTurn`` carries no results, no staged params, and no gaps —
    byte-identical to pre-spec behaviour (zero-regression guarantee).

    Self-correction (Slice 2): if the initial apply_plan leaves any rejected
    actions and ``max_retries > 0``, the gateway is recalled with the rejection
    errors appended to the goal context so it can propose corrected actions.
    The loop terminates when either:
      - no rejections remain (clean turn), or
      - ``max_retries`` iterations are exhausted (deterministic count cap).
    The turn with the most applied/staged results is kept so the loop never
    degrades a turn that was already partially valid.

    Parameters
    ----------
    ctx:
        Stateless action context (stage, skill, current params, figure spec).
    goal:
        The user's NL request, passed verbatim to the gateway.
    gateway:
        The AI seam — ``NullActionGateway`` for zero-regression offline mode,
        ``OperatorActionGateway`` for CI replay, ``PydanticAIGateway`` live.
    max_retries:
        Maximum number of self-correction attempts after the initial pass.
        0 = single-pass (Slice 1 behaviour).  Bounded deterministically.
    """
    plan = gateway.propose(ctx, goal)
    turn = apply_plan(plan, ctx)

    for _ in range(max_retries):
        rejected = [r for r in turn.results if r.status == "rejected"]
        if not rejected:
            break  # clean turn — no self-correction needed

        errors_text = "; ".join(e for r in rejected for e in r.errors)
        corrected_goal = (
            f"{goal} [previous attempt was rejected: {errors_text}; "
            "propose corrected actions]"
        )
        new_plan = gateway.propose(ctx, corrected_goal)
        new_turn = apply_plan(new_plan, ctx)

        # Keep the better turn: prefer the one with more applied/staged results.
        def _valid_count(t: HelperTurn) -> int:
            return sum(1 for r in t.results if r.status in ("applied", "staged"))

        if _valid_count(new_turn) >= _valid_count(turn):
            turn = new_turn

    return turn
