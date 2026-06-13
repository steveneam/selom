"""POST /run optional `design` upload — accepted, and kept out of the provenance record.

The bulk/time-course DE skills take an optional design sheet (sample->condition/time).
This checks the wire contract: the endpoint accepts the extra multipart field, still
returns the full publish-confidence bundle, and the reserved ``_design_path`` it threads
to the runner never leaks into the reproducibility params. Stub engine, zero heavy deps.
"""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def test_run_accepts_design_and_hides_it_from_provenance():
    r = client.post(
        "/skills/deg/run?mode=bulk&reference=ctrl&treatment=treat",
        files={
            "matrix": ("counts.csv", b"GeneID,ctrl_1,ctrl_2,treat_1,treat_2\ng1,5,6,30,33\n", "text/csv"),
            "design": ("design.csv", b"SampleID,grp\nctrl_1,ctrl\ntreat_1,treat\n", "text/csv"),
        },
    )
    assert r.status_code == 200
    bundle = r.json()
    assert isinstance(bundle["figure"]["data"], list) and bundle["figure"]["data"]
    assert bundle["provenance"]["skill"]["id"] == "deg"
    # Reserved runtime key must not appear in the recorded config.
    assert "_design_path" not in bundle["provenance"]["params"]
    assert bundle["provenance"]["params"]["reference"] == "ctrl"
    assert bundle["guardrails"] is not None


def test_run_without_design_still_works():
    r = client.post(
        "/skills/deg/run",
        files={"matrix": ("counts.csv", b"GeneID,a_1,a_2\ng1,5,6\n", "text/csv")},
    )
    assert r.status_code == 200
    assert "_design_path" not in r.json()["provenance"]["params"]
