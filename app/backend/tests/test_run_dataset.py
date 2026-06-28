"""Run-from-dataset_id (step 7c, BE-3, sub-spec §5).

The bytes are already in the object store from the upload flow, so a run reads them by dataset_id —
no multipart re-upload. Proves: the dataset bytes flow through the SAME pipeline as multipart /run
(real ingest/classify even under the stub skill engine → matching data_check), an unknown dataset is
404, and a dataset whose object never landed is 409. Stub skill engine (the run plumbing, not skill
correctness, is under test).
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from auth.context import AuthContext, get_verifier
from library.repo import LibraryRepo, set_library_repo
from storage.object_store import LocalObjectStore, set_object_store
from uploads.repo import UploadRepo, set_upload_repo

# Clean integer counts → classifies as bulk_counts, runs clean (mirrors test_run_guardrail).
_CLEAN_COUNTS = b"gene,s0,s1,s2,s3\n" + b"".join(
    f"g{i},{i + 1},{i + 2},{i + 3},{i + 4}\n".encode() for i in range(10)
)


class _Verifier:
    def verify(self, request) -> AuthContext:  # noqa: ARG002
        return AuthContext(user_id="A", email="a@x.com")


@pytest.fixture(autouse=True)
def _stub_engine(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


@pytest.fixture
def client(tmp_path):
    from main import app

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'rd.db'}", future=True)
    set_upload_repo(UploadRepo(engine=engine, create=True))
    set_library_repo(LibraryRepo(engine=engine))
    set_object_store(LocalObjectStore(tmp_path / "obj"))
    app.dependency_overrides[get_verifier] = lambda: _Verifier()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_verifier, None)
        set_upload_repo(None)
        set_library_repo(None)
        set_object_store(None)
        engine.dispose()


def _uploaded_dataset(client, data=_CLEAN_COUNTS, filename="counts.csv") -> str:
    """Run the real upload flow (intake → PUT → confirm) and return the ready dataset id."""
    pid = client.post("/projects", json={"name": "P", "id": "p1"}).json()["id"]
    intake = client.post("/uploads/intake", json={
        "project_id": pid, "filename": filename, "size_bytes": len(data)}).json()
    ds_id = intake["dataset"]["id"]
    key = intake["dataset"]["upload_s3_key"]  # server-derived key; the dev PUT route mirrors the S3 PUT
    put = client.put(f"/uploads/local/{key}", content=data)
    assert put.status_code == 200, put.text
    assert client.post(f"/uploads/{ds_id}/confirm", json={}).status_code == 200
    return ds_id


def test_run_dataset_runs_on_stored_bytes(client):
    ds_id = _uploaded_dataset(client)
    r = client.post("/skills/deg/run-dataset", json={"dataset_id": ds_id})
    assert r.status_code == 200, r.text
    body = r.json()
    # the real bytes were ingested + classified (not a blank run): the clean counts read as bulk_counts
    assert body["data_check"]["kind"] == "bulk_counts"
    assert body["figure"] and isinstance(body["figure"]["data"], list)


def test_run_dataset_matches_multipart_on_same_bytes(client):
    ds_id = _uploaded_dataset(client)
    by_id = client.post("/skills/deg/run-dataset", json={"dataset_id": ds_id}).json()
    multipart = client.post(
        "/skills/deg/run", files={"matrix": ("counts.csv", _CLEAN_COUNTS, "text/csv")}).json()
    # same skill + same bytes → identical figure + same provenance input hash (staleness goes live)
    assert by_id["figure"] == multipart["figure"]
    assert by_id["provenance"]["input"]["sha256"] == multipart["provenance"]["input"]["sha256"]


def test_run_dataset_unknown_dataset_404(client):
    r = client.post("/skills/deg/run-dataset", json={"dataset_id": "nope"})
    assert r.status_code == 404


def test_run_dataset_no_object_409(client):
    # intake creates the row + key but we never PUT/confirm → the object never landed → 409
    pid = client.post("/projects", json={"name": "P", "id": "p1"}).json()["id"]
    ds_id = client.post("/uploads/intake", json={
        "project_id": pid, "filename": "x.csv", "size_bytes": 10}).json()["dataset"]["id"]
    r = client.post("/skills/deg/run-dataset", json={"dataset_id": ds_id})
    assert r.status_code == 409
