"""TenantQuery + the DB-tenant helpers + retry/backoff (materialization 7b, spec §6/§8).

Proves the *application-layer* isolation guarantee on SQLite (the dev/test path; the Postgres RLS
backstop is exercised by ``tests/test_tenant_isolation.py`` when a Postgres URL is available): every
TenantQuery method is scoped, ``insert`` overwrites a forged ``user_id``, ``update`` can't reassign
ownership, and a tenant can't touch another tenant's rows by guessing ids.
"""

from __future__ import annotations

import sqlalchemy as sa
import pytest

from db.retry import is_transient, run_with_db_retry
from db.schema import metadata, projects, users, workspaces
from db.tenant import TenantQuery, set_tenant, upsert_user
from sqlalchemy.exc import OperationalError


@pytest.fixture
def conn():
    engine = sa.create_engine("sqlite://", future=True)
    metadata.create_all(engine)
    with engine.begin() as c:
        # two tenants
        for uid, email in (("A", "a@x.com"), ("B", "b@x.com")):
            upsert_user(c, uid, email)
        yield c


def test_insert_and_select_is_tenant_scoped(conn):
    a, b = TenantQuery(conn, "A"), TenantQuery(conn, "B")
    a.insert(workspaces, name="A-space")
    b.insert(workspaces, name="B-space")
    a_rows = a.select(workspaces)
    assert [r.name for r in a_rows] == ["A-space"]
    assert all(r.user_id == "A" for r in a_rows)
    assert [r.name for r in b.select(workspaces)] == ["B-space"]


def test_insert_overwrites_forged_user_id(conn):
    a = TenantQuery(conn, "A")
    # a malicious body claiming to be B is silently corrected to A
    wid = a.insert(workspaces, name="claimed-by-B", user_id="B")
    row = a.get(workspaces, wid)
    assert row is not None and row.user_id == "A"
    # ...and B genuinely cannot see it
    assert TenantQuery(conn, "B").get(workspaces, wid) is None


def test_get_is_scoped(conn):
    a, b = TenantQuery(conn, "A"), TenantQuery(conn, "B")
    wid = a.insert(workspaces, name="A-only")
    assert a.get(workspaces, wid).name == "A-only"
    assert b.get(workspaces, wid) is None  # B guessing A's id gets nothing


def test_update_is_scoped_and_cannot_reassign_owner(conn):
    a, b = TenantQuery(conn, "A"), TenantQuery(conn, "B")
    wid = a.insert(workspaces, name="orig")
    # B cannot update A's row
    assert b.update(workspaces, wid, name="hijacked") == 0
    assert a.get(workspaces, wid).name == "orig"
    # A can update its own, but user_id in changes is ignored (no ownership transfer)
    assert a.update(workspaces, wid, name="renamed", user_id="B") == 1
    row = a.get(workspaces, wid)
    assert row.name == "renamed" and row.user_id == "A"


def test_delete_is_scoped(conn):
    a, b = TenantQuery(conn, "A"), TenantQuery(conn, "B")
    wid = a.insert(workspaces, name="doomed")
    assert b.delete(workspaces, wid) == 0  # B can't delete A's row
    assert a.get(workspaces, wid) is not None
    assert a.delete(workspaces, wid) == 1
    assert a.get(workspaces, wid) is None


def test_select_with_filters(conn):
    a = TenantQuery(conn, "A")
    ws = a.insert(workspaces, name="W")
    a.insert(projects, name="p1", workspace_id=ws)
    a.insert(projects, name="p2", workspace_id=ws)
    assert {r.name for r in a.select(projects, workspace_id=ws)} == {"p1", "p2"}


def test_tenant_query_requires_user_id(conn):
    with pytest.raises(ValueError):
        TenantQuery(conn, "")


def test_set_tenant_is_noop_on_sqlite(conn):
    set_tenant(conn, "A")  # must not raise on a non-Postgres dialect


def test_upsert_user_is_idempotent(conn):
    upsert_user(conn, "A", "changed@x.com")  # A already exists → no-op, no error
    rows = list(conn.execute(sa.select(users).where(users.c.user_id == "A")))
    assert len(rows) == 1
    assert rows[0].email == "a@x.com"  # original kept (do-nothing on conflict)


# --- retry / backoff --------------------------------------------------------------------------

def _op_error(msg: str) -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception(msg))


def test_is_transient_classifies_resume_errors():
    assert is_transient(_op_error("the database is resuming"))
    assert is_transient(_op_error("server closed the connection unexpectedly"))
    assert not is_transient(_op_error("relation does not exist"))
    assert not is_transient(ValueError("nope"))


def test_retry_succeeds_after_transient():
    calls = {"n": 0}
    slept: list[float] = []

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _op_error("the database is resuming")
        return "ok"

    assert run_with_db_retry(flaky, base_delay=1.0, _sleep=slept.append) == "ok"
    assert calls["n"] == 3
    assert slept == [1.0, 2.0]  # exponential backoff between the 3 attempts


def test_retry_reraises_non_transient_immediately():
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise _op_error("syntax error")

    with pytest.raises(OperationalError):
        run_with_db_retry(boom, _sleep=lambda _: None)
    assert calls["n"] == 1  # not retried


def test_retry_gives_up_after_budget():
    def always():
        raise _op_error("the database is resuming")

    with pytest.raises(OperationalError):
        run_with_db_retry(always, retries=2, _sleep=lambda _: None)
