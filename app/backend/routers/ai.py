"""AI Action Gateway router — POST /ai/propose (Slice 1).

The gateway seam is a module-level function so Slice 2 can swap in the live
PydanticAIGateway by overriding ``get_action_gateway`` without touching the
handler.  The default is ``NullActionGateway`` — with it, every request returns
an empty plan, leaving all existing behaviour unchanged (zero-regression default).

No action is applied directly from this endpoint: the router only returns a
``HelperTurn`` (the proposed + staged plan).  Cosmetic auto-applies happen
client-side via the JSON-Patch; recompute actions go through the user-approval
gate before ``commit_recompute`` runs (POST /ai/apply, Slice 2).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from ai.gateway import ActionGateway, NullActionGateway
from ai.loop import run_helper_turn
from ai.models import ActionContext

router = APIRouter()


def get_action_gateway() -> ActionGateway:
    """Gateway provider seam.  S2 overrides this to return the live PydanticAIGateway."""
    return NullActionGateway()


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
    correct zero-regression baseline.  Slice 2 wires the live gateway here.
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

# S2: POST /ai/apply wires commit_recompute to the live gateway + dataset/upload data flow
