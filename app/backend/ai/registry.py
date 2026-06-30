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
# S3 — ingest-stage handlers (set_profile / set_design / map_columns / apply_cleaning_step).
#
# Engine-surface investigation findings (2026-06-29):
#   set_profile      — HOOK EXISTS: profile_data(bundle, override=<code>) in engine/cleaning.py.
#                      Effect delta carries _profile_override for the run path (S5 wires it).
#   set_design       — PARTIAL HOOK: Design model + _design_path reserved-key exist.
#                      Effect delta stages design fields as params; S5 wires to run path.
#   map_columns      — WIRED (P1 ingest hook): engine.columns column-override; effect delta
#                      {_column_override: {role: column}} honoured at D1/D2/the runner + recorded.
#   apply_cleaning_step — WIRED (P1 ingest hook, param-backed): a step in engine.cleaning.STEP_PARAM
#                      (normalize→normalize) compiles to a set_param effect; non-backed step → gap.
# ---------------------------------------------------------------------------

def _validate_set_profile(action, ctx) -> "ValidationOutcome":
    """Resolve an ambiguous DataProfile to a specific modality code.

    Reuses the engine's Kind constants (engine.models.ALL_KINDS) and the ERG profile
    code (engine.cleaning.ERG) — no parallel taxonomy.  If the caller populates
    ``ctx.capability_surface["candidates"]``, codes from the live DataProfile are also
    accepted (strongest validation; falls back to the full-vocab check gracefully).
    Unknown code → gap(validation_blocked) so the owner sees which codes the AI proposes.
    """
    from engine.cleaning import ERG
    from engine.models import ALL_KINDS
    from ai.models import ValidationOutcome

    if "value" not in action.payload:
        return ValidationOutcome(ok=False, errors=["set_profile payload must contain 'value'"])

    code = action.payload["value"]
    valid_codes: set[str] = set(ALL_KINDS) | {ERG}

    # If the caller passed the DataProfile's candidates via capability_surface, accept those too.
    surface = ctx.capability_surface or {}
    for cand in surface.get("candidates", []):
        if isinstance(cand, dict) and "code" in cand:
            valid_codes.add(cand["code"])

    if code not in valid_codes:
        return ValidationOutcome(
            ok=False,
            errors=[f"{code!r} is not a recognised data-type code; valid: {sorted(valid_codes)}"],
            gap=_make_gap(action, ctx, "validation_blocked"),
        )

    return ValidationOutcome(ok=True)


def _apply_set_profile(action, ctx) -> dict:
    """Stage the profile override — same key that profile_data(override=...) already accepts."""
    return {"params": {"_profile_override": action.payload["value"]}}


def _validate_set_design(action, ctx) -> "ValidationOutcome":
    """Set the experimental design (condition/batch columns) before a skill run.

    Column-existence check runs only when ``ctx.data_columns`` is provided; if the
    caller omits it the check is skipped rather than blocking (fail-soft, not false-
    negative).  Missing 'condition' key in the payload is always an error.
    """
    from ai.models import ValidationOutcome

    if "condition" not in action.payload:
        return ValidationOutcome(ok=False, errors=["set_design payload must contain 'condition'"])

    cols = ctx.data_columns
    if cols is not None:
        condition = action.payload["condition"]
        if condition not in cols:
            return ValidationOutcome(
                ok=False,
                errors=[f"condition column {condition!r} not found in data; available: {cols}"],
                gap=_make_gap(action, ctx, "validation_blocked"),
            )
        batch = action.payload.get("batch")
        if batch and batch not in cols:
            return ValidationOutcome(
                ok=False,
                errors=[f"batch column {batch!r} not found in data; available: {cols}"],
                gap=_make_gap(action, ctx, "validation_blocked"),
            )

    return ValidationOutcome(ok=True)


def _apply_set_design(action, ctx) -> dict:
    """Stage the design fields as params — the run path picks them up at commit time."""
    delta: dict = {"condition": action.payload["condition"]}
    for key in ("control", "treatment", "batch"):
        if key in action.payload:
            delta[key] = action.payload[key]
    return {"params": delta}


