"""POST /skills/{id}/run — honest error surfacing (T6 finding #6).

A runner raises ``ValueError`` for a DATA problem (missing columns, no groups, an empty result).
That must reach the user as a 4xx with the real message — NOT a generic 5xx "service unavailable".
Real engine, so the skill actually validates its input.
"""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_real(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "real")


def test_missing_columns_surfaces_real_cause_as_400():
    # A plain table lacks the condition/intensity/b-wave columns erg_intensity_response needs.
    csv = b"a,b,c\n1,2,3\n4,5,6\n"
    r = client.post(
        "/skills/erg_intensity_response/run",
        files={"matrix": ("plain.csv", csv, "text/csv")},
    )
    assert r.status_code == 400               # a data error, not a 500 outage
    detail = r.json()["detail"]
    assert "required columns" in detail        # the real cause, surfaced verbatim
    assert "b_wave_uv" in detail


def test_valid_erg_table_runs_through_the_run_endpoint():
    # The same skill on a real long-format ERG table returns a figure end-to-end (no 400/500).
    rows = b"".join(
        f"e1,Control,1,LE,G{i},{lv},{200 - i*10},{60 - i*5},N\n".encode()
        for i, lv in enumerate([-1.7, -0.8, 0.1, 1.0, 1.9])
    )
    csv = (b"sample_id,condition,animal,eye,intensity_group,intensity_log_cd_s_m2,"
           b"b_wave_uv,a_wave_uv,qc_excluded\n") + rows
    r = client.post(
        "/skills/erg_intensity_response/run",
        files={"matrix": ("erg_metrics_long.csv", csv, "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["figure"]["data"]
    # The layered data-type label + empty cleaning plan ride along on the run too.
    assert body["data_check"]["profile"]["code"] == "erg"
    assert body["data_check"]["cleaning_plan"]["applies"] is False
