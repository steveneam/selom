"""Reproduction-run store + the live-reproduction endpoints (Phase 2).

The drive itself is exercised in test_reproduction_drive; here we test the run lifecycle + the
multipart routes + SSE with an INJECTED drive (a canned DriveResult), so the suite stays stack-free
and never touches a real PDF or skill.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient

import config
import reproduction as R
import reproduction_runs
from jobs.store import JobStatus
from main import app
from reproduction_drive import DriveResult, PanelDrive

client = TestClient(app)


def _canned_result():
    panel = R.Panel(paper_id="t", figure="4", panel="", skill_id="volcano",
                    golden=[R.Golden(metric="de_total", value=2)])
    ledger = R.Ledger(paper=R.Paper(id="t", slug="t", title="Test paper"), panels=[panel])
    val = R.validate_panel(panel, {"de_total": 2}, run_id="r1")
    ledger.validations.append(val)
    ledger.scorecard = R.build_scorecard(ledger)
    drives = [PanelDrive(panel_key="4", status="driven", skill_id="volcano", metrics_read=["de_total"])]
    return DriveResult(ledger=ledger, panel_drives=drives)


def _fake_drive(main_path, supplement_paths, **kw):
    return _canned_result()


def _raising_drive(main_path, supplement_paths, **kw):
    raise RuntimeError("ingest blew up")


# --- run store lifecycle ------------------------------------------------------


def test_start_run_succeeds_and_stores_ledger():
    rec = reproduction_runs.start_run("m.pdf", ["d.csv"], paper_id="p", drive_fn=_fake_drive)
    assert rec.status == JobStatus.SUCCEEDED
    assert rec.ledger is not None and rec.ledger.scorecard is not None
    assert reproduction_runs.get_run(rec.id) is not None


def test_start_run_records_failure_never_raises():
    rec = reproduction_runs.start_run("m.pdf", [], drive_fn=_raising_drive)
    assert rec.status == JobStatus.FAILED and "ingest blew up" in (rec.error or "")
    assert rec.ledger is None


def test_public_light_omits_ledger():
    rec = reproduction_runs.start_run("m.pdf", [], drive_fn=_fake_drive)
    light = reproduction_runs.public(rec, light=True)
    full = reproduction_runs.public(rec)
    assert "ledger" not in light and light["status"] == "succeeded"
    assert full["ledger"]["paper"]["title"] == "Test paper" and full["scorecard"] is not None


# --- routes -------------------------------------------------------------------


def _multipart(main_bytes=b"%PDF-1.4 test", supp=None):
    files = [("main", ("paper.pdf", io.BytesIO(main_bytes), "application/pdf"))]
    for name, data in (supp or []):
        files.append(("supplements", (name, io.BytesIO(data), "text/csv")))
    return files


def test_reproduce_route_returns_run_handle(monkeypatch):
    monkeypatch.setattr(reproduction_runs, "reproduction_drive",
                        type("M", (), {"reproduce": staticmethod(_fake_drive)}))
    r = client.post("/papers/mypaper/reproduce",
                    files=_multipart(supp=[("data.csv", b"gene,lfc\nA,2")]))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "succeeded" and "run_id" in body and "ledger" not in body
    # the run is retrievable with the full ledger.
    got = client.get(f"/reproduction-runs/{body['run_id']}")
    assert got.status_code == 200 and got.json()["ledger"]["paper"]["slug"]


def test_reproduce_route_rejects_oversized_upload(monkeypatch):
    monkeypatch.setattr(config.settings, "max_upload_mb", 0)  # any non-empty file exceeds 0 MB
    r = client.post("/papers/p/reproduce", files=_multipart(main_bytes=b"x" * 10))
    assert r.status_code == 413 and "limit" in r.json()["detail"]


def test_get_unknown_run_404():
    assert client.get("/reproduction-runs/nope").status_code == 404


def test_events_stream_resolves_terminal(monkeypatch):
    rec = reproduction_runs.start_run("m.pdf", [], drive_fn=_fake_drive)
    with client.stream("GET", f"/reproduction-runs/{rec.id}/events") as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())
    assert '"status": "succeeded"' in body and '"ledger"' not in body  # light ticks


def test_events_unknown_run_emits_error():
    with client.stream("GET", "/reproduction-runs/ghost/events") as resp:
        body = "".join(resp.iter_text())
    assert "unknown run" in body
