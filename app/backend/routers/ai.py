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
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from ai.gateway import ActionGateway, NullActionGateway, _deterministic_explain, rank_sweep_space
from ai.loop import run_helper_turn
from ai.models import ActionContext
from auth import AuthContext, require_user
from companions import provenance
from config import settings
from routers._errors import RunError, unknown_skill
from routers._run import _execute_skill_run, _save_upload, _stringify_params

router = APIRouter()


def get_action_gateway() -> ActionGateway:
    """Gateway provider seam — selects the active gateway from ``SELOM_AI_GATEWAY``.

    Modes (first match wins; a mode whose credential is absent falls through to Null,
    so the call never raises and behaviour degrades clean):

    - ``gateway`` (+ ``AI_GATEWAY_API_KEY``) → ``VercelAIGateway`` — live Llama via the
      Vercel AI Gateway; the real gated-product path. Provider-agnostic (swap the model id).
    - ``operator`` → ``OperatorActionGateway.from_recordings()`` — Claude-authored recorded
      outputs, NO credit; the build/optimize default AND the canned demo engine.
    - ``live`` (+ ``ANTHROPIC_API_KEY``) → ``PydanticAIGateway`` — direct Anthropic (kept).
    - otherwise → ``NullActionGateway`` (the zero-regression deterministic default).

    Mirrors the ``OperatorVisionGateway`` seam in ``extract/vision.py``: flipping the env
    var (+ key) changes the gateway without touching any handler code.  See
    ``docs/ai-gateway-wiring/spec.md``.
    """
    mode = settings.ai_gateway.strip().lower()

    if mode == "gateway" and settings.ai_gateway_api_key:
        from ai.live.vercel_gateway import VercelAIGateway  # lazy import

        return VercelAIGateway.from_settings(settings)

    if mode == "operator":
        from ai.gateway import OperatorActionGateway  # lazy import

        return OperatorActionGateway.from_recordings(settings.ai_operator_recordings_path)

    if mode == "live" and settings.anthropic_api_key_present():
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

    Slice 2 — data-aware routing.  The client describes its data (``data_columns`` +
    ``data_kind`` + ``data_n_numeric_cols``, all sourced from ``POST /data/inspect``);
    the server still derives the fit *verdict* itself (``engine.compat.fit``, inside
    ``_validate_select_skill``) — a column list + kind is data *description*, never a
    verdict, so the honesty rule holds (the client cannot assert ``compatible``).  When
    no data context is supplied (e.g. the analyze composer), ``data_fit`` stays ``None``
    and the route-stage compat gate is skipped (fail-soft, unchanged behaviour).

    Actions are NOT accepted from this payload; the gateway proposes them from the
    goal + context alone.
    """

    stage: str = "analyze"
    skill_id: str | None = None
    params: dict = {}
    goal: str = ""
    figure_spec: dict | None = None
    capability_surface: dict | None = None
    # Slice 2 — data context for data-aware routing (the route-stage select_skill gate).
    data_columns: list[str] | None = None
    data_kind: str | None = None
    data_n_numeric_cols: int | None = None


@router.post("/ai/propose")
def propose(req: ProposeRequest):
    """Return an AI-proposed ActionPlan for the given goal and context.

    With the default NullActionGateway this always returns an empty plan — the
    correct zero-regression baseline.  Set SELOM_AI_GATEWAY=live + ANTHROPIC_API_KEY
    to wire the live PydanticAIGateway.

    Slice 2: when the request carries data context, ``ctx.data_fit`` is populated so
    the route-stage ``select_skill`` action is scored against the data
    (``_validate_select_skill`` → ``engine.compat.fit``).  ``data_fit`` here carries
    only the *description* (kind, numeric-column count) — the verdict is computed
    server-side from ``data_columns``, never trusted from the client.
    """
    data_fit: dict | None = None
    if req.data_columns is not None or req.data_kind is not None or req.data_n_numeric_cols is not None:
        data_fit = {
            "kind": req.data_kind or "unknown",
            "n_numeric_cols": req.data_n_numeric_cols,  # None ⇒ unknown (registry satisfies the numeric floor)
            # Permissive defaults — the fit VERDICT comes from compat.fit on the columns, not these.
            "score": 80,
            "qc_ok": True,
        }
    ctx = ActionContext(
        stage=req.stage,
        skill_id=req.skill_id,
        params=req.params,
        figure_spec=req.figure_spec,
        capability_surface=req.capability_surface,
        data_fit=data_fit,
        data_columns=req.data_columns,
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
    ``grade_advice``   — statistics advisory for a figure: which test / correction it
                         uses and what it assumes, grounded in the ``stats`` method
                         descriptor (skill_id + mode). Advisory only, never a mutation.
    ``draft_methods``  — polish a figure's DETERMINISTIC methods paragraph (``base_text``,
                         from ``companions.methods``) to the user's goal, preserving every
                         number / threshold / citation. The deterministic fallback IS
                         ``base_text`` verbatim, so gateway-off returns the honest draft
                         (``source="deterministic"``, no ✨) and a no-op polish stays so.
    ``draft_legend``   — the same polish over a figure's deterministic LEGEND/caption
                         (``companions.legends``); identical honesty lever (fallback = ``base_text``).
    """

    request: Literal[
        "explain_score", "propose_sweep", "grade_advice", "draft_methods", "draft_legend"
    ]
    stage: str = "grade"
    skill_id: str | None = None
    goal: str = ""
    scorecard: dict | None = None
    sweep_space: dict | None = None
    # grade_advice grounding — the figure's statistical method ({skill_id, mode}); a description, not a
    # verdict, so the honesty rule holds (the server owns the per-skill knowledge in ai.grade).
    stats: dict | None = None
    # draft_methods grounding — the figure's deterministic methods prose to polish. It is BOTH the
    # thing the live model rewrites AND the deterministic fallback (returned verbatim), so an unchanged
    # polish is honestly labelled `deterministic`. A description, not a verdict — no honesty risk.
    base_text: str | None = None


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
    if req.stats:
        data["stats"] = req.stats
    # draft_methods: the deterministic methods prose to polish. It is ALSO the deterministic fallback
    # (`_deterministic_explain` returns it verbatim), so the source-labelling comparison below stays
    # honest — a no-op polish reads `deterministic`, a real polish reads `ai`.
    if req.base_text is not None:
        data["base_text"] = req.base_text
    # skill_id rides in `data` so the operator gateway can key propose_sweep recordings on it
    # and the live gateway can ground its prose; `_deterministic_explain` ignores it, so the
    # source-labelling comparison below is unaffected.
    if req.skill_id:
        data["skill_id"] = req.skill_id

    text = gw.explain(req.request, data, req.goal)
    # Honesty: stamp `source` by what was ACTUALLY produced, NOT by the gateway class. A live
    # PydanticAIGateway degrades to the BYTE-IDENTICAL deterministic summary on timeout/error (its
    # fallback IS `_deterministic_explain`), so a class check would mislabel that fallback as "ai" —
    # and the FE ✨ "AI" badge would then claim AI produced text it didn't. Comparing against the
    # same fallback detects the degrade exactly; an identical-by-coincidence model output is labelled
    # the safe way (deterministic), never falsely AI (owner steer; gauntlet HIGH 2026-06-30).
    produced_by_ai = not isinstance(gw, NullActionGateway) and text != _deterministic_explain(
        req.request, data, req.goal
    )
    # The structured ranking is ALWAYS the deterministic one (pure data, never the gateway):
    # the live AI's prose may vary, but the picks the UI preselects stay reproducible + grounded.
    suggestions = rank_sweep_space(req.sweep_space) if req.request == "propose_sweep" else []
    return {
        "request": req.request,
        "text": text,
        "source": "ai" if produced_by_ai else "deterministic",
        "suggestions": suggestions,
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
    design: UploadFile | None = File(None),
    ctx: AuthContext = Depends(require_user),
):
    """Execute user-approved AI actions through the same gated run path as human runs.

    Accepts the user-approved final params (base + staged delta already merged
    client-side) and the approved action **delta** (``action_id`` / ``type`` /
    ``target`` / ``prompt`` — what to apply).  Passes them through the EXACT same
    ``_execute_skill_run`` body as ``POST /skills/{id}/run``: QC gate → D1
    data-contract gate → D2 frame-schema gate → skill execution → table synthesis →
    provenance builder.  No second gated path.

    **Provenance is server-controlled (NEXT#1).**  The attribution recorded in
    ``provenance.actions[]`` (``actor`` / ``model`` / ``approved_by`` /
    ``approved_at``) is NOT trusted from the request — it is re-derived here from
    the active gateway, the verified tenant (``ctx.user_id``), and the server clock
    via the one chokepoint ``provenance.stamp_ai_actions``.  A forged tag cannot
    survive.  Re-running from ``provenance.params`` with no gateway reproduces the
    figure byte-for-byte (AI compiles away invariant).

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
        JSON-encoded list of the approved action **delta** — each entry carries the
        descriptive ``{action_id, type, target, prompt}``.  Any caller-supplied
        ``actor`` / ``model`` / ``approved_by`` / ``approved_at`` is **ignored**:
        the server derives the trusted attribution itself (forgery-proof).
    """
    from skills.registry import list_skill_ids

    if skill_id not in set(list_skill_ids()):
        raise unknown_skill(skill_id)

    try:
        params_dict: dict = _json.loads(params)
    except (ValueError, TypeError):
        params_dict = {}

    try:
        actions_list: list[dict] = _json.loads(ai_actions)
    except (ValueError, TypeError):
        actions_list = []

    if not actions_list:
        raise RunError.bad_input(
            "ai_actions_empty",
            "/ai/apply requires a non-empty ai_actions log (the approved action delta).",
            fix="Approve at least one AI proposal before applying.")

    # Validate the DELTA shape only (descriptive integrity) — actor/model/approved_* are NEVER
    # required nor trusted from the caller; the server stamps them below.
    for entry in actions_list:
        if not isinstance(entry, dict) or not entry.get("type") or "target" not in entry:
            raise RunError.bad_input(
                "ai_actions_malformed",
                "malformed ai_actions entry: each must carry type and target.",
                fix="Send each approved action as {action_id, type, target, prompt}.")

    # Server-controlled provenance (NEXT#1, docs/provenance-chokepoint/spec.md): derive the trusted
    # attribution and route ONLY the stamped list to the run path — the raw `actions_list` (with any
    # forged actor/model/approved_*) never reaches provenance.build. `model` is the gateway active at
    # apply time (a propose→apply env flip would reflect the apply-time gateway — the server-trusted
    # value, strictly better than a forgeable client string; see spec "Accepted limitation").
    trusted_actions = provenance.stamp_ai_actions(
        actions_list,
        model=get_action_gateway().model_id,
        approved_by=ctx.user_id,
        approved_at=datetime.now(UTC).isoformat(),
    )

    path = _save_upload(matrix)
    # Thread the design sheet (sample→condition/time) exactly as the human /skills/{id}/run path does
    # (routers/skills.py): a design-consuming skill (deg / heatmap) re-run via the AI path MUST get it,
    # else it silently falls back to column-name inference → a DIFFERENT result, not an error. Reserved
    # param (the skill reads params["_design_path"]) + the path for the finally cleanup; kept out of
    # provenance (resolved_params strips "_"-prefixed keys), preserving "AI compiles away".
    design_path = _save_upload(design) if design is not None else None
    if design_path:
        params_dict["_design_path"] = design_path
    return await _execute_skill_run(
        skill_id,
        path,
        matrix.filename,
        _stringify_params(params_dict),
        override,
        design_path,
        ai_actions=trusted_actions,
    )
