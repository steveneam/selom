"""Task C3 — the /run guards: param-range validation (400) and the exec timeout (504)."""

import time

import pytest
from fastapi.testclient import TestClient

import main
from config import settings
from main import app
from skills.contract import load_skill, validate_param_ranges

client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


_CSV = ("matrix.csv", b"gene,ctrl,treat\nACTB,10,20\nGAPDH,30,40\nB2M,5,8\n", "text/csv")


# --- validate_param_ranges (unit) -------------------------------------------------------------

def test_numeric_out_of_range():
    spec = load_skill("volcano")  # fc_threshold: float, min 0, max 5
    assert validate_param_ranges(spec, {"fc_threshold": "100"})   # > max
    assert validate_param_ranges(spec, {"fc_threshold": "-1"})    # < min
    assert not validate_param_ranges(spec, {"fc_threshold": "3"})  # in range


def test_bad_option_and_type():
    heatmap = load_skill("heatmap")  # cluster: str, options none/row/column/both
    assert validate_param_ranges(heatmap, {"cluster": "diagonal"})
    assert not validate_param_ranges(heatmap, {"cluster": "both"})
    volcano = load_skill("volcano")  # top_n: int
    assert validate_param_ranges(volcano, {"top_n": "abc"})


def test_ignores_unknown_and_reserved():
    spec = load_skill("volcano")
    assert not validate_param_ranges(spec, {"mystery": "x", "_design_path": "/tmp/x"})


# --- /run endpoint ----------------------------------------------------------------------------

def test_run_rejects_out_of_range_param():
    # Validation fires before any heavy work, so this is a clean 400 (not a 422/500 from QC/skill).
    r = client.post("/skills/volcano/run?fc_threshold=100", files={"matrix": _CSV})
    assert r.status_code == 400
    body = r.json()["detail"]
    assert body["error"] == "param_out_of_range"
    assert any("fc_threshold" in m for m in body["errors"])


def test_jobs_submit_rejects_out_of_range_param():
    r = client.post("/skills/volcano/jobs?fc_threshold=100", files={"matrix": _CSV})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "param_out_of_range"


def test_run_happy_path_in_range():
    r = client.post("/skills/volcano/run?fc_threshold=3&override=true", files={"matrix": _CSV})
    assert r.status_code == 200
    assert r.json()["figure"]["data"]


def test_run_times_out_on_a_hung_skill(monkeypatch):
    monkeypatch.setattr(settings, "skill_timeout_s", 1)

    def hang(*args, **kwargs):
        time.sleep(3)
        return {"data": [], "layout": {}}, None

    # main bound these at import, so patch them on the main module (the closure reads the globals).
    monkeypatch.setattr(main, "run_bundle_with_table", hang)
    monkeypatch.setattr(main, "run_skill_with_table", hang)

    r = client.post("/skills/volcano/run?override=true", files={"matrix": _CSV})
    assert r.status_code == 504
    assert r.json()["detail"]["error"] == "skill_timeout"
