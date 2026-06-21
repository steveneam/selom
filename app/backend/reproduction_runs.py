"""Reproduction-run store + the run lifecycle (live-reproduction-spec §5).

A reproduce *run* is the new job type alongside the per-skill job: it orchestrates many panel
drives (``reproduction_drive.reproduce``) and produces a ``Ledger``, not a single figure. This
module is the FastAPI-free run store + lifecycle (so it stays unit-testable); ``main.py`` owns the
multipart routes + SSE. It reuses ``jobs.store``'s ``JobStatus``/``TERMINAL`` vocabulary + SSE
pattern (consistency), but keeps its own store because the artifact (a driven ``Ledger``) differs.

v1 is the **inline** path (``config.queue != "arq"``): ``start_run`` drives to completion on-request,
so the run is already terminal when the POST returns and the SSE resolves in one event. The arq
async worker (slow multi-skill drives off-request) is the deferred SCALE path — gated behind an ASK
([[ask-before-docker-wsl]]); v1 deliberately stays inline so no new infra is forced now.
"""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field

import reproduction as R
import reproduction_drive
from jobs.store import JobStatus


class RunRecord(BaseModel):
    """One reproduction run — the unit the FE polls (GET) / streams (SSE)."""

    id: str
    status: JobStatus = JobStatus.QUEUED
    progress: str = ""
    ledger: R.Ledger | None = None
    drive_summary: dict = Field(default_factory=dict)
    data_fits: list = Field(default_factory=list)  # list[engine.compat.FileFitReport] — Slice 2
    panel_drives: list = Field(default_factory=list)  # list[reproduction_drive.PanelDrive] — Slice 2
    error: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0


class RunStore:
    """In-process registry (inline mode) — the seam a Redis store swaps into for arq, like JobStore."""

    def __init__(self) -> None:
        self._runs: dict[str, RunRecord] = {}

    def create(self) -> RunRecord:
        now = time.time()
        rec = RunRecord(id=uuid.uuid4().hex, status=JobStatus.QUEUED, created_at=now, updated_at=now)
        self._runs[rec.id] = rec
        return rec

    def get(self, run_id: str) -> RunRecord | None:
        return self._runs.get(run_id)

    def update(self, run_id: str, **changes) -> RunRecord:
        rec = self._runs[run_id]
        updated = rec.model_copy(update={**changes, "updated_at": time.time()})
        self._runs[run_id] = updated
        return updated


run_store = RunStore()


def start_run(main_path: str, supplement_paths: list | None = None, *, paper_id: str = "",
              paper: R.Paper | None = None, data_map: dict[str, str] | None = None,
              params: dict | None = None, drive_fn=None) -> RunRecord:
    """Create a run and drive it inline to completion (the v1 path). ``drive_fn`` is injectable for
    tests; the default is the real ``reproduction_drive.reproduce``. Never raises — a drive failure
    is recorded as a ``failed`` run, not a 500."""
    drive = drive_fn or reproduction_drive.reproduce
    rec = run_store.create()
    run_store.update(rec.id, status=JobStatus.RUNNING, progress="running the matched skills")
    try:
        result = drive(main_path, supplement_paths or [], paper_id=(paper_id or rec.id),
                       paper=paper, data_map=data_map, params=params)
        run_store.update(rec.id, status=JobStatus.SUCCEEDED, ledger=result.ledger,
                         drive_summary=result.summary,
                         data_fits=getattr(result, "data_fits", []),
                         panel_drives=getattr(result, "panel_drives", []), progress="scored")
    except Exception as exc:  # noqa: BLE001 — surface a clean failed run, never a 500 stack
        run_store.update(rec.id, status=JobStatus.FAILED, error=str(exc), progress="failed")
    return run_store.get(rec.id)


def get_run(run_id: str) -> RunRecord | None:
    return run_store.get(run_id)


def public(rec: RunRecord, *, light: bool = False) -> dict:
    """The wire shape. ``light`` (for SSE ticks) omits the heavy ledger — the FE fetches the full
    ledger via GET once ``succeeded``; on success the full payload is the same shape as
    ``GET /papers/{slug}`` so the Score stage reuses every showcase component."""
    out: dict = {"run_id": rec.id, "status": rec.status.value, "progress": rec.progress}
    if rec.error:
        out["error"] = rec.error
    if not light and rec.ledger is not None:
        out["ledger"] = rec.ledger.model_dump()
        out["scorecard"] = rec.ledger.scorecard.model_dump() if rec.ledger.scorecard else None
        out["drive_summary"] = rec.drive_summary
        # The dropped-data fit ranking (Slice 2) — surfaced AFTER the run so the Score stage shows
        # how good/compatible each supplement was, with the confidence band the score means.
        out["data_fits"] = [f.model_dump() if hasattr(f, "model_dump") else f for f in rec.data_fits]
        # The honest per-panel drive record (Slice 2) — lets the Score stage offer a data picker for
        # exactly the `data_unmatched` panels (point one at a chosen file → re-run with `data_map`).
        out["panel_drives"] = [d.model_dump() if hasattr(d, "model_dump") else d
                               for d in rec.panel_drives]
    return out
