"""SQL-backed JobStore — the statelessness fix (step 2) + tenant ownership (step 7b).

Implements the ``JobStore`` surface (``create`` / ``get`` / ``update`` → a ``Job``) against the
``analysis_jobs`` table, so it drops into ``jobs/queue.py`` behind ``make_job_store`` with no caller
change. Unlike the in-memory store (a process-local dict), a job created on one instance is visible
to ``get`` on any other instance on the same database — a poll never lands on a cold worker that has
never seen the job (spec §4.1).

Step 7b: a job is **tenant-owned**. ``create`` stamps the verified ``user_id``, upserts the user
(first-request provisioning), and runs ``SET LOCAL app.user_id`` — all in ONE transaction so the
write satisfies the analysis_jobs FK + RLS on Postgres. ``get``/``update`` take an optional
``user_id`` that both sets the RLS tenant (Postgres) AND adds the predicate (SQLite, which has no
RLS) — so a cross-tenant poll returns nothing on either dialect. The worker (no requester) passes
the job's own ``user_id`` through the queue so its reads/writes stay tenant-scoped on Postgres too.
``public()`` is unchanged (no ``user_id``) — the FE wire shape the FE polls is identical.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa

from db.engine import make_engine
from db.schema import analysis_jobs
from db.tenant import set_tenant, upsert_user
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
        user_id=row.user_id,
        result_cache_key=row.result_cache_key,
        input_sha256=row.input_sha256,
    )


def _select_one(conn: sa.Connection, job_id: str, user_id: str | None) -> Job | None:
    stmt = sa.select(analysis_jobs).where(analysis_jobs.c.id == job_id)
    if user_id is not None:
        stmt = stmt.where(analysis_jobs.c.user_id == user_id)
    row = conn.execute(stmt).first()
    return _row_to_job(row) if row is not None else None


class SqlJobStore:
    """``JobStore`` surface over the ``analysis_jobs`` table (SQLite dev/test, Postgres prod)."""

    def __init__(self, engine: sa.Engine | None = None, url: str = "", create: bool = False) -> None:
        self.engine = engine if engine is not None else make_engine(url)
        if create:
            # Dev/test convenience (e.g. SQLite) — prod applies the Alembic migration instead.
            from db.schema import metadata

            metadata.create_all(self.engine)

    def create(
        self,
        skill_id: str,
        params: dict,
        filename: str | None = None,
        user_id: str | None = None,
        email: str | None = None,
        result_cache_key: str | None = None,
        input_sha256: str | None = None,
    ) -> Job:
        now = datetime.now(timezone.utc)
        jid = uuid.uuid4().hex
        with self.engine.begin() as conn:
            if user_id:
                set_tenant(conn, user_id)  # RLS tenant for this tx (Postgres)
                upsert_user(conn, user_id, email or f"{user_id}@unknown.local")  # first-request provisioning
            conn.execute(
                sa.insert(analysis_jobs).values(
                    id=jid,
                    user_id=user_id,
                    skill_id=skill_id,
                    status=JobStatus.QUEUED.value,
                    params=params or {},
                    filename=filename,
                    result_cache_key=result_cache_key,
                    input_sha256=input_sha256,
                    created_at=now,
                    updated_at=now,
                )
            )
            return _select_one(conn, jid, user_id)

    def find_succeeded(self, cache_key: str, user_id: str | None = None) -> Job | None:
        """Most-recent SUCCEEDED job with this content cache key for the tenant (M2 reuse), or None.
        Indexed by idx_jobs_cachekey; cross-instance, so a Lambda retry reuses a prior result."""
        if not cache_key:
            return None
        with self.engine.connect() as conn:
            if user_id:
                set_tenant(conn, user_id)
            stmt = (
                sa.select(analysis_jobs)
                .where(analysis_jobs.c.result_cache_key == cache_key)
                .where(analysis_jobs.c.status == JobStatus.SUCCEEDED.value)
            )
            if user_id is not None:
                stmt = stmt.where(analysis_jobs.c.user_id == user_id)
            row = conn.execute(stmt.order_by(analysis_jobs.c.updated_at.desc()).limit(1)).first()
            return _row_to_job(row) if row is not None else None

    def get(self, job_id: str, user_id: str | None = None) -> Job | None:
        with self.engine.connect() as conn:
            if user_id:
                set_tenant(conn, user_id)
            return _select_one(conn, job_id, user_id)

    def update(self, job_id: str, user_id: str | None = None, **changes) -> Job | None:
        values: dict = {}
        for key, value in changes.items():
            if key == "status" and isinstance(value, JobStatus):
                value = value.value  # store the enum's string value
            values[key] = value
        values["updated_at"] = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            if user_id:
                set_tenant(conn, user_id)
            stmt = sa.update(analysis_jobs).where(analysis_jobs.c.id == job_id)
            if user_id is not None:
                stmt = stmt.where(analysis_jobs.c.user_id == user_id)
            conn.execute(stmt.values(**values))
            return _select_one(conn, job_id, user_id)