def _validate_map_columns(action, ctx) -> "ValidationOutcome":
    """Map a non-standard-named column to a DE-figure role (logFC / pval / gene).

    WIRED (P1 ingest hook): the engine now has a column-override (engine.columns) — a {role: column}
    map that wins over synonym auto-detection at every resolution site (D1 schema / D2 usability / the
    volcano runner).  The payload IS the map.  Validation: each role must be overridable (the set is
    disjoint from set_design's condition/batch); when ctx.data_columns is provided, each mapped column
    must EXIST in the data (else gap(validation_blocked), mirroring set_design — override-only, never
    fabricate); an unknown role is a clean rejection (malformed, no gap).
    """
    from engine.columns import OVERRIDABLE_ROLES
    from ai.models import ValidationOutcome

    mapping = dict(action.payload or {})
    if not mapping:
        return ValidationOutcome(
            ok=False,
            errors=["map_columns payload must be a {role: column} map (roles: "
                    + ", ".join(sorted(OVERRIDABLE_ROLES)) + ")"],
        )
    unknown = [r for r in mapping if r not in OVERRIDABLE_ROLES]
    if unknown:
        return ValidationOutcome(
            ok=False,
            errors=[f"unknown role(s) {unknown}; overridable roles: {sorted(OVERRIDABLE_ROLES)}"],
        )
    cols = ctx.data_columns
    if cols is not None:
        for role, col in mapping.items():
            if col not in cols:
                return ValidationOutcome(
                    ok=False,
                    errors=[f"column {col!r} for role {role!r} not found in data; available: {cols}"],
                    gap=_make_gap(action, ctx, "validation_blocked"),
                )
    return ValidationOutcome(ok=True)


def _apply_map_columns(action, ctx) -> dict:  # noqa: ARG001 — ctx unused (the map is the payload)
    """Stage the column-override — the run path reads params['_column_override'] + records it, so a
    re-run reproduces the figure with no AI ("AI compiles away" extended to ingest overrides)."""
    return {"params": {"_column_override": dict(action.payload)}}


def _validate_apply_cleaning_step(action, ctx) -> "ValidationOutcome":
    """Toggle a cleaning step on/off by setting its controlling skill param (param-backed).

    WIRED (P1 ingest hook): a step in engine.cleaning.STEP_PARAM (e.g. 'normalize' → the 'normalize'
    param) compiles to a set_param effect, REUSING skills.contract.validate_param_ranges (no parallel
    path) so the figure genuinely changes + is recorded.  A non-param-backed (hard-coded) step, no
    active skill, or a skill that lacks that param → an honest gap(validation_blocked), so the backlog
    captures demand to wire more steps.  Payload: {step_id, enabled} (enabled defaults True).
    """
    from engine.cleaning import STEP_PARAM
    from skills.contract import load_skill, validate_param_ranges
    from ai.models import ValidationOutcome

    step_id = action.payload.get("step_id")
    if not step_id:
        return ValidationOutcome(ok=False, errors=["apply_cleaning_step payload must contain 'step_id'"])
    enabled = bool(action.payload.get("enabled", True))

    param = STEP_PARAM.get(step_id)
    if param is None:
        return ValidationOutcome(
            ok=False,
            errors=[f"cleaning step {step_id!r} has no skip hook yet (it is hard-coded, not "
                    f"param-backed); togglable steps: {sorted(STEP_PARAM)}"],
            gap=_make_gap(action, ctx, "validation_blocked"),
        )
    if ctx.skill_id is None:
        return ValidationOutcome(
            ok=False,
            errors=["toggling a cleaning step needs an active skill (its param controls the step)"],
            gap=_make_gap(action, ctx, "validation_blocked"),
        )
    try:
        spec = load_skill(ctx.skill_id)
    except Exception as exc:
        return ValidationOutcome(ok=False, errors=[f"could not load skill {ctx.skill_id!r}: {exc}"])
    if param not in spec.param_spec:
        return ValidationOutcome(
            ok=False,
            errors=[f"{ctx.skill_id!r} has no {param!r} step to toggle"],
            gap=_make_gap(action, ctx, "validation_blocked"),
        )
    errs = validate_param_ranges(spec, {param: enabled})
    if errs:
        return ValidationOutcome(ok=False, errors=errs, gap=_make_gap(action, ctx, "validation_blocked"))
    return ValidationOutcome(ok=True)


def _apply_apply_cleaning_step(action, ctx) -> dict:  # noqa: ARG001 — ctx unused
    """Stage the controlling skill param (disable = param False) — a real recompute param, so it is
    validated, recorded, and reproduced by the existing machinery (no reserved key needed)."""
    from engine.cleaning import STEP_PARAM
    step_id = action.payload["step_id"]
    enabled = bool(action.payload.get("enabled", True))
    return {"params": {STEP_PARAM[step_id]: enabled}}


# ---------------------------------------------------------------------------
# S4 — P3 route action: select_skill.
#
# Engine-surface: engine.compat.fit(skill_id, FileAssessment) gates on a *certain*
# payload-class mismatch (table vs matrix) — the honesty rule.  When ctx.data_fit is
# provided, a FileAssessment is reconstructed from its fields (kind, quality, qc_ok,
# columns via ctx.data_columns) and the target skill is scored.  A DataFit.gated=True
# result (compatible=False) → honest no_fitting_skill gap (recorded) so the backlog
# captures demand for compatible alternatives.  When ctx.data_fit is None the compat
# check is skipped (fail-soft: we don't know the data, so we can't gate).
# ---------------------------------------------------------------------------

