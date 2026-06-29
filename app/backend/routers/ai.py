"""AI Action Gateway router — POST /ai/propose, POST /ai/apply (Slice 1 + Slice 2).

The gateway seam is a module-level function so Slice 2 can swap in the live
PydanticAIGateway by overriding ``get_action_gateway`` without touching the
handlers.  The default is ``NullActionGateway`` — with it, every request
returns an empty plan, leaving all existing behaviour unchanged (zero-regression
default).

Execution invariant: ``POST /ai/apply`` routes approved AI actions through the
EXACT same ``_execute_skill_run`` body as human-initiated ``POST /skills/{id}/run``
— the same QC / D1 / D2 gates, the same provenance builder, the same table
synthesis.  No second gated path exists.  AI assistance is recorded via the
``ai_actions`` provenance argument; the result is byte-reproducible from the
recorded ``provenance.params`` with zero AI in the loop (AI compiles away).
"""

from __future__ import annotations

import json as _json
import os
from typing import Literal

from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ai.gateway import ActionGateway, NullActionGateway
from ai.loop import run_helper_turn
from ai.models import ActionContext
from config import settings
from routers._run import _execute_skill_run, _save_upload, _stringify_params

router = APIRouter()


def get_action_gateway() -> ActionGateway:
    """Gateway provider seam.

    Returns the live ``PydanticAIGateway`` when ``SELOM_AI_GATEWAY=live`` AND
    ``ANTHROPIC_API_KEY`` is set; otherwise falls back to ``NullActionGateway``
    (the zero-regression default).  Mirrors the ``OperatorVisionGateway`` seam
    in ``extract/vision.py``: flipping the env var + key turns the live gateway
    on without touching any handler code.
    """
    if (
        settings.ai_gateway.strip().lower() == "live"
        and os.environ.get("ANTHROPIC_API_KEY")
    ):
        from ai.live.pydantic_gateway import PydanticAIGateway  # lazy import

        return PydanticAIGateway(
            token_budget=settings.ai_token_budget,
            timeout_s=settings.ai_timeout_s,
        )
    return NullActionGateway()


# ---------------------------------------------------------------------------
# POST /ai/propose
# ---------------------------------------------------------------------------

class ProposeRequest(BaseModel):
    """Inbound context for an AI helper proposal.

    ``data_fit`` is intentionally absent — it is derived server-side from the
    engine, never trusted from the client, so the ActionContext is populated with
    ``data_fit=None`` here (Slice 2 adds server-side derivation when the dataset
    is known).  Actions are NOT accepted from this payload; the gateway proposes
    them from the goal + context alone.
    """

    stage: str = "analyze"
    skill_id: str | None = None
    params: dict = {}
    goal: str = ""
    figure_spec: dict | None = None
    capability_surface: dict | None = None


@router.post("/ai/propose")
def propose(req: ProposeRequest):
    """Return an AI-proposed ActionPlan for the given goal and context.

    With the default NullActionGateway this always returns an empty plan — the
    correct zero-regression baseline.  Set SELOM_AI_GATEWAY=live + ANTHROPIC_API_KEY
    to wire the live PydanticAIGateway.
    """
    ctx = ActionContext(
        stage=req.stage,
        skill_id=req.skill_id,
        params=req.params,
        figure_spec=req.figure_spec,
        capability_surface=req.capability_surface,
        data_fit=None,
    )
    turn = run_helper_turn(ctx, req.goal, get_action_gateway())
    return turn.model_dump()


# ---------------------------------------------------------------------------
# POST /ai/apply
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# GET /ai/gaps — review-only capability-gap backlog
# ---------------------------------------------------------------------------

@router.get("/ai/gaps")
def get_gaps():
    """Return the ranked, categorized capability-gap backlog.

    Each entry carries context_hash, stage, unmet, category, skill_id, count,
    and sample_attempt (the last attempted payload that produced this gap).

    **Review-only** — this endpoint never mutates the action registry, relaxes a
    validation rule, or widens a param_spec (the integrity boundary).  It is the
    surface the retro workflow and the FE backlog view consume.
    """
    from ai import gaps as g

    entries = g.list_gaps()
    return [
        {
            "context_hash": entry["gap"].context_hash,
            "stage": entry["gap"].stage,
            "unmet": entry["gap"].unmet,
            "category": entry["category"],
            "skill_id": entry["gap"].skill_id,
            "count": entry["count"],
            "sample_attempt": entry["gap"].attempted,
        }
        for entry in entries
    ]


# ---------------------------------------------------------------------------
# POST /ai/explain — informational helpers (NOT mutations)
#
# explain_score and propose_sweep produce explanatory text grounded in
# deterministic artifacts (the scorecard; the SOP sweep space).  They are NOT
# mutations: they do not go through the action registry or apply_plan.  The
# gateway translate is used for structured output; the Null gateway falls back
# to a short deterministic summary of the passed data (degrade-clean).
#
# DEFERRED: methods/legend polish (optional AI over the deterministic litsynth /
# companions.methods; lower priority than explain_score + propose_sweep).
# ---------------------------------------------------------------------------

