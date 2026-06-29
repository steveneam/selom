"""Pydantic v2 wire types for the AI Action Gateway (Slice 1).

All types are plain Pydantic BaseModels so they cross the HTTP boundary cleanly
and carry no AI dependency — the probabilistic shell is pluggable behind the
deterministic core's validation.
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

# The closed, declared action vocabulary.  Every entry must have a matching
# ActionDef in ai.registry — the structure guard enforces this pair.
# Tier assignment is ALWAYS derived from the registry, never trusted from input.
ACTION_TYPES = (
    "set_param",
    "add_filter",
    "remove_filter",
    "restyle_figure",
    "relabel",
    # S3 — ingest-stage helpers (P1 surface)
    "set_profile",
    "set_design",
    "map_columns",
    "apply_cleaning_step",
    # S4 — P3 route action
    "select_skill",
)
ActionType = Literal[
    "set_param",
    "add_filter",
    "remove_filter",
    "restyle_figure",
    "relabel",
    # S3 — ingest-stage helpers (P1 surface)
    "set_profile",
    "set_design",
    "map_columns",
    "apply_cleaning_step",
    # S4 — P3 route action
    "select_skill",
]


class Action(BaseModel):
    """One atomic, typed mutation proposal from the AI gateway.

    ``id`` is stable across a turn for provenance + revert lookup.
    ``tier`` is NEVER sourced from this field — it is always derived from the
    registry so the AI cannot misclassify a recompute action as cosmetic.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    type: ActionType
    target: str = ""
    payload: dict = {}
    rationale: str = ""


class ActionPlan(BaseModel):
    """A gateway's response: the NL goal and the ordered list of proposed actions.

    ``notes`` carries the AI's explanation shown in the pending-changes banner.
    An empty ``actions`` list is valid (NullActionGateway) — the zero-regression default.
    """

    goal: str
    actions: list[Action] = []
    notes: str = ""


class ActionContext(BaseModel):
    """Stateless context passed per request — the AI holds no session state.

    ``stage`` locates the action in the engine spine; ``skill_id`` scopes param
    validation; ``figure_spec`` is read-only to the AI (it proposes a patch, never
    a replacement).  ``data_fit`` and ``capability_surface`` gate certain actions.
    ``data_columns`` carries the bundle's column names for ingest-stage column checks
    (set_design); left ``None`` when the caller cannot provide them, which skips the
    check rather than blocking the action.
    """

    stage: Literal["ingest", "join", "route", "analyze", "grade", "output"] = "analyze"
    skill_id: str | None = None
    params: dict = {}
    figure_spec: dict | None = None
    capability_surface: dict | None = None
    data_fit: dict | None = None
    data_columns: list[str] | None = None


class CapabilityGap(BaseModel):
    """A coherent but unfulfillable action — the self-improving loop's signal.

    Gaps aggregate by ``context_hash`` across independent sessions into a
    frequency-ranked backlog.  They are SURFACED FOR REVIEW ONLY — the gap log
    never auto-adds a registry action, auto-relaxes a validator, or widens a
    param_spec (integrity boundary — see spec.md §Design/self-improving loop).
    """

    stage: str
    intent: str
    unmet: Literal[
        "no_such_action",
        "param_not_in_spec",
        "unsupported_filter",
        "no_fitting_skill",
        "validation_blocked",
        "missing_column_op",
    ]
    attempted: dict = {}
    context_hash: str
    skill_id: str | None = None


class ValidationOutcome(BaseModel):
    """Result of validate_action — drives the apply/stage/gap/reject branch."""

    ok: bool
    errors: list[str] = []
    gap: CapabilityGap | None = None


class ActionResult(BaseModel):
    """Per-action outcome after execute.apply_plan processes one Action.

    ``tier`` is the registry-derived tier (never trusted from the Action).
    ``status`` meanings:
      applied  — cosmetic action applied immediately (undoable via JSON-Patch).
      staged   — recompute action queued in the pending-changes banner.
      rejected — validation refused it (validation_blocked or malformed payload).
      gap      — capability doesn't exist in the registry (backlog candidate).
    """

    action_id: str
    type: str
    target: str
    tier: Literal["cosmetic", "recompute"]
    status: Literal["applied", "staged", "rejected", "gap"]
    effect: dict = {}
    errors: list[str] = []
    gap: CapabilityGap | None = None


class HelperTurn(BaseModel):
    """Full outcome of one propose→validate→(stage|apply) pass.

    ``staged_params`` accumulates every recompute action's merged param delta —
    the queue that feeds commit_recompute on user approval.
    ``figure_spec`` reflects all cosmetic patches applied in this turn.
    ``provenance_actions`` records actor=ai entries for every applied/staged action.
    """

    goal: str
    plan: ActionPlan
    results: list[ActionResult] = []
    staged_params: dict = {}
    figure_spec: dict | None = None
    gaps: list[CapabilityGap] = []
    provenance_actions: list[dict] = []
