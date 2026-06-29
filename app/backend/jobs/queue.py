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
from jobs.store import TERMINAL, Job, JobStatus, make_job_store
from storage.results import ResultStore, make_result_store

# One result store + one job store per process, chosen from config. The job store is in-memory
# by default (inline dev) or SQL-backed (SELOM_JOB_STORE=sql) so a poll on another instance sees
# this job — the statelessness fix (materialization step 2). Both are by-id stores; the queue
# operates by id + re-fetch, so the SQL backend is a drop-in.
result_store: ResultStore = make_result_store(settings)
job_store = make_job_store(settings)


def execute_job(job_id: str, data_path: str, params: dict, user_id: str | None = None) -> None:
    """Run the job's skill to completion, updating the store. Never raises.

    ``user_id`` (the job's tenant) is threaded to every store call so the worker's reads/writes stay
    tenant-scoped under Postgres RLS — on SQLite (no RLS) it's harmless."""
    from companions import guardrails
    from companions import methods
    from companions import provenance
    from skills.contract import load_skill, run_skill_with_table  # lazy: keeps import graph light

    job = job_store.get(job_id, user_id)
    if job is None:
        return
    job_store.update(job_id, user_id=user_id, status=JobStatus.RUNNING)
    try:
        spec = load_skill(job.skill_id)
        figure, table = run_skill_with_table(job.skill_id, data_path, params)
        # Store the full B4 bundle (same shape /run returns) so /jobs/{id}/result
        # carries the reproducibility record + methods + Statistics table, not just the figure.
        bundle = {
            "figure": figure,
            "provenance": provenance.build(spec, data_path, job.filename, params),
            "methods": methods.build(spec, params),
            "guardrails": guardrails.build(spec, data_path, params),
            "table": table,
        }
        url = result_store.put(job_id, bundle)
        job_store.update(job_id, user_id=user_id, status=JobStatus.SUCCEEDED, result_url=url)
    except Exception as exc:  # surface a clean message; never leak a 500 stack to the job
        job_store.update(job_id, user_id=user_id, status=JobStatus.FAILED, error=str(exc))
    finally:
        try:
            pathlib.Path(data_path).unlink(missing_ok=True)
        except OSError:
            pass


def _content_keys(skill_id: str, data_path: str, params: dict) -> tuple[str | None, str | None]:
    """``(result_cache_key, input_sha256)`` for this run — the M2 submission idempotency key, or
    ``(None, None)`` if the input is unhashable. Best-effort: never blocks a submit."""
    try:
        from skills._result_cache import _file_sha256, cache_key  # lazy: keep the import graph light
        from skills.contract import load_skill

        spec = load_skill(skill_id)
        ckey = cache_key(skill_id, spec.version, spec.param_spec, data_path, params)
        return ckey, _file_sha256(data_path)
    except Exception:  # noqa: BLE001 — idempotency metadata is advisory; a failure must not block the run
        return None, None


def submit(
    skill_id: str,
    data_path: str,
    params: dict,
    filename: str | None = None,
    user_id: str | None = None,
    email: str | None = None,
) -> Job:
    """Create a tenant-owned job and either run it inline or hand it to the arq worker.

    ``user_id`` defaults to the configured dev tenant so the inline/offline path is unchanged; the
    HTTP endpoint passes the verified ``ctx.user_id`` (never a request param)."""
    uid = user_id or settings.dev_user_id
    ckey, input_sha = _content_keys(skill_id, data_path, params)
    # M2 idempotency (opt-in): a duplicate/retried submit (same skill+version+params+input) reuses the
    # prior SUCCEEDED job instead of creating a second row + recomputing. OFF by default → inline dev
    # path unchanged. The columns are stamped on create regardless (metadata / future dedup).
    if settings.job_idempotency and ckey:
        existing = job_store.find_succeeded(ckey, uid)
        if existing is not None and existing.result_url:
            try:
                pathlib.Path(data_path).unlink(missing_ok=True)  # we won't run, so clean the temp here
            except OSError:
                pass
            return existing
    job = job_store.create(
        skill_id, params, filename, user_id=uid, email=email or settings.dev_user_email,
        result_cache_key=ckey, input_sha256=input_sha,
    )
    if settings.queue == "arq":
        _enqueue_arq(job.id, skill_id, data_path, params, uid)
    else:
        execute_job(job.id, data_path, params, uid)
    return job_store.get(job.id, uid)


def get_job(job_id: str, user_id: str | None = None) -> Job | None:
    """Job state for polling, scoped to the requesting tenant (a cross-tenant poll → None → 404).
    In arq mode, detect out-of-process completion via the shared result store (the worker writes
    there before the API would otherwise know)."""
    job = job_store.get(job_id, user_id)
    if job is None:
        return None
    if job.status not in TERMINAL and settings.queue == "arq":
        url = result_store.url_if_exists(job_id)
        if url:
            job_store.update(job_id, user_id=user_id, status=JobStatus.SUCCEEDED, result_url=url)
    return job_store.get(job_id, user_id)


def _enqueue_arq(job_id: str, skill_id: str, data_path: str, params: dict, user_id: str | None = None) -> None:
    """Fire-and-forget enqueue to arq over Redis (DECISIONS #6). Lazy-imported so the
    light core never needs arq/redis. Requires the `[jobs]` extra + a running worker."""
    import asyncio

    from arq import create_pool
    from arq.connections import RedisSettings

    async def _go() -> None:
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await pool.enqueue_job("run_skill_job", job_id, skill_id, data_path, params, user_id)
        await pool.close()

    asyncio.run(_go())