def _validate_select_skill(action, ctx) -> "ValidationOutcome":
    """Propose switching the active skill for the current data (P3 route action).

    Two-layer validation:
      1. Registry existence — the target skill must be installed.
      2. Compat check (when ctx.data_fit is available) — engine.compat.fit scores
         the current data against the target skill.  A certain mismatch (gated=True)
         emits a no_fitting_skill gap rather than a hard error, so the backlog captures
         demand for incompatible-but-requested skill switches.

    Reuses engine.compat.fit — no parallel validation path.
    """
    from ai.models import ValidationOutcome

    # Resolve the target skill from payload or target field.
    target_skill = action.payload.get("skill_id") or action.target
    if not target_skill:
        return ValidationOutcome(
            ok=False, errors=["select_skill payload must contain 'skill_id'"]
        )

    # Layer 1 — registry existence.
    try:
        from skills.registry import list_skill_ids
        if target_skill not in set(list_skill_ids()):
            return ValidationOutcome(
                ok=False,
                errors=[f"skill {target_skill!r} is not in the registry"],
                gap=_make_gap(action, ctx, "no_fitting_skill"),
            )
    except Exception as exc:
        return ValidationOutcome(
            ok=False, errors=[f"could not check skill registry: {exc}"]
        )

    # Layer 2 — compat check (skip when data_fit is absent — fail-soft).
    if ctx.data_fit:
        try:
            from engine.compat import FileAssessment
            from engine.compat import fit as compat_fit

            # Real numeric-column count when the caller measured it; otherwise len(columns) so the
            # gsea numeric sub-check (≥1 numeric col) is SATISFIED, never falsely tripped from
            # missing info (don't gate on what we didn't measure). The over-count can only ever
            # satisfy the floor, never invent a miss — the honest direction. _check_schema is shared
            # with the D1 run gate, so we fix the caller's assessment, not the shared validator.
            n_numeric = ctx.data_fit.get("n_numeric_cols")
            columns = ctx.data_columns or []
            fa = FileAssessment(
                path=ctx.data_fit.get("path", ""),
                filename=ctx.data_fit.get("filename", ""),
                loadable=True,
                kind=ctx.data_fit.get("kind", "unknown"),
                # Use score as a proxy for quality (same 0-100 scale, reasonable approx).
                quality=ctx.data_fit.get("score", 80),
                qc_ok=ctx.data_fit.get("qc_ok", True),
                columns=columns,
                n_numeric_cols=n_numeric if n_numeric is not None else len(columns),
            )
            result = compat_fit(target_skill, fa)
            if result.gated:
                return ValidationOutcome(
                    ok=False,
                    errors=[
                        f"skill {target_skill!r} is incompatible with the current data: "
                        f"{result.reason}"
                    ],
                    gap=_make_gap(action, ctx, "no_fitting_skill"),
                )
        except Exception:
            pass  # compat check failed — degrade-clean, don't block the action

    return ValidationOutcome(ok=True)


def _apply_select_skill(action, ctx) -> dict:
    """Stage the skill switch — the run path picks it up at commit time."""
    target_skill = action.payload.get("skill_id") or action.target
    return {"params": {"_selected_skill": target_skill}}


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
    # S3 — ingest-stage helpers
    "set_profile": ActionDef(
        type="set_profile",
        tier="recompute",
        validate=_validate_set_profile,
        apply=_apply_set_profile,
        doc="Resolve an ambiguous data-type profile to a specific modality (requires re-ingest).",
    ),
    "set_design": ActionDef(
        type="set_design",
        tier="recompute",
        validate=_validate_set_design,
        apply=_apply_set_design,
        doc="Set the experimental grouping (condition/batch columns) before a skill run.",
    ),
    "map_columns": ActionDef(
        type="map_columns",
        tier="recompute",
        validate=_validate_map_columns,
        apply=_apply_map_columns,
        doc="Map a non-standard-named column to a DE role (logFC/pval/gene) (requires re-run).",
    ),
    "apply_cleaning_step": ActionDef(
        type="apply_cleaning_step",
        tier="recompute",
        validate=_validate_apply_cleaning_step,
        apply=_apply_apply_cleaning_step,
        doc="Toggle a cleaning step on/off via its controlling skill param (requires re-run).",
    ),
    # S4 — P3 route action
    "select_skill": ActionDef(
        type="select_skill",
        tier="recompute",
        validate=_validate_select_skill,
        apply=_apply_select_skill,
        doc="Switch the active skill to a compatible alternative (requires re-run).",
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
