"""SQL-backed JobStore — the statelessness fix (materialization step 2).

Implements the exact ``JobStore`` surface (``create`` / ``get`` / ``update`` → a ``Job``) against
the ``analysis_jobs`` table, so it drops into ``jobs/queue.py`` behind ``make_job_store`` with no
caller change. Unlike the in-memory store (a process-local dict), a job created on one instance is
visible to ``get`` on any other instance on the same database — a poll never lands on a cold
worker that has never seen the job (spec §4.1).

The queue already operates **by id + re-fetch** (``update(job_id, …)`` then ``get(job_id)``), so it
never relied on the in-memory store's shared-object mutation — exactly what a row-backed store needs.
Timestamps are stored as ``timestamptz`` and surfaced as epoch floats in ``Job`` so the wire shape
the FE polls (``created_at``/``updated_at`` numbers) is unchanged across the seam.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa

from db.engine import make_engine
from db.schema import analysis_jobs
from jobs.store import Job, JobStatus


def _row_to_job(row) -> Job:
    return Job(
        id=row.id,
        skill_id=row.skill_id,
        status=JobStatus(row.status),
        params=row.params or {},
        created_at=row.created_at.timestamp(),
        updated_at=row.updated_at.timestamp(),
        filename=row.filename,
        result_url=row.result_url,
        error=row.error,
    )


class SqlJobStore:
    """``JobStore`` surface over the ``analysis_jobs`` table (SQLite dev/test, Postgres prod)."""

    def __init__(self, engine: sa.Engine | None = None, url: str = "", create: bool = False) -> None:
        self.engine = engine if engine is not None else make_engine(url)
        if create:
            # Dev/test convenience (e.g. SQLite) — prod applies the Alembic migration instead.
            from db.schema import metadata

            metadata.create_all(self.engine)

    def create(self, skill_id: str, params: dict, filename: str | None = None) -> Job:
        now = datetime.now(timezone.utc)
        jid = uuid.uuid4().hex
        with self.engine.begin() as conn:
            conn.execute(
                sa.insert(analysis_jobs).values(
                    id=jid,
                    skill_id=skill_id,
                    status=JobStatus.QUEUED.value,
                    params=params or {},
                    filename=filename,
                    created_at=now,
                    updated_at=now,
                )
            )
        return self.get(jid)

    def get(self, job_id: str) -> Job | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                sa.select(analysis_jobs).where(analysis_jobs.c.id == job_id)
            ).first()
        return _row_to_job(row) if row is not None else None

    def update(self, job_id: str, **changes) -> Job | None:
        values: dict = {}
        for key, value in changes.items():
            if key == "status" and isinstance(value, JobStatus):
                value = value.value  # store the enum's string value
            values[key] = value
        values["updated_at"] = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            conn.execute(
                sa.update(analysis_jobs).where(analysis_jobs.c.id == job_id).values(**values)
            )
        return self.get(job_id)
