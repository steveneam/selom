"""P1c "is-my-data-clean?" guardrail on POST /skills/{id}/run (engine-spine spec §5, E3/D-e5).

A block-severity QC problem warns + REQUIRES an explicit override rather than silently producing a
misleading figure — the native moat for non-bioinformaticians. The verdict (kind + QC + suggested
pipeline) rides along on every successful run as ``data_check`` (P1c/P3a surfaced for own data).
Fail-soft: an upload the engine can't inspect runs the path-based way, never blocked. Stub engine.
"""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

# Negative integers auto-classify as bulk_counts -> negative_counts is a BLOCK-severity flag.
_NEG_COUNTS = b"gene,s0,s1,s2\ng1,-5,3,4\ng2,2,3,4\n"
# Clean integer counts, >=2 samples, no all-zero rows -> ok=True.
_CLEAN_COUNTS = b"gene,s0,s1,s2,s3\n" + b"".join(
    f"g{i},{i + 1},{i + 2},{i + 3},{i + 4}\n".encode() for i in range(10)
)


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def test_block_severity_halts_with_a_structured_qc_verdict():
    r = client.post("/skills/deg/run", files={"matrix": ("counts.csv", _NEG_COUNTS, "text/csv")})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "data_check_failed"
    assert detail["kind"] == "bulk_counts"
    assert detail["qc"]["blocked"] is True
    flags = detail["qc"]["flags"]
    assert any(f["code"] == "negative_counts" for f in flags)
    assert any(f["fix"] for f in flags)            # a fix hint always rides along (E3)


def test_override_runs_the_analysis_anyway():
    r = client.post(
        "/skills/deg/run?override=true",
        files={"matrix": ("counts.csv", _NEG_COUNTS, "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["figure"]["data"]
    assert body["data_check"]["qc"]["blocked"] is True   # still reported, just not enforced
    assert "override" not in body["provenance"]["params"]  # popped — never reaches skill/provenance


def test_clean_data_passes_and_surfaces_the_verdict_plus_routing():
    r = client.post("/skills/deg/run", files={"matrix": ("counts.csv", _CLEAN_COUNTS, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    dc = body["data_check"]
    assert dc["kind"] == "bulk_counts"
    assert dc["qc"]["ok"] is True and dc["qc"]["blocked"] is False
    # P3 guidance: the suggested pipeline for this modality rides along.
    assert "deg" in [s["skill_id"] for s in dc["routing"]["steps"]]
    # Slice 2 (product-agnostic): the data-fit verdict for THIS skill on the user's own data.
    assert body["data_fit"]["confidence"] == "confident" and body["data_fit"]["skill_id"] == "deg"


def test_uninspectable_upload_is_fail_soft():
    # A placeholder upload (non-h5ad bytes named .h5ad) can't be ingested -> the guardrail is
    # skipped and the run proceeds exactly as before (the proven path is never broken).
    r = client.post(
        "/skills/cluster/run",
        files={"matrix": ("demo.h5ad", b"dummy", "application/octet-stream")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["figure"]["data"]
    assert body["data_check"] == {"kind": "unknown", "qc": None, "routing": None}
    assert body["data_fit"] is None            # no bundle to score → honest null (Slice 2)
