"""arq worker entrypoint (DECISIONS #6) — the distributed/off-request job path.

Run alongside the API when ``SELOM_QUEUE=arq``:

    uv run --directory app/backend arq jobs.worker.WorkerSettings

The worker runs the SAME ``execute_job`` the inline path uses and writes the figure
to the shared result store (R2 in production), so the API observes completion via
``get_job``'s result-store probe.

Status caveat (follow-up): job *status* is still held in each process's in-memory
``JobStore``. The success path is cross-process (result store), but error messages and
queued/running transitions need a Redis-backed JobStore to be visible to the API. That
swap is the remaining B3 work; inline mode is the verified path today.
"""

from __future__ import annotations

from config import settings


async def run_skill_job(ctx, job_id: str, skill_id: str, data_path: str, params: dict) -> None:
    from jobs.queue import execute_job

    execute_job(job_id, data_path, params)


class WorkerSettings:
    functions = [run_skill_job]

    @staticmethod
    def redis_settings():
        from arq.connections import RedisSettings

        return RedisSettings.from_dsn(settings.redis_url)
