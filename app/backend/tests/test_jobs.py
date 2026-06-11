"""Async job API (B3) — inline lifecycle, result fetch, SSE, and error paths.

Exercises the default inline + local-filesystem path (no Redis/R2). The stub engine
is forced so this runs with zero heavy deps, like the golden tests.
"""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def _submit(skill: str = "cluster"):
    return client.post(
        f"/skills/{skill}/jobs",
        files={"matrix": ("x.h5ad", b"dummy", "application/octet-stream")},
    )


def test_inline_job_completes_and_stores_result():
    job = _submit().json()
    assert job["skill_id"] == "cluster"
    # Inline mode runs the job to completion before the request returns.
    assert job["status"] == "succeeded"
    assert job["result_url"]

    # The poll endpoint agrees with the submit response.
    assert client.get(f"/jobs/{job['id']}").json()["status"] == "succeeded"

    # The stored result is the full B4 bundle, fetchable like /run's output.
    res = client.get(f"/jobs/{job['id']}/result")
    assert res.status_code == 200
    bundle = res.json()
    fig = bundle["figure"]
    assert isinstance(fig["data"], list) and fig["data"]
    assert isinstance(fig["layout"], dict)
    # Reproducibility bundle + methods-text ride along (publish-confidence).
    assert bundle["provenance"]["skill"]["id"] == "cluster"
    assert bundle["provenance"]["input"]["sha256"]
    assert "Leiden" in bundle["methods"]["text"]
    assert bundle["methods"]["citations"]


def test_sse_emits_terminal_state():
    job = _submit().json()
    r = client.get(f"/jobs/{job['id']}/events")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "succeeded" in r.text


def test_unknown_skill_is_404():
    r = client.post(
        "/skills/not_a_skill/jobs",
        files={"matrix": ("x.h5ad", b"d", "application/octet-stream")},
    )
    assert r.status_code == 404


def test_unknown_job_is_404():
    assert client.get("/jobs/deadbeef").status_code == 404
    assert client.get("/jobs/deadbeef/result").status_code == 404
