"""Presigned upload + datasets + projects (materialization step 6, spec §4.2/§6/§12).

Drives the real HTTP surface through ``TestClient`` against a SQLite-backed ``UploadRepo`` and a
filesystem ``LocalObjectStore`` (the dev seam — a faithful prod stand-in, plan D6). Covers the
three-step flow (intake → PUT → confirm), the server-side leak-free parse, quota gating, and the
T1 isolation gate (the tenant is the verified claim, never input).

A *file*-backed SQLite URL (not ``sqlite://`` memory) is deliberate: a sync FastAPI handler runs on
an anyio worker thread, so an in-memory DB (per-connection) wouldn't be visible to the request.
"""

from __future__ import annotations

import sqlalchemy as sa
import pytest
from fastapi.testclient import TestClient

from auth.context import AuthContext, get_verifier
from storage.object_store import LocalObjectStore, set_object_store
from uploads.repo import UploadRepo, set_upload_repo


class _SwitchVerifier:
    def __init__(self, user_id: str = "A") -> None:
        self.user_id = user_id

    def verify(self, request) -> AuthContext:  # noqa: ARG002
        return AuthContext(user_id=self.user_id, email=f"{self.user_id}@x.com")


@pytest.fixture
def env(tmp_path):
    from main import app

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'up.db'}", future=True)
    repo = UploadRepo(engine=engine, create=True)
    set_upload_repo(repo)
    store = LocalObjectStore(tmp_path / "obj")
    set_object_store(store)
    verifier = _SwitchVerifier("A")
    app.dependency_overrides[get_verifier] = lambda: verifier
    try:
        yield TestClient(app), verifier, repo, store, engine
    finally:
        app.dependency_overrides.pop(get_verifier, None)
        set_upload_repo(None)
        set_object_store(None)
        engine.dispose()


def _project(client, name="P1") -> str:
    r = client.post("/projects", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _intake(client, pid, *, filename="data.csv", size=100, sha=None, **extra):
    body = {"project_id": pid, "filename": filename, "size_bytes": size, "content_sha256": sha, **extra}
    return client.post("/uploads/intake", json=body)


# --- the happy path: intake → PUT → confirm → parse -------------------------------------------

def test_full_upload_and_parse(env):
    client, _v, _repo, store, _eng = env
    pid = _project(client)
    csv = b"gene,ctrl,treat\nACTB,10,20\nGAPDH,30,40\n"

    r = _intake(client, pid, filename="counts.csv", size=len(csv))
    assert r.status_code == 200, r.text
    body = r.json()
    ds = body["dataset"]
    assert ds["status"] == "pending_upload"
    key = ds["upload_s3_key"]
    assert key.startswith(f"uploads/A/{pid}/{ds['id']}/")
    # the local presign points at the in-app PUT route (dev stand-in for the S3 direct PUT)
    assert body["upload"]["url"] == f"/uploads/local/{key}"

    # PUT the bytes straight to the (local) store, bypassing any handler buffer
    assert client.put(body["upload"]["url"], content=csv).status_code == 200
    assert store.get_bytes(key) == csv

    # confirm: server heads the object + flips ready, stamping the REAL size
    r = client.post(f"/uploads/{ds['id']}/confirm", json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready"
    assert r.json()["size_bytes"] == len(csv)

    # parse: server-side, leak-free → data/{sha}.csv pointer stamped
    r = client.post(f"/uploads/{ds['id']}/parse")
    assert r.status_code == 200, r.text
    parsed = r.json()
    assert parsed["parquet_s3_key"] and parsed["parquet_s3_key"].startswith("data/")
    assert parsed["parquet_s3_key"].endswith(".csv")  # CSV until the parquet substrate lands (Q5)
    assert store.get_bytes(parsed["parquet_s3_key"]) is not None
    assert parsed["current_sha256"]  # authoritative raw-bytes hash recomputed at parse


def test_confirm_before_upload_is_409(env):
    client, _v, _repo, _store, _eng = env
    pid = _project(client)
    ds = _intake(client, pid, size=10).json()["dataset"]
    # no PUT happened → the object isn't in the store → confirm can't flip it ready
    assert client.post(f"/uploads/{ds['id']}/confirm", json={}).status_code == 409


def test_intake_rejects_zero_size(env):
    client, _v, _repo, _store, _eng = env
    pid = _project(client)
    assert _intake(client, pid, size=0).status_code == 400


def test_intake_unknown_project_is_404(env):
    client, _v, _repo, _store, _eng = env
    assert _intake(client, "no-such-project", size=10).status_code == 404


def test_local_put_rejects_non_uploads_key(env):
    client, _v, _repo, _store, _eng = env
    assert client.put("/uploads/local/data/evil.csv", content=b"x").status_code == 400


# --- quota (spec §12) -------------------------------------------------------------------------

def test_project_quota(env):
    client, _v, _repo, _store, _eng = env
    for i in range(3):  # default max_projects = 3
        assert client.post("/projects", json={"name": f"P{i}"}).status_code == 200
    r = client.post("/projects", json={"name": "P4"})
    assert r.status_code == 402
    assert r.json()["detail"]["limit"] == "max_projects"


def test_storage_quota_blocks_oversized_intake(env):
    client, _v, _repo, _store, engine = env
    pid = _project(client)
    from db.schema import users

    with engine.begin() as conn:  # tighten this tenant's storage cap, then exceed it
        conn.execute(sa.update(users).where(users.c.user_id == "A").values(max_storage_bytes=50))
    r = _intake(client, pid, size=100)
    assert r.status_code == 402
    assert r.json()["detail"]["limit"] == "max_storage_bytes"


# --- T1 cross-tenant isolation (the tenant is the verified claim, never input) -----------------

def test_dataset_invisible_to_other_tenant(env):
    client, verifier, _repo, _store, _eng = env
    verifier.user_id = "A"
    pid = _project(client, "A-proj")
    ds = _intake(client, pid, size=10).json()["dataset"]

    verifier.user_id = "B"
    assert client.get(f"/datasets/{ds['id']}").status_code == 404      # can't read A's dataset
    assert client.get("/datasets").json()["datasets"] == []           # sees none of A's
    assert client.get("/projects").json()["projects"] == []           # sees none of A's projects
    assert _intake(client, pid, size=10).status_code == 404           # can't upload into A's project
    assert client.post(f"/uploads/{ds['id']}/confirm", json={}).status_code == 404


def test_body_user_id_is_ignored(env):
    client, verifier, _repo, _store, _eng = env
    verifier.user_id = "A"
    pid = _project(client)
    # a forged user_id in the body must NOT change ownership — Pydantic drops the unknown field and
    # the repo forces the verified tenant regardless (spec §6.1/§6.2).
    ds = _intake(client, pid, size=10, user_id="B").json()["dataset"]
    verifier.user_id = "B"
    assert client.get(f"/datasets/{ds['id']}").status_code == 404  # still A's
    verifier.user_id = "A"
    assert client.get(f"/datasets/{ds['id']}").status_code == 200


def test_list_datasets_filtered_by_project(env):
    client, _v, _repo, _store, _eng = env
    p1, p2 = _project(client, "P1"), _project(client, "P2")
    _intake(client, p1, filename="a.csv", size=10)
    _intake(client, p2, filename="b.csv", size=10)
    assert len(client.get("/datasets").json()["datasets"]) == 2
    only_p1 = client.get(f"/datasets?project_id={p1}").json()["datasets"]
    assert len(only_p1) == 1 and only_p1[0]["project_id"] == p1
