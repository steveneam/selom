"""Validate + apply an ActionPlan against the deterministic core (Slice 1).

This module is the only entry point from the AI side into the skill execution
path.  No action handler is ever called from outside this module.

Two public functions:
  validate_action(action, ctx) → ValidationOutcome
      Dispatches to the registry handler.  An unregistered type is immediately
      refused with a no_such_action gap — the AI cannot invent a mutation type.

  apply_plan(plan, ctx) → HelperTurn
      Iterates the plan, validates each action, then either applies cosmetics
      (threading the figure_spec through successive patches), stages recomputes
      (merging into staged_params), or records a gap/rejection.  Provenance
      entries are emitted for every applied/staged action.

  commit_recompute(skill_id, data_path, base_params, staged_params, *, …) → dict
      Merges base+staged, runs the skill via the injected runner, builds the
      reproducibility bundle.  The injectable ``runner`` makes this stack-free-
      testable and is the "AI compiles away" hinge: re-running from the recorded
      ``params`` with no gateway reproduces the figure byte-for-byte.
"""

from __future__ import annotations

import copy

from ai.models import (
    Action,
    ActionContext,
    ActionPlan,
    ActionResult,
    CapabilityGap,
    HelperTurn,
    ValidationOutcome,
)


def validate_action(action: Action, ctx: ActionContext) -> ValidationOutcome:
    """Dispatch to the registry handler.  Unknown type → ValidationOutcome(ok=False, gap).

    The gap is recorded by the caller (apply_plan) so the structure guard can assert
    that no validation path lives outside this module.
    """
    from ai import registry as reg
    from ai.gaps import context_hash

    if not reg.is_registered(action.type):
        ch = context_hash(ctx.stage, action.type, "no_such_action", ctx.skill_id)
        gap = CapabilityGap(
            stage=ctx.stage,
            intent=action.type,
            unmet="no_such_action",
            attempted={"type": action.type, "target": action.target, "payload": action.payload},
            context_hash=ch,
            skill_id=ctx.skill_id,
        )
        return ValidationOutcome(
            ok=False,
            errors=[f"unknown action type {action.type!r} — not in the closed registry"],
            gap=gap,
        )

    return reg.get(action.type).validate(action, ctx)


def apply_plan(plan: ActionPlan, ctx: ActionContext, *, model_id: str = "operator") -> HelperTurn:
    """Validate and dispatch every action in ``plan``.

    Cosmetic actions are applied immediately and their figure_spec patches are
    threaded: each action sees the spec as the *previous* action left it, so a
    sequence of label+restyle changes accumulates correctly.

    Recompute actions merge their param delta into ``staged_params`` — the queue
    that ``commit_recompute`` consumes on user approval.

    Gaps (coherent but unfulfillable intents) are recorded into ``ai.gaps`` for
    the frequency-ranked backlog; the loop step that dropped the action falls back
    to the existing manual UI for that control.
    """
    from ai import gaps as g
    from ai import registry as reg

    results: list[ActionResult] = []
    staged_params: dict = {}
    gap_list: list[CapabilityGap] = []
    provenance_actions: list[dict] = []

    # Start from a deep copy so successive cosmetic actions accumulate on one spec.
    running_figure_spec = copy.deepcopy(ctx.figure_spec) if ctx.figure_spec is not None else None

    for action in plan.actions:
        outcome = validate_action(action, ctx)
        # Derive tier from the registry; fall back to the fail-safe "recompute" for
        # unknown types (the validate path above already refused them, but the tier
        # is needed to build the ActionResult).
        tier = reg.tier_of(action.type) if reg.is_registered(action.type) else "recompute"

        if not outcome.ok:
            if outcome.gap is not None:
                g.record(outcome.gap)
                gap_list.append(outcome.gap)
                # validation_blocked = coherent attempt, value refused → "rejected"
                # all other gap codes = capability absent → "gap" (backlog candidate)
                status: str = (
                    "rejected" if outcome.gap.unmet == "validation_blocked" else "gap"
                )
            else:
                # Malformed payload with no gap (e.g. missing 'path' key in restyle)
                status = "rejected"

            results.append(ActionResult(
                action_id=action.id,
                type=action.type,
                target=action.target,
                tier=tier,
                status=status,  # type: ignore[arg-type]
                errors=outcome.errors,
                gap=outcome.gap,
            ))
            continue

        # Valid action — apply it. FAIL SOFT: a validated-but-unapplicable action (e.g. a threaded-
        # spec mismatch the top-of-loop validate couldn't foresee) degrades to a rejected result —
        # the deterministic core never crashes on an AI proposal.
        try:
            if tier == "cosmetic":
                # Thread the running figure_spec so each cosmetic action builds on the last.
                apply_ctx = ctx.model_copy(update={"figure_spec": running_figure_spec})
                effect = reg.get(action.type).apply(action, apply_ctx)
                if "figure_spec" in effect:
                    running_figure_spec = effect["figure_spec"]
                status = "applied"
            else:
                # Recompute — stage the param delta; don't execute yet.
                effect = reg.get(action.type).apply(action, ctx)
                staged_params.update(effect.get("params", {}))
                status = "staged"
        except (KeyError, ValueError, IndexError, TypeError) as exc:
            results.append(ActionResult(
                action_id=action.id, type=action.type, target=action.target,
                tier=tier, status="rejected",
                errors=[f"action could not be applied: {exc!r}"],
            ))
            continue

        results.append(ActionResult(
            action_id=action.id,
            type=action.type,
            target=action.target,
            tier=tier,
            status=status,  # type: ignore[arg-type]
            effect=effect,
        ))

        # Actor-tagged provenance entry for every successfully applied/staged action.
        provenance_actions.append({
            "action_id": action.id,
            "actor": "ai",
            "type": action.type,
            "target": action.target,
            "prompt": plan.goal,
            "model": model_id,
            "approved_by": None,
            "approved_at": None,
        })

    return HelperTurn(
        goal=plan.goal,
        plan=plan,
        results=results,
        staged_params=staged_params,
        figure_spec=running_figure_spec,
        gaps=gap_list,
        provenance_actions=provenance_actions,
    )