class ExplainRequest(BaseModel):
    """Inbound request for an informational AI helper.

    ``request`` selects which helper to invoke.  ``scorecard`` and
    ``sweep_space`` are the deterministic artifacts that ground the explanation —
    the AI is instructed never to fabricate values outside them.

    ``explain_score``  — plain-language explanation of a reproducibility scorecard
                         grounded in the scorecard fields (score, tier, panels).
    ``propose_sweep``  — suggest which parameters to sweep, grounded in the
                         declared sweep-space dict (param → range/options).
    """

    request: Literal["explain_score", "propose_sweep"]
    stage: str = "grade"
    skill_id: str | None = None
    goal: str = ""
    scorecard: dict | None = None
    sweep_space: dict | None = None


@router.post("/ai/explain")
def explain(req: ExplainRequest):
    """Return AI-generated (or deterministic) explanatory text for a grade/output helper.

    Uses the active gateway's ``explain`` method — the Null gateway returns a
    deterministic text built from the supplied deterministic data (scorecard /
    sweep-space); the live gateway returns AI-generated text grounded in the same
    data.  Either way the call degrades clean: no raises, no fabricated values.

    This is an **informational path** — it never goes through ``apply_plan``, never
    stages a param, and never records a gap.  Not in ACTION_TYPES.
    """
    gw = get_action_gateway()
    data: dict = {}
    if req.scorecard:
        data["scorecard"] = req.scorecard
    if req.sweep_space:
        data["sweep_space"] = req.sweep_space

    text = gw.explain(req.request, data, req.goal)
    return {
        "request": req.request,
        "text": text,
        "source": "deterministic" if isinstance(gw, NullActionGateway) else "ai",
    }


# ---------------------------------------------------------------------------
# POST /ai/apply
# ---------------------------------------------------------------------------

@router.post("/ai/apply")
async def apply_approved(
    matrix: UploadFile,
    skill_id: str = Form(...),
    goal: str = Form(""),
    override: bool = Form(False),
    params: str = Form("{}"),
    ai_actions: str = Form("[]"),
):
    """Execute user-approved AI actions through the same gated run path as human runs.

    Accepts the user-approved final params (base + staged delta already merged
    client-side) and the actor-tagged ``provenance_actions`` from the ``HelperTurn``
    (with ``approved_by`` / ``approved_at`` stamped by the client).  Passes them
    through the EXACT same ``_execute_skill_run`` body as ``POST /skills/{id}/run``:
    QC gate → D1 data-contract gate → D2 frame-schema gate → skill execution →
    table synthesis → provenance builder.  No second gated path.

    The provenance bundle's ``actions`` field carries the actor-tagged log so the
    result is auditable.  Re-running from ``provenance.params`` with no gateway
    reproduces the figure byte-for-byte (AI compiles away invariant).

    Parameters (multipart form)
    ---------------------------
    matrix:
        The data file (same as ``POST /skills/{id}/run``).
    skill_id:
        The skill to run (must be in the registry).
    goal:
        The user's NL goal (recorded in provenance).
    override:
        Pass QC / data-contract gates anyway (same escape hatch as human runs).
    params:
        JSON-encoded dict of the FINAL approved params (base merged with the
        user-approved staged delta).
    ai_actions:
        JSON-encoded list of approved ``provenance_actions`` from the HelperTurn
        (each entry: action_id, actor, type, target, prompt, model,
        approved_by, approved_at).
    """
    # S5: harden actor-tag against client forgery (FE posts staged delta separately; backend re-derives the tag). Backlog.
    from skills.registry import list_skill_ids

    if skill_id not in set(list_skill_ids()):
        raise HTTPException(status_code=404, detail=f"unknown skill {skill_id!r}")

    try:
        params_dict: dict = _json.loads(params)
    except (ValueError, TypeError):
        params_dict = {}

    try:
        actions_list: list[dict] = _json.loads(ai_actions)
    except (ValueError, TypeError):
        actions_list = []

    if not actions_list:
        raise HTTPException(
            status_code=400,
            detail="/ai/apply requires a non-empty ai_actions log (the approved, actor-tagged actions)",
        )

    for entry in actions_list:
        if (
            not isinstance(entry, dict)
            or entry.get("actor") != "ai"
            or not entry.get("type")
            or "target" not in entry
        ):
            raise HTTPException(
                status_code=400,
                detail="malformed ai_actions entry: each must carry actor='ai', type, target",
            )

    path = _save_upload(matrix)
    return await _execute_skill_run(
        skill_id,
        path,
        matrix.filename,
        _stringify_params(params_dict),
        override,
        None,
        ai_actions=actions_list,
    )
