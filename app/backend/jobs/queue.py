"""Submit + execute a skill run as a job.

``execute_job`` is the single code path that actually runs a skill and stores its
result — shared verbatim by the inline executor and the arq worker, so the two modes
can never drift. ``submit`` picks the mode from ``SELOM_QUEUE``:

  * inline (default) — run to completion on-request. No infra; deterministic. The
    request blocks for the skill's duration, same as the synchronous /run endpoint.
  * arq — enqueue to Redis and return immediately; a worker process runs it.

Completion is observable cross-process via the shared result store: ``get_job``
probes it so arq jobs flip to ``succeeded`` once the worker writes the figure.
"""

from __future__ import annotations

import pathlib

from config import settings
from jobs.store import Job, JobStatus, TERMINAL, job_store
from storage.results import ResultStore, make_result_store

# One result store per process, chosen from config (local filesystem unless R2 is set).
result_store: ResultStore = make_result_store(settings)


def execute_job(job_id: str, data_path: str, params: dict) -> None:
    """Run the job's skill to completion, updating the store. Never raises."""
    from skills.contract import run_skill  # lazy: keeps import graph light

    job = job_store.get(job_id)
    if job is None:
        return
    job_store.update(job_id, status=JobStatus.RUNNING)
    try:
        figure = run_skill(job.skill_id, data_path, params)
        url = result_store.put(job_id, figure)
        job_store.update(job_id, status=JobStatus.SUCCEEDED, result_url=url)
    except Exception as exc:  # surface a clean message; never leak a 500 stack to the job
        job_store.update(job_id, status=JobStatus.FAILED, error=str(exc))
    finally:
        try:
            pathlib.Path(data_path).unlink(missing_ok=True)
        except OSError:
            pass


def submit(skill_id: str, data_path: str, params: dict) -> Job:
    """Create a job and either run it inline or hand it to the arq worker."""
    job = job_store.create(skill_id, params)
    if settings.queue == "arq":
        _enqueue_arq(job.id, skill_id, data_path, params)
    else:
        execute_job(job.id, data_path, params)
    return job_store.get(job.id)


def get_job(job_id: str) -> Job | None:
    """Job state for polling. In arq mode, detect out-of-process completion via the
    shared result store (the worker writes there before the API would otherwise know)."""
    job = job_store.get(job_id)
    if job is None:
        return None
    if job.status not in TERMINAL and settings.queue == "arq":
        url = result_store.url_if_exists(job_id)
        if url:
            job_store.update(job_id, status=JobStatus.SUCCEEDED, result_url=url)
    return job_store.get(job_id)


def _enqueue_arq(job_id: str, skill_id: str, data_path: str, params: dict) -> None:
    """Fire-and-forget enqueue to arq over Redis (DECISIONS #6). Lazy-imported so the
    light core never needs arq/redis. Requires the `[jobs]` extra + a running worker."""
    import asyncio

    from arq import create_pool
    from arq.connections import RedisSettings

    async def _go() -> None:
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await pool.enqueue_job("run_skill_job", job_id, skill_id, data_path, params)
        await pool.close()

    asyncio.run(_go())