def commit_recompute(
    skill_id: str,
    data_path: str,
    base_params: dict,
    staged_params: dict,
    *,
    goal: str,
    approved_by=None,
    approved_at=None,
    filename: str | None = None,
    runner=None,
    provenance_actions: list[dict] | None = None,
) -> dict:
    """Execute approved recompute actions and return the full result bundle.

    Merges ``base_params`` + ``staged_params``, runs the skill via ``runner``
    (default: ``run_skill_with_table`` — injectable for stack-free testing),
    then builds the reproducibility bundle.

    The injectable ``runner`` is the "AI compiles away" hinge: after this call,
    anyone can reproduce the figure by calling ``runner(skill_id, data_path,
    provenance["params"])`` with zero AI in the loop.  AI helped *choose* the
    params; the params — not the AI — are what the deterministic core executes.

    ``provenance_actions`` carries the actor-tagged log entries stamped with
    ``approved_by`` / ``approved_at`` for the reproducibility bundle.
    """
    from companions import provenance
    from skills.contract import load_skill, resolved_params, run_skill_with_table

    if runner is None:
        runner = run_skill_with_table

    merged = {**base_params, **staged_params}
    figure, table = runner(skill_id, data_path, merged)
    spec = load_skill(skill_id)

    # Stamp attribution through the ONE chokepoint (NEXT#1) — never merge approved_by into a raw
    # actions dict here. stamp_ai_actions re-derives actor/model/approved_by/approved_at and keeps
    # only the descriptive delta, so this path cannot become a second, forgeable stamping site. The
    # model is the one apply_plan already recorded on the proposal (same model across a turn).
    actions_to_record: list[dict] | None = None
    if provenance_actions:
        actions_to_record = provenance.stamp_ai_actions(
            provenance_actions,
            model=provenance_actions[0].get("model") or "operator",
            approved_by=approved_by,
            approved_at=str(approved_at) if approved_at else None,
        )

    prov = provenance.build(
        spec, data_path, filename, merged, actions=actions_to_record
    )
    return {
        "figure": figure,
        "table": table,
        "provenance": prov,
        "params": resolved_params(spec, merged),
    }
    # NOTE: the live AI write-path is POST /ai/apply (routers/ai.py → _execute_skill_run); it stamps
    # provenance via the same provenance.stamp_ai_actions chokepoint. commit_recompute is the in-process
    # variant used by the AI-compiles-away tests.
