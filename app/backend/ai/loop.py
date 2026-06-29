"""Bounded propose→validate→(stage|apply)→observe driver (Slice 1).

The loop is deterministic code; the AI is a subroutine.  It terminates on a
deterministic condition (schema valid / user approves / max turns), never on
the AI's self-declared "done" alone (Requirement 9).

Single-pass for Slice 1 — the AI proposes once per call.  Self-correction
retries (≤ 2) and the multi-turn observe→re-propose cycle are Slice 2.
"""

from __future__ import annotations

from ai.execute import apply_plan
from ai.gateway import ActionGateway
from ai.models import ActionContext, HelperTurn


def run_helper_turn(
    ctx: ActionContext,
    goal: str,
    gateway: ActionGateway,
) -> HelperTurn:
    """Run one propose→validate→(stage|apply) pass.

    ``gateway.propose`` is the only AI call in this function; everything else is
    deterministic.  With a ``NullActionGateway`` the plan is empty and the
    returned ``HelperTurn`` carries no results, no staged params, and no gaps —
    byte-identical to pre-spec behaviour (zero-regression guarantee).
    """
    plan = gateway.propose(ctx, goal)

    # S2: ≤2 self-correct retries on rejected actions (re-propose with the errors)
    return apply_plan(plan, ctx)
