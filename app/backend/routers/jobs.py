import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from auth import AuthContext, require_user
from jobs.queue import get_job, result_store
from jobs.store import TERMINAL

from routers._run import _content_etag

router = APIRouter()


@router.get("/jobs/{job_id}")
def job_status(job_id: str, ctx: AuthContext = Depends(require_user)):
    job = get_job(job_id, ctx.user_id)  # scoped: another tenant's job id → 404
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return job.public()


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, ctx: AuthContext = Depends(require_user)):
    # Server-Sent Events: emit current state, then poll until terminal. Inline jobs are
    # already terminal, so this resolves in one event; arq jobs stream the transitions.
    async def stream():
        for _ in range(600):  # ~5 min ceiling at 0.5s/tick
            job = get_job(job_id, ctx.user_id)
            if job is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'unknown job'})}\n\n"
                return
            yield f"data: {json.dumps(job.public())}\n\n"
            if job.status in TERMINAL:
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/jobs/{job_id}/result")
def job_result(job_id: str, request: Request, ctx: AuthContext = Depends(require_user)):
    # Scope the result to the owner: confirm the job belongs to this tenant before serving its
    # bundle (the result store is keyed by job_id, so the ownership check is the gate).
    if get_job(job_id, ctx.user_id) is None:
        raise HTTPException(status_code=404, detail="result not available")
    bundle = result_store.get(job_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="result not available")
    # C2: a stored result is immutable, so its content hash is a stable ETag. An FE that already
    # holds this figure sends If-None-Match and gets a 304 (no figure re-download).
    etag = _content_etag(bundle)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(bundle, headers={"ETag": etag})  # {figure, provenance, methods} — /run shape
