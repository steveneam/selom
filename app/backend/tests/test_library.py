"""Account library: gene sets, saved papers (+supplements), skill installs (step 7c, BE-2).

Same harness as ``test_figures.py`` — ``UploadRepo`` + ``LibraryRepo`` on one SQLite engine + a
switchable verifier. Covers the idempotency contracts (client id / dedup key / scope), the
whole-paper-upsert supplement reconcile, project- vs workspace-scoped installs, and tenant isolation.
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
    set_library_repo(LibraryRepo(engine=engine))
    verifier = _SwitchVerifier("A")
    app.dependency_overrides[get_verifier] = lambda: verifier
    try:
        yield TestClient(app), verifier
    finally:
        app.dependency_overrides.pop(get_verifier, None)
        set_upload_repo(None)
        set_library_repo(None)
        engine.dispose()


def _project(client, *, pid="p1", name="P1") -> str:
    r = client.post("/projects", json={"name": name, "id": pid})
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ── workspace ──────────────────────────────────────────────────────────────────────────────────
def test_workspace_autocreated(env):
    client, _ = env
    r = client.get("/workspace")
    assert r.status_code == 200
    assert r.json()["id"]  # provisioned on first read


# ── gene sets ────────────────────────────────────────────────────────────────────────────────
def test_gene_set_save_list_delete(env):
    client, _ = env
    r = client.post("/workspace/gene-sets", json={
        "id": "gs1", "name": "Cone genes", "genes": ["PDE6B", "RPGRIP1"],
        "source": "go", "source_label": "GO", "license": "CC-BY", "created_from": "go:0001",
    })
    assert r.status_code == 200, r.text
    assert r.json()["genes"] == ["PDE6B", "RPGRIP1"]
    assert {g["id"] for g in client.get("/workspace/gene-sets").json()["gene_sets"]} == {"gs1"}
    assert client.delete("/workspace/gene-sets/gs1").status_code == 200
    assert client.get("/workspace/gene-sets").json()["gene_sets"] == []


def test_gene_set_dedup_on_created_from(env):
    client, _ = env
    client.post("/workspace/gene-sets", json={"id": "gs1", "name": "A", "created_from": "go:1"})
    client.post("/workspace/gene-sets", json={"id": "gs2", "name": "B", "created_from": "go:1"})
    sets = client.get("/workspace/gene-sets").json()["gene_sets"]
    assert len(sets) == 1  # same source catalog id collapses to one entry


# ── papers + supplements ───────────────────────────────────────────────────────────────────────
def test_paper_save_with_supplements_round_trips(env):
    client, _ = env
    body = {
        "id": "paper1", "filename": "loi2025.pdf", "doi": "10.1/x", "title": "RPGRIP1",
        "authors": ["Loi"], "skills": ["deg", "volcano"], "figure_count": 6,
        "tier_summary": {"structured": 4, "recovered": 2},
        "supplements": [{"id": "s1", "filename": "ST2.xlsx", "kind": "xlsx", "size": 1024}],
    }
    r = client.post("/workspace/papers", json=body)
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["skills"] == ["deg", "volcano"]
    assert len(saved["supplements"]) == 1
    assert saved["supplements"][0]["filename"] == "ST2.xlsx"


def test_paper_dedup_on_doi(env):
    client, _ = env
    client.post("/workspace/papers", json={"id": "p1", "filename": "a.pdf", "doi": "10.1/x"})
    client.post("/workspace/papers", json={"id": "p2", "filename": "b.pdf", "doi": "10.1/x"})
    papers = client.get("/workspace/papers").json()["papers"]
    assert len(papers) == 1  # same DOI updates in place


def test_paper_supplement_reconcile_add_and_remove(env):
    client, _ = env
    client.post("/workspace/papers", json={
        "id": "p1", "filename": "a.pdf",
        "supplements": [{"id": "s1", "filename": "one.csv", "kind": "csv"}],
    })
    # re-upsert with s1 removed + s2 added → the set is reconciled to {s2}
    r = client.post("/workspace/papers", json={
        "id": "p1", "filename": "a.pdf",
        "supplements": [{"id": "s2", "filename": "two.csv", "kind": "csv"}],
    })
    supps = {s["id"] for s in r.json()["supplements"]}
    assert supps == {"s2"}


def test_paper_delete(env):
    client, _ = env
    client.post("/workspace/papers", json={"id": "p1", "filename": "a.pdf"})
    assert client.delete("/workspace/papers/p1").status_code == 200
    assert client.get("/workspace/papers/p1").status_code == 404


# ── skill installs (project- + workspace-scoped) ────────────────────────────────────────────────
def test_install_project_scoped(env):
    client, _ = env
    pid = _project(client, pid="p1")
    r = client.post("/skill-installs", json={"skill_id": "deg", "project_id": pid})
    assert r.status_code == 200, r.text
    assert r.json()["project_id"] == "p1"
    installs = client.get("/skill-installs", params={"project_id": "p1"}).json()["installs"]
    assert {i["skill_id"] for i in installs} == {"deg"}


def test_install_workspace_wide(env):
    client, _ = env
    r = client.post("/skill-installs", json={"skill_id": "volcano"})  # no project → workspace-wide
    assert r.status_code == 200, r.text
    assert r.json()["project_id"] is None
    assert r.json()["workspace_id"]


def test_install_is_idempotent_per_scope(env):
    client, _ = env
    pid = _project(client, pid="p1")
    client.post("/skill-installs", json={"skill_id": "deg", "project_id": pid})
    client.post("/skill-installs", json={"skill_id": "deg", "project_id": pid})  # re-install
    installs = client.get("/skill-installs", params={"project_id": "p1"}).json()["installs"]
    assert len(installs) == 1


def test_install_unknown_project_404(env):
    client, _ = env
    r = client.post("/skill-installs", json={"skill_id": "deg", "project_id": "nope"})
    assert r.status_code == 404


def test_uninstall(env):
    client, _ = env
    pid = _project(client, pid="p1")
    client.post("/skill-installs", json={"skill_id": "deg", "project_id": pid})
    r = client.delete("/skill-installs", params={"skill_id": "deg", "project_id": "p1"})
    assert r.status_code == 200 and r.json()["removed"] == 1
    assert client.get("/skill-installs", params={"project_id": "p1"}).json()["installs"] == []


def test_install_workspace_wide_no_cross_tenant_collision(env):
    """Two tenants both installing the same skill workspace-wide must NOT collide on the functional
    unique COALESCE(project_id, workspace_id) — each carries its own (unique) workspace_id."""
    client, verifier = env
    a = client.post("/skill-installs", json={"skill_id": "deg"})
    assert a.status_code == 200
    verifier.user_id = "B"
    b = client.post("/skill-installs", json={"skill_id": "deg"})
    assert b.status_code == 200, b.text  # would IntegrityError if workspace_id were null for both


# ── tenant isolation ────────────────────────────────────────────────────────────────────────────
def test_library_isolation_across_tenants(env):
    client, verifier = env
    client.post("/workspace/gene-sets", json={"id": "gs1", "name": "A"})
    client.post("/workspace/papers", json={"id": "p1", "filename": "a.pdf"})

    verifier.user_id = "B"
    assert client.get("/workspace/gene-sets").json()["gene_sets"] == []
    assert client.get("/workspace/papers").json()["papers"] == []
    assert client.get("/workspace/papers/p1").status_code == 404
    assert client.delete("/workspace/gene-sets/gs1").status_code == 404
