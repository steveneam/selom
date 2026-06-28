"""Job records + the job-store seam.

``JobStore`` is a thin in-memory dict — all the inline (single-process) dev path needs.
``make_job_store`` selects it (default) or the SQL-backed ``SqlJobStore`` (materialization
step 2) by config, exactly as ``make_object_store``/``make_result_store`` select their
backends: the in-memory store for dev, the ``analysis_jobs`` table for a multi-instance /
Lambda deploy where a poll must see a job another instance created. A ``Job`` is the unit
the API polls; both backends return the same ``Job`` shape.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


TERMINAL = {JobStatus.SUCCEEDED, JobStatus.FAILED}


@dataclass
class Job:
    id: str
    skill_id: str
    status: JobStatus
    params: dict
    created_at: float
    updated_at: float
    filename: str | None = None  # original upload name, for the B4 provenance bundle
    result_url: str | None = None
    error: str | None = None
    user_id: str | None = None   # the verified tenant (materialization 7b); not in the FE wire shape

    def public(self) -> dict:
        """The wire shape the FE polls (GET /jobs/{id})."""
        return {
            "id": self.id,
            "skill_id": self.skill_id,
            "status": self.status.value,
            "result_url": self.result_url,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def create(
        self,
        skill_id: str,
        params: dict,
        filename: str | None = None,
        user_id: str | None = None,
        email: str | None = None,  # noqa: ARG002 — in-memory mode has no users table
    ) -> Job:
        now = time.time()
        job = Job(
            id=uuid.uuid4().hex,
            skill_id=skill_id,
            status=JobStatus.QUEUED,
            params=params,
            created_at=now,
            updated_at=now,
            filename=filename,
            user_id=user_id,
        )
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str, user_id: str | None = None) -> Job | None:
        """Fetch a job. When ``user_id`` is given, scope to that tenant (a cross-tenant poll → None)."""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        if user_id is not None and job.user_id is not None and job.user_id != user_id:
            return None
        return job

    def update(self, job_id: str, user_id: str | None = None, **changes) -> Job:  # noqa: ARG002
        job = self._jobs[job_id]
        for key, value in changes.items():
            setattr(job, key, value)
        job.updated_at = time.time()
        return job


def make_job_store(settings):
    """Select the job-store backend by config: in-memory (default) or SQL (``analysis_jobs``).

    Mirrors ``make_object_store``/``make_result_store`` — one config seam, the dev default
    unchanged until ``SELOM_JOB_STORE=sql`` (with ``SELOM_DATABASE_URL``) flips it on. The SQL
    store is lazy-imported so the light core never needs SQLAlchemy."""
    if settings.job_store.strip().lower() == "sql":
        from jobs.sql_store import SqlJobStore

        return SqlJobStore(url=settings.database_url, create=settings.db_auto_create)
    return JobStore()
