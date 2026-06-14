import asyncio
import json
import pathlib
import shutil
import tempfile

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

import guardrails
import methods
import provenance
from gene_sets import library as gene_sets
from jobs.queue import get_job, result_store, submit
from jobs.store import TERMINAL
from skills.contract import load_skill, run_skill
from skills.registry import list_catalog, list_skill_ids

app = FastAPI(title="Selom API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/skills")
def list_skills():
    # Live Skill-Store registry: every on-disk skill as a SkillCatalogEntry. The FE
    # Store reads this and drops its hard-coded Verified seed (B3 — registry-driven).
    return list_catalog()


@app.get("/skills/{skill_id}")
def describe(skill_id: str):
    return load_skill(skill_id).model_dump()        # registry-driven UI reads this


@app.get("/gene-sets")
def gene_sets_list(q: str = "", source: str | None = None, limit: int = 50):
    # Gene-set builder Phase A (DECISIONS #11): a searchable, license-clean catalog over
    # the corpus Selom owns or that is open (GO · WikiPathways · curated). The FE "Gene
    # Sets" surface reads this; cards omit the full member list (fetched per set below).
    return {"sources": gene_sets.list_sources(), "results": gene_sets.search(q, source, limit)}


@app.get("/gene-sets/{set_id}")
def gene_set_detail(set_id: str):
    s = gene_sets.get_set(set_id)
    if s is None:
        raise HTTPException(status_code=404, detail=f"unknown gene set '{set_id}'")
    return s                                            # card + member symbols + provenance


def _save_upload(matrix: UploadFile) -> str:
    # Preserve the upload's extension so skills can tell .h5ad (scRNA) from .csv (bulk).
    suffix = pathlib.Path(matrix.filename or "").suffix or ".h5ad"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        shutil.copyfileobj(matrix.file, f)
        return f.name


@app.post("/skills/{skill_id}/run")
async def run(skill_id: str, request: Request, matrix: UploadFile, design: UploadFile | None = File(None)):
    # Synchronous one-shot — the proven fast path for light skills (B1). Heavy skills
    # should use POST /skills/{id}/jobs (below). Tuning params arrive as the query
    # string; the contract fills skill defaults and each runner coerces types.
    # An optional `design` sheet (sample->condition/time) feeds bulk + time-course DE;
    # it is threaded as a reserved param and kept out of the provenance record.
    path = _save_upload(matrix)
    params = dict(request.query_params)
    design_path = _save_upload(design) if design is not None else None
    if design_path:
        params["_design_path"] = design_path
    spec = load_skill(skill_id)
    try:
        figure = run_skill(skill_id, path, params)
        # B4 publish-confidence: every figure ships with its reproducibility bundle +
        # auto methods-text. Additive — the FE still reads `.figure`.
        return {
            "figure": figure,                            # Plotly JSON -> frontend
            "provenance": provenance.build(spec, path, matrix.filename, params),
            "methods": methods.build(spec, params),
            "guardrails": guardrails.build(spec, path, params),
        }
    finally:
        if design_path:
            pathlib.Path(design_path).unlink(missing_ok=True)


@app.post("/skills/{skill_id}/jobs")
async def submit_job(skill_id: str, request: Request, matrix: UploadFile):
    # Async job path (B3): enqueue a run, return a job handle the FE polls. In inline
    # mode the job completes before this returns; arq mode runs it off-request.
    if skill_id not in set(list_skill_ids()):
        raise HTTPException(status_code=404, detail=f"unknown skill '{skill_id}'")
    path = _save_upload(matrix)
    params = dict(request.query_params)
    job = submit(skill_id, path, params, matrix.filename)
    return job.public()


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return job.public()


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str):
    # Server-Sent Events: emit current state, then poll until terminal. Inline jobs are
    # already terminal, so this resolves in one event; arq jobs stream the transitions.
    async def stream():
        for _ in range(600):  # ~5 min ceiling at 0.5s/tick
            job = get_job(job_id)
            if job is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'unknown job'})}\n\n"
                return
            yield f"data: {json.dumps(job.public())}\n\n"
            if job.status in TERMINAL:
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/jobs/{job_id}/result")
def job_result(job_id: str):
    bundle = result_store.get(job_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="result not available")
    return bundle                                     # {figure, provenance, methods} — same shape as /run
