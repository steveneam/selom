"""One-time localStorage → Postgres import (step 7c, BE-3, sub-spec §4).

Drives POST /import/local-state with FE-shaped blobs and asserts: the rows land across every table in
dependency order, the cross-list gene-set dedup (createdFrom) holds, and a re-import is idempotent
(no duplicates, the second pass adds nothing).
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from auth.context import AuthContext, get_verifier
from library.repo import LibraryRepo, set_library_repo
from uploads.repo import UploadRepo, set_upload_repo


class _Verifier:
    def verify(self, request) -> AuthContext:  # noqa: ARG002
        return AuthContext(user_id="A", email="a@x.com")


@pytest.fixture
def client(tmp_path):
    from main import app

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'imp.db'}", future=True)
    set_upload_repo(UploadRepo(engine=engine, create=True))
    set_library_repo(LibraryRepo(engine=engine))
    app.dependency_overrides[get_verifier] = lambda: _Verifier()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_verifier, None)
        set_upload_repo(None)
        set_library_repo(None)
        engine.dispose()


_BLOB = {
    "projects": {
        "projects": [{"id": "p1", "name": "PBMC", "color": "#22d3ee"}],
        "datasets": [{"id": "d1", "projectId": "p1", "filename": "pbmc.csv", "modality": "bulk RNA-seq",
                      "currentSha256": "abc", "qc": {"detectedModality": "bulk RNA-seq"}}],
        "figures": [{"id": "f1", "projectId": "p1", "datasetId": "d1", "skillId": "selom.deg",
                     "title": "Volcano", "spec": {"data": [], "layout": {}}, "frozen": True}],
        "installs": [{"id": "i1", "projectId": "p1", "skillId": "selom.deg"}],
        "geneSets": [{"id": "gs1", "name": "Cone", "genes": ["PDE6B"], "createdFrom": "go:1"}],
    },
    "workspace": {
        "papers": [{"id": "paper1", "filename": "loi.pdf", "doi": "10.1/x", "title": "RPGRIP1",
                    "skills": ["deg"], "figureCount": 6,
                    "supplements": [{"id": "s1", "filename": "ST2.xlsx", "kind": "xlsx", "size": 99}]}],
        "geneSets": [{"id": "gs2", "name": "Cone dup", "createdFrom": "go:1"}],  # dup on createdFrom
        "skills": [{"id": "ws1", "skillId": "selom.volcano"}],
    },
}


def test_import_lands_all_rows(client):
    r = client.post("/import/local-state", json=_BLOB)
    assert r.status_code == 200, r.text
    counts = r.json()["imported"]
    assert counts["projects"] == 1
    assert counts["datasets"] == 1
    assert counts["figures"] == 1
    assert counts["installs"] == 2          # 1 project-scoped + 1 workspace-wide
    assert counts["gene_sets"] == 1         # the workspace dup collapsed on createdFrom
    assert counts["papers"] == 1
    assert counts["supplements"] == 1

    assert [p["id"] for p in client.get("/projects").json()["projects"]] == ["p1"]
    figs = client.get("/figures").json()["figures"]
    assert figs[0]["id"] == "f1" and figs[0]["frozen"] is True
    assert client.get("/datasets").json()["datasets"][0]["id"] == "d1"
    assert client.get("/workspace/papers").json()["papers"][0]["supplements"][0]["filename"] == "ST2.xlsx"
    assert len(client.get("/workspace/gene-sets").json()["gene_sets"]) == 1
    assert len(client.get("/skill-installs").json()["installs"]) == 2


def test_import_is_idempotent(client):
    client.post("/import/local-state", json=_BLOB)
    again = client.post("/import/local-state", json=_BLOB).json()["imported"]
    assert all(v == 0 for v in again.values()), again  # nothing new on the second pass
    # and no duplicate rows
    assert len(client.get("/projects").json()["projects"]) == 1
    assert len(client.get("/figures").json()["figures"]) == 1
    assert len(client.get("/workspace/papers").json()["papers"]) == 1


def test_import_empty_is_noop(client):
    r = client.post("/import/local-state", json={})
    assert r.status_code == 200
    assert all(v == 0 for v in r.json()["imported"].values())
