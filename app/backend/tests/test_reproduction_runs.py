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
from engine.compat import DataFit, FileFitReport
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
    fits = [FileFitReport(path="d.csv", filename="d.csv", kind="de_results", quality=100,
                          qc_ok=True, loadable=True, score=100, best_skill="volcano",
                          best_verdict="fit",
                          fits=[DataFit(path="d.csv", filename="d.csv", skill_id="volcano",
                                        kind="de_results", score=100, compatible=True,
                                        verdict="fit", qc_ok=True)])]
    return DriveResult(ledger=ledger, panel_drives=drives, data_fits=fits)


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


def test_public_surfaces_data_fits_with_confidence_band():
    # the run contract carries the dropped-data fit ranking + the confidence band the score means.
    rec = reproduction_runs.start_run("m.pdf", ["d.csv"], drive_fn=_fake_drive)
    full = reproduction_runs.public(rec)
    assert full["data_fits"] and full["data_fits"][0]["filename"] == "d.csv"
    assert full["data_fits"][0]["confidence"] == "confident"  # computed band, serialized for the FE


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


# --- pre-run data-fit assessment (Slice 2: the score BEFORE Run) --------------


def _assess(supp, skills=""):
    files = [("supplements", (name, io.BytesIO(data), "text/csv")) for name, data in supp]
    return client.post("/papers/p/assess-data", files=files, data={"skills": skills})


def test_assess_data_scores_a_good_file_confident():
    # a DE table dropped for a volcano panel → Confident, before any run (no PDF needed: skills given).
    r = _assess([("de.csv", b"gene,log2FoldChange,padj\nA,2.0,0.001\nB,-1.5,0.02")], skills="volcano")
    assert r.status_code == 200
    fits = r.json()["data_fits"]
    assert fits and fits[0]["confidence"] == "confident" and fits[0]["best_skill"] == "volcano"


def test_assess_data_flags_a_wrong_file_not_a_fit():
    # a QC table dropped for a single-cell panel → Not a fit, so the user can swap it before Run.
    r = _assess([("qc.csv", b"sample,estimated_cells,median_genes\ns1,5000,1500\ns2,6000,1480")],
                skills="umap_scrna")
    fits = r.json()["data_fits"]
    assert fits and fits[0]["confidence"] == "not_a_fit"


def test_assess_data_no_supplements_is_empty():
    r = client.post("/papers/p/assess-data", data={"skills": "volcano"})
    assert r.status_code == 200 and r.json() == {"paper_id": "p", "n_files": 0, "data_fits": []}
