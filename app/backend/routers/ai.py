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

    path = _save_upload(matrix)
    return await _execute_skill_run(
        skill_id,
        path,
        matrix.filename,
        _stringify_params(params_dict),
        override,
        None,
        ai_actions=actions_list if actions_list else None,
    )
