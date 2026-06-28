"""Job store seam (AWS materialization step 2 — statelessness fix).

The win: a job created on one instance is visible to a poll on another, because state lives in
the `analysis_jobs` row, not a process-local dict. Validated here on stdlib SQLite (no Aurora) —
the SQLAlchemy-portable store runs the same on SQLite and Postgres, so the dev/test path is a
faithful stand-in for prod (plan D6). Four layers of proof:
  * make_job_store selects in-memory (default) vs SQL by config;
  * SqlJobStore CRUD round-trips + the wire shape (epoch-float timestamps) is unchanged;
  * the cross-instance guarantee — a fresh store (separate engine) reads another's job;
  * the Alembic prod migration applies cleanly + the full /jobs submit path runs over SQL.
"""

from __future__ import annotations

import types

import sqlalchemy as sa

from jobs.sql_store import SqlJobStore
from jobs.store import JobStatus, JobStore, make_job_store


def _sqlite_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'jobs.db'}"


# --- the config seam ---------------------------------------------------------------------------

def test_make_job_store_defaults_to_memory():
    settings = types.SimpleNamespace(job_store="memory", database_url="", db_auto_create=False)
    assert isinstance(make_job_store(settings), JobStore)


def test_make_job_store_selects_sql(tmp_path):
    settings = types.SimpleNamespace(
        job_store="sql", database_url=_sqlite_url(tmp_path), db_auto_create=True
    )
    assert isinstance(make_job_store(settings), SqlJobStore)


# --- SqlJobStore CRUD + wire shape -------------------------------------------------------------

def test_sql_store_create_get_update_roundtrip(tmp_path):
    store = SqlJobStore(url=_sqlite_url(tmp_path), create=True)
    job = store.create("volcano", {"fc_threshold": 2.0}, filename="de.csv")
    assert job.status is JobStatus.QUEUED
    assert job.skill_id == "volcano" and job.filename == "de.csv"
    assert job.params == {"fc_threshold": 2.0}

    got = store.get(job.id)
    assert got is not None and got.id == job.id and got.status is JobStatus.QUEUED

    updated = store.update(job.id, status=JobStatus.SUCCEEDED, result_url="/jobs/x/result")
    assert updated.status is JobStatus.SUCCEEDED and updated.result_url == "/jobs/x/result"
    # the change persists on a re-fetch (not just the returned object)
    assert store.get(job.id).status is JobStatus.SUCCEEDED
    assert store.get("deadbeef") is None


def test_sql_store_wire_shape_is_epoch_floats(tmp_path):
    """public() must stay FE-compatible: created_at/updated_at are epoch numbers, not ISO strings."""
    store = SqlJobStore(url=_sqlite_url(tmp_path), create=True)
    job = store.create("cluster", {})
    pub = store.get(job.id).public()
    assert isinstance(pub["created_at"], float) and isinstance(pub["updated_at"], float)
    assert pub["status"] == "queued" and pub["skill_id"] == "cluster"
    assert set(pub) == {"id", "skill_id", "status", "result_url", "error",
                        "created_at", "updated_at"}


def test_update_bumps_updated_at(tmp_path):
    store = SqlJobStore(url=_sqlite_url(tmp_path), create=True)
    job = store.create("pca", {})
    after = store.update(job.id, status=JobStatus.RUNNING)
    assert after.updated_at >= job.created_at


# --- the statelessness guarantee (the whole point of step 2) -----------------------------------

def test_a_fresh_instance_sees_a_job_created_by_another(tmp_path):
    """A job created via one store/engine is visible to a SEPARATE store on its own engine over
    the same database — what an in-memory dict (a fresh, empty JobStore) could never do."""
    url = _sqlite_url(tmp_path)
    instance_a = SqlJobStore(engine=sa.create_engine(url), create=True)
    job = instance_a.create("umap", {"n_neighbors": 15})
    instance_a.update(job.id, status=JobStatus.SUCCEEDED, result_url="/jobs/u/result")

    # a "cold" second instance — its own engine, no shared in-process state
    instance_b = SqlJobStore(engine=sa.create_engine(url))
    seen = instance_b.get(job.id)
    assert seen is not None
    assert seen.status is JobStatus.SUCCEEDED and seen.result_url == "/jobs/u/result"
    # contrast: a fresh in-memory store has never heard of it
    assert JobStore().get(job.id) is None


# --- the Alembic prod migration applies (the real prod schema path) ----------------------------

def test_alembic_migration_creates_analysis_jobs(tmp_path):
    import argparse
    import pathlib

    from alembic import command
    from alembic.config import Config

    backend = pathlib.Path(__file__).resolve().parent.parent
    url = _sqlite_url(tmp_path)
    cfg = Config()
    cfg.set_main_option("script_location", str(backend / "alembic"))
    cfg.cmd_opts = argparse.Namespace(x=[f"url={url}"])  # env.py reads -x url=…

    command.upgrade(cfg, "head")

    eng = sa.create_engine(url)
    insp = sa.inspect(eng)
    assert "analysis_jobs" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("analysis_jobs")}
    assert {"id", "user_id", "skill_id", "status", "params", "result_url", "created_at"} <= cols
    idx = {i["name"] for i in insp.get_indexes("analysis_jobs")}
    assert {"idx_jobs_user", "idx_jobs_status", "idx_jobs_cachekey"} <= idx

    # downgrade is reversible
    command.downgrade(cfg, "base")
    assert "analysis_jobs" not in sa.inspect(sa.create_engine(url)).get_table_names()


# --- end-to-end: the /jobs submit path runs over the SQL store ---------------------------------

def test_submit_runs_a_job_over_the_sql_store(tmp_path, monkeypatch):
    """The queue (submit → execute_job → get_job) is by-id, so it drives the SQL store unchanged;
    the completed job is then readable from a fresh instance — statelessness, end to end."""
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    from jobs import queue

    url = _sqlite_url(tmp_path)
    monkeypatch.setattr(queue, "job_store", SqlJobStore(url=url, create=True))

    src = tmp_path / "matrix.csv"
    src.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")

    job = queue.submit("volcano", str(src), {}, filename="matrix.csv")
    assert job.status is JobStatus.SUCCEEDED and job.result_url

    # a fresh instance (cold) sees the succeeded job — the statelessness acceptance
    assert SqlJobStore(engine=sa.create_engine(url)).get(job.id).status is JobStatus.SUCCEEDED
