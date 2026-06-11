"""B4 reproducibility bundle — provenance unit tests + the /run bundle contract.

The stub engine is forced so this runs with zero heavy deps, like the golden tests.
"""

import hashlib

import pytest
from fastapi.testclient import TestClient

import provenance
from main import app
from skills.contract import load_skill

client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def test_sha256_file_matches_hashlib(tmp_path):
    blob = b"some bytes\x00\x01pretending to be an h5ad"
    f = tmp_path / "matrix.h5ad"
    f.write_bytes(blob)
    assert provenance.sha256_file(str(f)) == hashlib.sha256(blob).hexdigest()


def test_environment_snapshot_shape():
    env = provenance.environment_snapshot()
    assert env["python"] and env["platform"]
    assert env["engine_policy"] == "stub"
    assert isinstance(env["packages"], dict)


def test_build_records_typed_params_and_input(tmp_path):
    blob = b"x" * 128
    f = tmp_path / "demo.h5ad"
    f.write_bytes(blob)
    spec = load_skill("cluster")
    # Raw query-style param (a string) must land in the bundle coerced to its type.
    bundle = provenance.build(spec, str(f), "demo.h5ad", {"resolution": "1.5"})

    assert bundle["skill"] == {
        "id": "cluster",
        "version": spec.version,
        "title": spec.title,
        "engine": "python",
    }
    assert bundle["params"]["resolution"] == 1.5  # coerced float, not "1.5"
    assert bundle["params"]["n_pcs"] == 50  # default filled in
    assert bundle["input"]["filename"] == "demo.h5ad"
    assert bundle["input"]["sha256"] == hashlib.sha256(blob).hexdigest()
    assert bundle["input"]["n_bytes"] == 128


def test_run_endpoint_returns_figure_provenance_methods():
    res = client.post(
        "/skills/cluster/run?resolution=2.0",
        files={"matrix": ("demo.h5ad", b"dummy", "application/octet-stream")},
    )
    assert res.status_code == 200
    body = res.json()
    assert set(body) >= {"figure", "provenance", "methods"}
    assert body["figure"]["data"]
    assert body["provenance"]["params"]["resolution"] == 2.0
    assert body["provenance"]["input"]["sha256"]
    assert "resolution 2.0" in body["methods"]["text"]
