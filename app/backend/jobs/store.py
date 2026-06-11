"""Job records + an in-process registry.

The ``JobStore`` is intentionally a thin in-memory dict: it's all the inline (single
process) path needs, and it documents the seam where a Redis-backed store swaps in for
distributed arq mode (see ``jobs/worker.py``). A ``Job`` is the unit the API polls.
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
    result_url: str | None = None
    error: str | None = None

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

    def create(self, skill_id: str, params: dict) -> Job:
        now = time.time()
        job = Job(
            id=uuid.uuid4().hex,
            skill_id=skill_id,
            status=JobStatus.QUEUED,
            params=params,
            created_at=now,
            updated_at=now,
        )
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def update(self, job_id: str, **changes) -> Job:
        job = self._jobs[job_id]
        for key, value in changes.items():
            setattr(job, key, value)
        job.updated_at = time.time()
        return job


# Process-wide singleton (inline mode). Distributed mode replaces this with Redis.
job_store = JobStore()
