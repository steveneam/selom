"""Cross-tenant isolation — Acceptance E, the HARD merge gate (spec §6.4, plan R-3).

The headline production risk is a cross-tenant leak. This proves isolation at the two layers that
exist today:

  * **HTTP (the live tenant-scoped endpoints = jobs):** tenant A submits a job; B cannot poll it or
    read its result (404); a request param claiming to be B does NOT change ownership — the tenant is
    the verified claim, never input (spec §6.2).
  * **Application (``TenantQuery`` across every tenant table):** A reads only A's rows; A can't get/
    update/delete B's rows by guessing ids; an ``insert`` with a forged ``user_id`` is owned by A.

The **DB-RLS backstop** (step 6 of §6.4 — a raw-SQL bypass blocked by Postgres RLS) needs a real
Postgres; it runs only when ``SELOM_TEST_DATABASE_URL`` points at one (Aurora / a local PG), and
skips on the SQLite fast lane (which has no RLS — the application layer is the guarantee there).
"""

from __future__ import annotations

import os

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from auth.context import AuthContext, get_verifier
from db.schema import datasets, figures, gene_sets, metadata, papers, projects, workspaces
from db.tenant import TenantQuery, set_tenant, upsert_user
from jobs.sql_store import SqlJobStore


# =============================================================================================
# HTTP layer — the jobs endpoints (the only tenant-scoped HTTP surface today)
# =============================================================================================

class _SwitchVerifier:
    """A test verifier whose 'current tenant' can be flipped between requests."""

    def __init__(self, user_id: str = "A") -> None:
        self.user_id = user_id

    def verify(self, request) -> AuthContext:  # noqa: ARG002
        return AuthContext(user_id=self.user_id, email=f"{self.user_id}@x.com")


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    from main import app

    verifier = _SwitchVerifier("A")
    app.dependency_overrides[get_verifier] = lambda: verifier
    try:
        yield TestClient(app), verifier
    finally:
        app.dependency_overrides.pop(get_verifier, None)


def _submit(client, skill="cluster", params=""):
    return client.post(
        f"/skills/{skill}/jobs{params}",
        files={"matrix": ("x.h5ad", b"dummy", "application/octet-stream")},
    )


def test_a_job_is_invisible_to_another_tenant(http):
    client, verifier = http
    verifier.user_id = "A"
    job = _submit(client).json()
    jid = job["id"]
    assert client.get(f"/jobs/{jid}").status_code == 200  # A sees its own job
    assert client.get(f"/jobs/{jid}/result").status_code == 200

    verifier.user_id = "B"  # now poll as B, guessing A's job id
    assert client.get(f"/jobs/{jid}").status_code == 404
    assert client.get(f"/jobs/{jid}/result").status_code == 404
    assert client.get(f"/jobs/{jid}/events").text.count("error") >= 1  # SSE → unknown job


def test_artifact_table_bytes_are_invisible_to_another_tenant(http, tmp_path):
    """`GET /artifacts/{id}/table` — the sharpest hole the P-E audit found (spec §1).

    It served the EXACT matrix a skill consumed to whoever held the id, with no tenant check at
    all. An opaque id is an identifier, not an authorization, and "you would have to guess it" is
    not a control. Proved at the HTTP layer here; the engine layer is `test_lineage.py`.
    """
    import pandas as pd

    from engine import lineage
    from engine.lineage import ArtifactStore

    client, verifier = http
    prev = lineage._default
    lineage.set_store(ArtifactStore(root=tmp_path / "artifacts", enabled=True))
    try:
        df = pd.DataFrame({"gene": ["ACTB"], "padj": [0.01]})
        meta = lineage.materialize(df, owner="A", kind=lineage.KIND_INGESTED, filename="de.csv")
        aid = meta.artifact_id

        verifier.user_id = "A"
        assert client.get(f"/artifacts/{aid}").status_code == 200
        table = client.get(f"/artifacts/{aid}/table")
        assert table.status_code == 200 and b"ACTB" in table.content

        # B knows the id exactly — it is a content hash of a table B could hold too.
        verifier.user_id = "B"
        assert client.get(f"/artifacts/{aid}").status_code == 404
        assert client.get(f"/artifacts/{aid}/table").status_code == 404
    finally:
        lineage.set_store(prev)


def test_a_missing_artifact_404s_rather_than_403s(http, tmp_path):
    """404, never 403. A 403 confirms the id EXISTS, which turns the error code itself into an
    oracle for enumerating another tenant's artifacts."""
    import pandas as pd

    from engine import lineage
    from engine.lineage import ArtifactStore

    client, verifier = http
    prev = lineage._default
    lineage.set_store(ArtifactStore(root=tmp_path / "artifacts", enabled=True))
    try:
        meta = lineage.materialize(pd.DataFrame({"a": [1]}), owner="A",
                                   kind=lineage.KIND_INGESTED, filename="x.csv")
        verifier.user_id = "B"
        real_but_not_mine = client.get(f"/artifacts/{meta.artifact_id}")
        pure_fiction = client.get("/artifacts/0000000000000000000000000000000000000000000000000000000000000000")
        assert real_but_not_mine.status_code == pure_fiction.status_code == 404, (
            "a real-but-other-tenant id must be indistinguishable from a nonexistent one"
        )
    finally:
        lineage.set_store(prev)


