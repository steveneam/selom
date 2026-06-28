"""Figures CRUD + client-authoritative project ids (AWS materialization step 7c, BE-1).

Drives the real HTTP surface through ``TestClient`` against a SQLite ``UploadRepo`` + ``LibraryRepo``
sharing ONE engine (so a figure can reference a real project row), a switchable verifier for the
tenant-isolation gate, and the dev auth seam. Covers: the client-supplied project id (honoured +
idempotent + back-compat), figure CRUD, idempotent figure upsert, the unknown-project 404, and that
a second tenant can't see/patch/delete the first's figure (the §6.4 isolation gate, extended).

A *file*-backed SQLite URL (not ``sqlite://`` memory) is deliberate — a sync FastAPI handler runs on
an anyio worker thread, so an in-memory DB (per-connection) wouldn't be visible to the request (same
reason as ``test_uploads.py``).
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from auth.context import AuthContext, get_verifier
from library.repo import LibraryRepo, set_library_repo
from uploads.repo import UploadRepo, set_upload_repo


class _SwitchVerifier:
    def __init__(self, user_id: str = "A") -> None:
        self.user_id = user_id

    def verify(self, request) -> AuthContext:  # noqa: ARG002
        return AuthContext(user_id=self.user_id, email=f"{self.user_id}@x.com")


@pytest.fixture
def env(tmp_path):
    from main import app

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'lib.db'}", future=True)
    set_upload_repo(UploadRepo(engine=engine, create=True))
    set_library_repo(LibraryRepo(engine=engine))  # same engine → shares the schema create_all above
    verifier = _SwitchVerifier("A")
    app.dependency_overrides[get_verifier] = lambda: verifier
    try:
        yield TestClient(app), verifier
    finally:
        app.dependency_overrides.pop(get_verifier, None)
        set_upload_repo(None)
        set_library_repo(None)
        engine.dispose()


def _project(client, *, name="P1", pid=None) -> str:
    body = {"name": name}
    if pid is not None:
        body["id"] = pid
    r = client.post("/projects", json=body)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _figure(client, project_id, *, fid="f_abc", title="UMAP", **extra) -> dict:
    body = {"id": fid, "project_id": project_id, "title": title, **extra}
    r = client.post("/figures", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ── client-authoritative project ids ──────────────────────────────────────────────────────────
def test_project_honours_client_id(env):
    client, _ = env
    pid = _project(client, pid="p_client123")
    assert pid == "p_client123"


def test_project_without_id_server_mints(env):
    client, _ = env
    pid = _project(client)  # no id → server mints (step-6 back-compat)
    assert pid and pid != ""


def test_project_create_is_idempotent_on_id(env):
    client, _ = env
    _project(client, pid="p_dup", name="First")
    # a retried optimistic write with the same id returns the existing row, no duplicate
    pid2 = _project(client, pid="p_dup", name="Second")
    assert pid2 == "p_dup"
    r = client.get("/projects")
    ids = [p["id"] for p in r.json()["projects"]]
    assert ids.count("p_dup") == 1


# ── figure CRUD ───────────────────────────────────────────────────────────────────────────────
def test_figure_create_get_round_trips(env):
    client, _ = env
    pid = _project(client, pid="p1")
    fig = _figure(client, pid, fid="f1", title="Volcano",
                  spec={"data": [], "layout": {}}, frozen=False,
                  guardrails=[{"level": "info", "msg": "ok"}])
    assert fig["id"] == "f1"
    assert fig["project_id"] == "p1"
    assert fig["guardrails"] == [{"level": "info", "msg": "ok"}]

    got = client.get("/figures/f1")
    assert got.status_code == 200
    assert got.json()["spec"] == {"data": [], "layout": {}}


def test_figure_list_scoped_by_project(env):
    client, _ = env
    p1 = _project(client, pid="p1")
    p2 = _project(client, pid="p2", name="P2")
    _figure(client, p1, fid="f1")
    _figure(client, p2, fid="f2")
    all_figs = client.get("/figures").json()["figures"]
    assert {f["id"] for f in all_figs} == {"f1", "f2"}
    only_p1 = client.get("/figures", params={"project_id": "p1"}).json()["figures"]
    assert {f["id"] for f in only_p1} == {"f1"}


def test_figure_patch_updates_only_given_fields(env):
    client, _ = env
    pid = _project(client, pid="p1")
    _figure(client, pid, fid="f1", title="Old", spec={"data": [1]}, frozen=False)
    r = client.patch("/figures/f1", json={"frozen": True, "title": "New"})
    assert r.status_code == 200
    body = r.json()
    assert body["frozen"] is True
    assert body["title"] == "New"
    assert body["spec"] == {"data": [1]}  # untouched (not in the patch)


def test_figure_upsert_is_idempotent(env):
    client, _ = env
    pid = _project(client, pid="p1")
    _figure(client, pid, fid="f1", title="One")
    _figure(client, pid, fid="f1", title="Two")  # re-POST same id → update, not duplicate
    figs = client.get("/figures").json()["figures"]
    assert len(figs) == 1
    assert figs[0]["title"] == "Two"


def test_figure_fork_is_just_a_create_with_parent(env):
    client, _ = env
    pid = _project(client, pid="p1")
    _figure(client, pid, fid="f1", title="Parent")
    fork = _figure(client, pid, fid="f2", title="Parent", parent_figure_id="f1",
                   variant_label="edited copy")
    assert fork["parent_figure_id"] == "f1"
    assert fork["variant_label"] == "edited copy"


def test_figure_delete(env):
    client, _ = env
    pid = _project(client, pid="p1")
    _figure(client, pid, fid="f1")
    assert client.delete("/figures/f1").status_code == 200
    assert client.get("/figures/f1").status_code == 404
    assert client.delete("/figures/f1").status_code == 404  # already gone


def test_figure_on_unknown_project_404(env):
    client, _ = env
    r = client.post("/figures", json={"id": "f1", "project_id": "nope", "title": "X"})
    assert r.status_code == 404


# ── tenant isolation (the §6.4 gate, extended to figures) ──────────────────────────────────────
def test_figure_isolation_across_tenants(env):
    client, verifier = env
    pid = _project(client, pid="p1")
    _figure(client, pid, fid="f1", title="A's figure")

    verifier.user_id = "B"  # switch tenant
    assert client.get("/figures/f1").status_code == 404           # can't read
    assert client.patch("/figures/f1", json={"frozen": True}).status_code == 404  # can't patch
    assert client.delete("/figures/f1").status_code == 404        # can't delete
    assert client.get("/figures").json()["figures"] == []         # not in B's list
    # B can't even create a figure under A's project (the project isn't B's)
    assert client.post("/figures", json={"id": "fb", "project_id": "p1", "title": "x"}).status_code == 404

    verifier.user_id = "A"  # back to the owner — still intact
    assert client.get("/figures/f1").status_code == 200
