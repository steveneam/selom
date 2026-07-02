import pathlib
import shutil

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel

from auth import AuthContext, require_user
from jobs.queue import submit
from skills._engine import to_bool
from skills.contract import load_skill, validate_param_ranges
from skills.registry import list_catalog, list_skill_ids
from storage.object_store import get_object_store

from routers._errors import RunError, param_out_of_range, unknown_skill
from routers._run import _dataset_to_temp, _execute_skill_run, _save_upload, _stringify_params
from routers.deps import _uploads_repo

router = APIRouter()


@router.get("/skills")
def list_skills():
    # Live Skill-Store registry: every on-disk skill as a SkillCatalogEntry. The FE
    # Store reads this and drops its hard-coded Verified seed (B3 — registry-driven).
    return list_catalog()


@router.get("/skills/{skill_id}")
def describe(skill_id: str):
    return load_skill(skill_id).model_dump()        # registry-driven UI reads this


class RecommendRequest(BaseModel):
    # The data DESCRIPTION the FE forwards (mirrors the data-aware-routing context) — never a verdict.
    # All optional: a missing field degrades its rule to the static default. Mirrors engine.RecommendContext
    # (the router owns the wire DTO, the engine owns the logic — same split as routers/ai.py ProposeRequest).
    data_columns: list[str] | None = None
    data_kind: str | None = None
    data_n_numeric_cols: int | None = None
    design: dict | None = None


@router.post("/skills/{skill_id}/recommend-params")
def recommend_params_route(skill_id: str, body: RecommendRequest):
    # Layer A "Auto-tune" (docs/auto-tune/spec.md): the DETERMINISTIC best-practice params for this
    # skill given the data description — no AI gateway, no key, works gateway-off. The FE stages the
    # returned diff into the shared pending queue as human-authored changes (no ✨ marker). Unknown
    # skill → 404. The engine (engine/recommend.py) is imported inside the handler to keep it off the
    # hot router-import path (same discipline as routers/data.py).
    from engine.recommend import RecommendContext, recommend_params

    try:
        recs = recommend_params(skill_id, RecommendContext(**body.model_dump()))
    except FileNotFoundError as exc:
        raise unknown_skill(skill_id) from exc
    return recs.model_dump()


@router.post("/skills/{skill_id}/run")
async def run(skill_id: str, request: Request, matrix: UploadFile, design: UploadFile | None = File(None)):
    # Synchronous one-shot — the proven fast path for light skills (B1). Heavy skills
    # should use POST /skills/{id}/jobs (below). Tuning params arrive as the query
    # string; the contract fills skill defaults and each runner coerces types.
    # An optional `design` sheet (sample->condition/time) feeds bulk + time-course DE;
    # it is threaded as a reserved param and kept out of the provenance record.
    path = _save_upload(matrix)
    params = dict(request.query_params)
    # P1c "is-my-data-clean?" guardrail (engine-spine spec §5, E3/D-e5): a block-severity QC
    # problem warns + REQUIRES an explicit override rather than silently producing a misleading
    # figure — the native moat for non-bioinformaticians. `override=true` runs anyway. The flag is
    # popped here so it never reaches the skill, methods text, or the recorded provenance config.
    override = to_bool(params.pop("override", False))
    design_path = _save_upload(design) if design is not None else None
    if design_path:
        params["_design_path"] = design_path
    return await _execute_skill_run(skill_id, path, matrix.filename, params, override, design_path)


@router.post("/skills/{skill_id}/jobs")
async def submit_job(
    skill_id: str, request: Request, matrix: UploadFile, ctx: AuthContext = Depends(require_user)
):
    # Async job path (B3): enqueue a run, return a job handle the FE polls. In inline
    # mode the job completes before this returns; arq mode runs it off-request. The job is owned
    # by the verified tenant (ctx.user_id) — never a request param (spec §6.2).
    if skill_id not in set(list_skill_ids()):
        raise unknown_skill(skill_id)
    path = _save_upload(matrix)
    params = dict(request.query_params)
    # C3: the same param-range gate as /run — reject an out-of-range knob before enqueuing.
    range_errors = validate_param_ranges(load_skill(skill_id), params)
    if range_errors:
        raise param_out_of_range(range_errors)
    job = submit(skill_id, path, params, matrix.filename, user_id=ctx.user_id, email=ctx.email)
    return job.public()


class RunDatasetRequest(BaseModel):
    dataset_id: str
    params: dict = {}
    override: bool = False


@router.post("/skills/{skill_id}/run-dataset")
async def run_dataset(skill_id: str, body: RunDatasetRequest, repo=Depends(_uploads_repo),
                      ctx: AuthContext = Depends(require_user)):
    # Run-from-dataset_id (sub-spec §5): the bytes are already in the store from the upload flow, so
    # no multipart re-upload. Reuses the EXACT run pipeline (QC / D1 / D2 gates, theme, table synth)
    # via _execute_skill_run; provenance's input sha is the dataset's real hash (staleness goes live).
    if skill_id not in set(list_skill_ids()):
        raise unknown_skill(skill_id)
    try:
        path, filename = _dataset_to_temp(repo, get_object_store(), ctx.user_id, body.dataset_id)
    except KeyError as exc:
        raise RunError.unsupported(
            "unknown_dataset", f"No dataset {body.dataset_id!r} for this account.",
            fix="Upload the file first, then run from the dataset it creates.") from exc
    except FileNotFoundError as exc:
        raise RunError.unsupported(
            "dataset_not_materialized", str(exc), status_code=409,
            fix="Re-upload the file to materialize its bytes, then run.") from exc
    try:
        return await _execute_skill_run(
            skill_id, path, filename, _stringify_params(body.params), body.override, None)
    finally:
        shutil.rmtree(pathlib.Path(path).parent, ignore_errors=True)


@router.post("/skills/{skill_id}/jobs-dataset")
async def submit_job_dataset(skill_id: str, body: RunDatasetRequest, repo=Depends(_uploads_repo),
                             ctx: AuthContext = Depends(require_user)):
    # Async (heavy-lane) twin of run-dataset — enqueue from a stored dataset. The worker owns the
    # temp's lifetime (same as the multipart /jobs path); cleaned by the C3 managed-temp/atexit path.
    if skill_id not in set(list_skill_ids()):
        raise unknown_skill(skill_id)
    try:
        path, filename = _dataset_to_temp(repo, get_object_store(), ctx.user_id, body.dataset_id)
    except KeyError as exc:
        raise RunError.unsupported(
            "unknown_dataset", f"No dataset {body.dataset_id!r} for this account.",
            fix="Upload the file first, then run from the dataset it creates.") from exc
    except FileNotFoundError as exc:
        raise RunError.unsupported(
            "dataset_not_materialized", str(exc), status_code=409,
            fix="Re-upload the file to materialize its bytes, then run.") from exc
    params = _stringify_params(body.params)
    range_errors = validate_param_ranges(load_skill(skill_id), params)
    if range_errors:
        raise param_out_of_range(range_errors)
    job = submit(skill_id, path, params, filename, user_id=ctx.user_id, email=ctx.email)
    return job.public()
