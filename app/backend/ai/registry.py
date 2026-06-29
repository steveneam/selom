"""Closed, declared action registry — the moat-as-data (Slice 1).

Every action the AI may propose must have an ``ActionDef`` here.  Generic loop
code reads ``ActionDef.tier`` / ``.validate`` / ``.apply``; it never branches on
an action's ``type`` string.  Adding a new action = one new entry + a new
ActionType literal member in models.py.  Removing one = the structure guard fails.

Validation handlers REUSE ``skills.contract.validate_param_ranges`` — there is
no parallel validation path in the ai/ package (the structure guard asserts this).
An AI-proposed out-of-range param is refused by the exact same rule that refuses
a human's out-of-range query string.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from ai.models import ValidationOutcome


@dataclass
class ActionDef:
    """Declared descriptor for one action type in the registry.

    ``tier``       — drives the approval rail (cosmetic = apply now / recompute = stage).
    ``validate``   — (action, ctx) → ValidationOutcome; MUST reuse skills.contract validators.
    ``apply``      — (action, ctx) → effect dict; called only after validate returns ok=True.
    ``capability`` — optional meta.selom capability key that gates this action ('' = ungated).
    ``doc``        — one-line shown in the pending-changes banner.
    """

    type: str
    tier: Literal["cosmetic", "recompute"]
    validate: Callable
    apply: Callable
    capability: str = ""
    doc: str = ""


# ---------------------------------------------------------------------------
# JSON-pointer helper (RFC 6901 subset) — used by cosmetic apply handlers.
# ---------------------------------------------------------------------------

def _set_pointer(doc: dict, path: str, value) -> dict:
    """Apply one JSON-pointer write to a deep copy of ``doc``.

    Handles the two escape sequences (~0 = ~, ~1 = /) and traverses both dicts
    and lists.  Raises ``KeyError`` for an un-traversable intermediate segment so
    the validate handler can surface a clean ``missing_column_op`` gap.
    """
    out = copy.deepcopy(doc)
    parts = [p.replace("~1", "/").replace("~0", "~") for p in path.split("/") if p]
    node = out
    for part in parts[:-1]:
        if isinstance(node, dict):
            node = node.setdefault(part, {})
        elif isinstance(node, list):
            node = node[int(part)]
        else:
            raise KeyError(f"Cannot traverse into {type(node).__name__!r} at {part!r}")
    if not parts:
        return out
    last = parts[-1]
    if isinstance(node, dict):
        node[last] = value
    elif isinstance(node, list):
        node[int(last)] = value
    else:
        raise KeyError(f"Cannot set on {type(node).__name__!r}")
    return out


# ---------------------------------------------------------------------------
# Cosmetic-path allowlist (gauntlet finding 2026-06-29) — cosmetic actions are visual-only.
# ---------------------------------------------------------------------------

# A "cosmetic" action (restyle_figure/relabel) is applied IMMEDIATELY client-side via JSON-Patch with
# no recompute and no provenance entry of its own. So its JSON-pointer must NEVER reach plotted data
# (/data/<i>/<array>) or the meta.selom capability contract (/layout/meta/...): either would let an
# AI-chosen number become the displayed figure with zero engine involvement — defeating "AI compiles
# away" and feeding a non-engine number into the figure. To CHANGE data, the AI must use a recompute
# action (set_param/add_filter), which is staged + recorded in provenance params.
_COSMETIC_TRACE_KEYS = frozenset({
    "marker", "line", "name", "opacity", "mode", "showlegend", "hoverinfo", "hovertemplate",
    "textposition", "textfont", "textangle", "fill", "fillcolor", "colorscale", "showscale",
    "colorbar", "orientation", "width", "color", "size", "symbol",
})


def _is_cosmetic_safe_path(path: str) -> bool:
    """True iff a cosmetic JSON-pointer is purely presentational.

    Allowed: ``/layout/...`` style (but NOT ``/layout/meta`` — the selom contract), and
    ``/data/<i>/<key>/...`` where ``<key>`` is a trace PRESENTATION key. Rejected: ``/data`` or
    ``/data/<i>`` (whole-array / whole-trace overwrite), any ``/data/<i>/<data-array>`` (x/y/z/
    values/labels/customdata/text…), and anything outside layout/data.
    """
    parts = [p.replace("~1", "/").replace("~0", "~") for p in path.split("/") if p]
    if not parts:
        return False
    if parts[0] == "layout":
        return not (len(parts) >= 2 and parts[1] == "meta")
    if parts[0] == "data":
        return len(parts) >= 3 and parts[2] in _COSMETIC_TRACE_KEYS
    return False


# ---------------------------------------------------------------------------
# Shared gap-builder (avoids repeating the import in every handler).
# ---------------------------------------------------------------------------

def _make_gap(action, ctx, unmet: str):
    """Build a CapabilityGap for one rejected action."""
    from ai.models import CapabilityGap
    from ai.gaps import context_hash

    return CapabilityGap(
        stage=ctx.stage,
        intent=action.type,
        unmet=unmet,
        attempted={
            "type": action.type,
            "target": action.target,
            "payload": action.payload,
        },
        context_hash=context_hash(ctx.stage, action.type, unmet, ctx.skill_id),
        skill_id=ctx.skill_id,
    )


# ---------------------------------------------------------------------------
# Validate + apply handlers (one pair per action type).
# ---------------------------------------------------------------------------

def _validate_set_param(action, ctx) -> "ValidationOutcome":
    """Validate a set_param action against the live skill param_spec.

    Reuses ``validate_param_ranges`` from skills.contract — no parallel path.
    If the param is unknown → gap(param_not_in_spec).
    If the value is out-of-range → gap(validation_blocked) — a coherent but
    blocked attempt; recorded so the owner can tighten or widen the spec.
    """
    from skills.contract import load_skill, validate_param_ranges
    from ai.models import ValidationOutcome

    if ctx.skill_id is None:
        return ValidationOutcome(ok=False, errors=["no skill in context"])

    try:
        spec = load_skill(ctx.skill_id)
    except Exception as exc:
        return ValidationOutcome(ok=False, errors=[f"could not load skill {ctx.skill_id!r}: {exc}"])

    if action.target not in spec.param_spec:
        return ValidationOutcome(
            ok=False,
            errors=[f"param {action.target!r} is not in {ctx.skill_id!r} param_spec"],
            gap=_make_gap(action, ctx, "param_not_in_spec"),
        )

    if "value" not in action.payload:
        return ValidationOutcome(ok=False, errors=["set_param payload must contain 'value'"])

    errs = validate_param_ranges(spec, {action.target: action.payload.get("value")})
    if errs:
        return ValidationOutcome(
            ok=False, errors=errs,
            gap=_make_gap(action, ctx, "validation_blocked"),
        )

    return ValidationOutcome(ok=True)


def _apply_set_param(action, ctx) -> dict:
    return {"params": {action.target: action.payload["value"]}}


def _validate_add_filter(action, ctx) -> "ValidationOutcome":
    """A filter is expressed as a param (target=param name, payload value).

    Uses the same validation path as set_param; the only distinction is the
    gap code: unknown target → unsupported_filter rather than param_not_in_spec,
    signalling the backlog category more precisely.
    """
    from skills.contract import load_skill, validate_param_ranges
    from ai.models import ValidationOutcome

    if ctx.skill_id is None:
        return ValidationOutcome(ok=False, errors=["no skill in context"])

    try:
        spec = load_skill(ctx.skill_id)
    except Exception as exc:
        return ValidationOutcome(ok=False, errors=[f"could not load skill {ctx.skill_id!r}: {exc}"])

    if action.target not in spec.param_spec:
        return ValidationOutcome(
            ok=False,
            errors=[f"filter target {action.target!r} is not a param of {ctx.skill_id!r}"],
            gap=_make_gap(action, ctx, "unsupported_filter"),
        )

    if "value" not in action.payload:
        return ValidationOutcome(ok=False, errors=["filter payload must contain 'value'"])

    errs = validate_param_ranges(spec, {action.target: action.payload.get("value")})
    if errs:
        return ValidationOutcome(
            ok=False, errors=errs,
            gap=_make_gap(action, ctx, "validation_blocked"),
        )

    return ValidationOutcome(ok=True)


def _apply_add_filter(action, ctx) -> dict:
    return {"params": {action.target: action.payload["value"]}}


def _validate_remove_filter(action, ctx) -> "ValidationOutcome":
    """Remove/reset a filter — target must be a real param (to know its default)."""
    from skills.contract import load_skill
    from ai.models import ValidationOutcome

    if ctx.skill_id is None:
        return ValidationOutcome(ok=False, errors=["no skill in context"])

    try:
        spec = load_skill(ctx.skill_id)
    except Exception as exc:
        return ValidationOutcome(ok=False, errors=[f"could not load skill {ctx.skill_id!r}: {exc}"])

    if action.target not in spec.param_spec:
        return ValidationOutcome(
            ok=False,
            errors=[f"filter target {action.target!r} is not a param of {ctx.skill_id!r}"],
            gap=_make_gap(action, ctx, "unsupported_filter"),
        )

    return ValidationOutcome(ok=True)


def _apply_remove_filter(action, ctx) -> dict:
    """Reset the param to its skill-declared default."""
    from skills.contract import load_skill
    spec = load_skill(ctx.skill_id)
    default = spec.param_spec[action.target]["default"]
    return {"params": {action.target: default}}


def _validate_cosmetic(action, ctx) -> "ValidationOutcome":
    """Shared validator for restyle_figure and relabel.

    Payload must carry ``{"path": "/...", "value": <any>}``.  If the figure_spec
    is available and the parent pointer doesn't resolve, a missing_column_op gap
    is emitted so the owner knows the path vocabulary is stale.
    """
    from ai.models import ValidationOutcome

    payload = action.payload
    if "path" not in payload or "value" not in payload:
        return ValidationOutcome(
            ok=False, errors=["payload must contain 'path' and 'value' keys"]
        )
    path = payload.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        return ValidationOutcome(
            ok=False, errors=["payload 'path' must be a string starting with '/'"]
        )

    # Visual-only boundary: a cosmetic pointer may not touch plotted data or the meta.selom contract.
    if not _is_cosmetic_safe_path(path):
        return ValidationOutcome(
            ok=False,
            errors=[f"cosmetic actions may only restyle presentation; {path!r} targets plotted data "
                    f"or the meta.selom contract — use a recompute action (set_param/add_filter) to "
                    f"change data"],
        )

    # Check parent traversal in figure_spec when available.
    if ctx.figure_spec is not None:
        parts = [p.replace("~1", "/").replace("~0", "~") for p in path.split("/") if p]
        node = ctx.figure_spec
        for part in parts[:-1]:
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]  # traverse a trace index (matches _set_pointer)
            else:
                return ValidationOutcome(
                    ok=False,
                    errors=[f"path {path!r} parent does not resolve in figure_spec"],
                    gap=_make_gap(action, ctx, "missing_column_op"),
                )

    return ValidationOutcome(ok=True)


def _apply_cosmetic(action, ctx) -> dict:
    """Apply a JSON-pointer write to a copy of the current figure_spec.

    Returns the JSON-Patch record (``op=replace``) alongside the mutated spec —
    the FE uses the patch for undo, the spec for immediate re-render.
    """
    path = action.payload["path"]
    value = action.payload["value"]
    doc = ctx.figure_spec or {}
    new_doc = _set_pointer(doc, path, value)
    return {
        "patch": [{"op": "replace", "path": path, "value": value}],
        "figure_spec": new_doc,
    }


# ---------------------------------------------------------------------------
# The registry (the moat-as-data).
# ---------------------------------------------------------------------------

ACTION_REGISTRY: dict[str, ActionDef] = {
    "set_param": ActionDef(
        type="set_param",
        tier="recompute",
        validate=_validate_set_param,
        apply=_apply_set_param,
        doc="Set a named skill parameter to a new value (requires re-run).",
    ),
    "add_filter": ActionDef(
        type="add_filter",
        tier="recompute",
        validate=_validate_add_filter,
        apply=_apply_add_filter,
        doc="Apply a filter expressed as a param value (requires re-run).",
    ),
    "remove_filter": ActionDef(
        type="remove_filter",
        tier="recompute",
        validate=_validate_remove_filter,
        apply=_apply_remove_filter,
        doc="Reset a filter param to its skill default (requires re-run).",
    ),
    "restyle_figure": ActionDef(
        type="restyle_figure",
        tier="cosmetic",
        validate=_validate_cosmetic,
        apply=_apply_cosmetic,
        doc="Update a figure layout/style property via JSON-pointer (no re-run).",
    ),
    "relabel": ActionDef(
        type="relabel",
        tier="cosmetic",
        validate=_validate_cosmetic,
        apply=_apply_cosmetic,
        doc="Relabel a figure element (axis, trace, title) via JSON-pointer (no re-run).",
    ),
}


def is_registered(action_type: str) -> bool:
    """True when the action type is in the closed registry."""
    return action_type in ACTION_REGISTRY


def get(action_type: str) -> ActionDef:
    """Return the ActionDef for a registered action type."""
    return ACTION_REGISTRY[action_type]


def tier_of(action_type: str) -> Literal["cosmetic", "recompute"]:
    """Derive the tier from the registry — never trusted from the Action payload."""
    return ACTION_REGISTRY[action_type].tier