def test_request_param_cannot_reassign_job_ownership(http):
    client, verifier = http
    verifier.user_id = "A"
    # a body/query param claiming to be B must NOT change the owner — the tenant is the claim.
    job = _submit(client, params="?user_id=B").json()
    jid = job["id"]
    verifier.user_id = "B"
    assert client.get(f"/jobs/{jid}").status_code == 404  # still A's job, invisible to B
    verifier.user_id = "A"
    assert client.get(f"/jobs/{jid}").status_code == 200


# =============================================================================================
# Application layer — TenantQuery across every tenant table
# =============================================================================================

def _seed_tenant(conn, store: SqlJobStore, uid: str) -> dict:
    """One of every owned row for a tenant; returns the ids for cross-tenant probing."""
    upsert_user(conn, uid, f"{uid}@x.com")
    tq = TenantQuery(conn, uid)
    ws = tq.insert(workspaces, name=f"{uid}-ws")
    proj = tq.insert(projects, name=f"{uid}-proj", workspace_id=ws)
    ds = tq.insert(datasets, project_id=proj, filename="d.csv")
    fig = tq.insert(figures, project_id=proj, title="F")
    paper = tq.insert(papers, filename="p.pdf")
    gs = tq.insert(gene_sets, name="GS")
    job = store.create("volcano", {}, user_id=uid)
    return {"workspace": ws, "project": proj, "dataset": ds, "figure": fig,
            "paper": paper, "gene_set": gs, "job": job.id}


@pytest.fixture
def seeded():
    engine = sa.create_engine("sqlite://", future=True)
    metadata.create_all(engine)
    store = SqlJobStore(engine=engine)
    with engine.begin() as conn:
        ids = {"A": _seed_tenant(conn, store, "A"), "B": _seed_tenant(conn, store, "B")}
        yield conn, store, ids


_TABLES = {
    "workspace": workspaces, "project": projects, "dataset": datasets,
    "figure": figures, "paper": papers, "gene_set": gene_sets,
}


def test_select_returns_only_own_rows(seeded):
    conn, _store, ids = seeded
    a = TenantQuery(conn, "A")
    for key, table in _TABLES.items():
        rows = a.select(table)
        assert len(rows) == 1, f"{key}: A should see exactly its own row"
        assert rows[0].user_id == "A"


def test_cannot_get_or_mutate_another_tenants_rows(seeded):
    conn, _store, ids = seeded
    a = TenantQuery(conn, "A")
    for key, table in _TABLES.items():
        bid = ids["B"][key]
        assert a.get(table, bid) is None, f"{key}: A must not read B's row"
        assert a.update(table, bid, **_a_change(key)) == 0, f"{key}: A must not update B's row"
        assert a.delete(table, bid) == 0, f"{key}: A must not delete B's row"
    # B's rows are all still intact
    b = TenantQuery(conn, "B")
    for key, table in _TABLES.items():
        assert b.get(table, ids["B"][key]) is not None


_CHANGE_COL = {
    "workspace": "name", "project": "name", "gene_set": "name",
    "dataset": "filename", "paper": "filename", "figure": "title",
}


def _a_change(key: str) -> dict:
    return {_CHANGE_COL[key]: "hijacked"}


def test_insert_with_forged_user_id_is_owned_by_caller(seeded):
    conn, _store, _ids = seeded
    a = TenantQuery(conn, "A")
    pid = a.insert(projects, name="forged", user_id="B")  # claims B
    assert a.get(projects, pid).user_id == "A"
    assert TenantQuery(conn, "B").get(projects, pid) is None  # B genuinely can't see it


def test_job_is_tenant_scoped(seeded):
    _conn, store, ids = seeded
    assert store.get(ids["A"]["job"], "A") is not None
    assert store.get(ids["A"]["job"], "B") is None  # B can't read A's job over the SQL store


# =============================================================================================
# DB-RLS backstop — step 6 of §6.4 (Postgres only; skipped on the SQLite fast lane)
# =============================================================================================

_PG_URL = os.environ.get("SELOM_TEST_DATABASE_URL", "")
_pg = pytest.mark.skipif(
    not _PG_URL.startswith("postgresql"),
    reason="DB-RLS backstop needs a Postgres (set SELOM_TEST_DATABASE_URL); SQLite has no RLS",
)


@_pg
def test_db_rls_blocks_raw_sql_bypass():
    """Even a hand-written SELECT that ignores TenantQuery sees only the current tenant's rows."""
    import argparse
    import pathlib

    from alembic import command
    from alembic.config import Config

    backend = pathlib.Path(__file__).resolve().parent.parent
    cfg = Config()
    cfg.set_main_option("script_location", str(backend / "alembic"))
    cfg.cmd_opts = argparse.Namespace(x=[f"url={_PG_URL}"])
    command.upgrade(cfg, "head")

    engine = sa.create_engine(_PG_URL, future=True)
    try:
        with engine.begin() as conn:
            for uid in ("A", "B"):
                set_tenant(conn, uid)
                upsert_user(conn, uid, f"{uid}@x.com")
                TenantQuery(conn, uid).insert(workspaces, name=f"{uid}-ws")
        # As A, a raw SQL SELECT (bypassing TenantQuery) still returns only A's row.
        with engine.connect() as conn:
            set_tenant(conn, "A")
            rows = conn.execute(sa.text("SELECT user_id FROM workspaces")).all()
            assert rows and all(r.user_id == "A" for r in rows)
    finally:
        command.downgrade(cfg, "base")
        engine.dispose()
