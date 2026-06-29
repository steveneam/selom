"""Auto-drive regression fixtures (reproduction_fixtures.py) — Slice 4.

Three tiers, matching ``docs/records/reproduction-dogfood/spec.md`` D5:

* **framework unit tests** (CI, no data) — prove ``snapshot`` / ``diff`` / ``assert_reproduces`` and
  the s46 tolerance reuse: an identical re-drive reproduces, a status flip is caught, a driven
  metric within its metric-type band stays green, an out-of-band value flips red ("break a reader ->
  fixture goes red", the spec's Testing-Strategy check) — all on a synthetic stub-runner drive.
* **characterization tests** (CI, no data) — load every committed snapshot JSON and assert its honest
  shape (statuses honest, summary == tally, 0 Selom defects), guarding the blessed baseline from
  corruption.
* **opt-in real re-drive** (owner machine only — skips where the paper PDF is not staged) — the
  genuine engine-regression guard: cold-``reproduce()`` each blessed paper and assert it still
  reproduces its committed snapshot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import reproduction as R
from extract.ingest import SUPP_CSV, IngestedPaper, IngestedSupplement, PaperBundle
from reproduction.drive import DRIVEN, DriveResult, PanelDrive, drive_bundle
from reproduction.fixtures import (
    HONEST_STATUSES,
    assert_reproduces,
    diff,
    load_snapshot,
    save_snapshot,
    snapshot,
)
from scripts.regen_reproduction_fixtures import FIXTURE_PAPERS

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "reproduction"


# --- synthetic drive (the framework unit tests, no data) ----------------------

_DE_TEXT = (
    "Methods. Differential gene expression analysis was performed with DESeq2 and visualised as "
    "volcano plots. Results. In total, 180 genes were differentially expressed, with 61 upregulated "
    "and 119 downregulated (Figure 4)."
)


def _bundle(text=_DE_TEXT):
    main = IngestedPaper(path="main.pdf", n_pages=1, text=text)
    supp = IngestedSupplement(path="data.csv", kind=SUPP_CSV, role="tables", sheets={"data": ["gene"]})
    return PaperBundle(paper_id="t", main=main, supplements=[supp])


def _volcano_runner(up, down, ns=1):
    rows = ([["u%d" % i, 2.0, 0.001, "up"] for i in range(up)]
            + [["d%d" % i, -2.0, 0.002, "down"] for i in range(down)]
            + [["n%d" % i, 0.1, 0.9, "n.s."] for i in range(ns)])
    table = {"columns": ["gene", "log2FC", "padj", "direction"], "rows": rows,
             "title": "Differential expression"}

    def runner(skill_id, data_path, params):
        return {"data": [], "layout": {}}, table
    return runner


def _driven_panel_snapshot():
    """A synthetic cold drive that actually drives a volcano DE panel → snapshot it (the framework's
    happy path; today's real papers drive 0 panels, so the metric path is proved here)."""
    res = drive_bundle(_bundle(), paper_id="t", runner=_volcano_runner(1, 1))
    snap = snapshot(res)
    driven = [p for p in snap.panels if p.status == DRIVEN]
    assert driven, snap.summary
    assert driven[0].metrics, "a driven panel must carry its read-back metric values"
    return snap


def test_snapshot_projects_status_and_driven_metrics():
    snap = _driven_panel_snapshot()
    driven = next(p for p in snap.panels if p.status == DRIVEN)
    assert {"de_up", "de_down", "de_total"} <= set(driven.metrics)
    assert snap.selom_defects == 0
    assert snap.n_panels == len(snap.panels)


def test_identical_redrive_reproduces():
    snap = _driven_panel_snapshot()
    again = drive_bundle(_bundle(), paper_id="t", runner=_volcano_runner(1, 1))
    assert diff(snap, again) == []
    assert_reproduces(snap, again)            # does not raise


def test_status_flip_is_caught():
    snap = _driven_panel_snapshot()
    # No tabular this run → the DE panel can't match data → status flips driven -> data_unmatched.
    main = IngestedPaper(path="main.pdf", n_pages=1, text=_DE_TEXT)
    no_data = PaperBundle(paper_id="t", main=main, supplements=[])
    regressed = drive_bundle(no_data, paper_id="t", runner=_volcano_runner(1, 1))
    problems = diff(snap, regressed)
    assert any("status" in p for p in problems), problems
    with pytest.raises(AssertionError):
        assert_reproduces(snap, regressed)


def test_broken_reader_out_of_band_flips_red():
    # Same panel still drives, but the read-back DE counts change wildly (a reader/extractor break):
    # de counts are strict (MT_DE_COUNT), so 1->10 is out of band -> flagged.
    snap = _driven_panel_snapshot()
    broken = drive_bundle(_bundle(), paper_id="t", runner=_volcano_runner(10, 10))
    problems = diff(snap, broken)
    assert any("out of tolerance band" in p for p in problems), problems


# --- the metric-type tolerance band (engine delta green / break red) ----------


def _one_driven_result(*, metric="composition_pct", mtype=R.MT_PROPORTION, value=50.0):
    """A hand-built single-panel ``DriveResult`` with one driven, typed golden — to exercise
    ``diff``'s use of the s46 ``resolve_tolerances`` band directly."""
    panel = R.Panel(paper_id="t", figure="1", panel="", skill_id="composition",
                    golden=[R.Golden(metric=metric, value=value, metric_type=mtype)])
    run = R.ReproRun(id="r1", panel_key=panel.key, skill_id="composition",
                     computed=[R.MetricValue(metric=metric, value=value)])
    ledger = R.Ledger(paper=R.Paper(id="t", slug="t"), panels=[panel], runs=[run])
    drive = PanelDrive(panel_key=panel.key, status=DRIVEN, skill_id="composition",
                       metrics_read=[metric])
    return DriveResult(ledger=ledger, panel_drives=[drive])


def test_within_band_metric_delta_stays_green():
    # proportion band = 15% close_tol; 50 -> 52 (4%) is a tolerated delta, not a regression.
    expected = snapshot(_one_driven_result(value=50.0))
    actual = _one_driven_result(value=52.0)
    assert diff(expected, actual) == []


def test_out_of_band_metric_delta_flips_red():
    # 50 -> 80 (60%) blows past the proportion band -> a real regression.
    expected = snapshot(_one_driven_result(value=50.0))
    actual = _one_driven_result(value=80.0)
    problems = diff(expected, actual)
    assert any("out of tolerance band" in p for p in problems), problems


def test_engine_sensitive_band_is_wider_than_strict():
    # The SAME numeric delta (100 -> 128, 28%) that breaks a strict de_count (close_tol 0.25) is
    # tolerated for a gsea term count (engine-sensitive, close_tol 0.30) — proving the band follows
    # the metric TYPE, so a measured gseapy<<fgsea engine delta isn't mislabelled a regression.
    strict_exp = snapshot(_one_driven_result(metric="de_total", mtype=R.MT_DE_COUNT, value=100.0))
    strict_act = _one_driven_result(metric="de_total", mtype=R.MT_DE_COUNT, value=128.0)
    assert diff(strict_exp, strict_act), "a 28% delta on a strict de_count must flag"
    wide_exp = snapshot(_one_driven_result(metric="enriched_terms",
                                           mtype=R.MT_GSEA_TERM_COUNT, value=100.0))
    wide_act = _one_driven_result(metric="enriched_terms", mtype=R.MT_GSEA_TERM_COUNT, value=128.0)
    assert diff(wide_exp, wide_act) == [], "a 28% delta on a gsea term count is within band"


# --- JSON round-trip ----------------------------------------------------------


def test_snapshot_round_trips_through_json(tmp_path):
    snap = _driven_panel_snapshot()
    path = save_snapshot(snap, tmp_path / "t.json")
    assert path.exists()
    again = load_snapshot(path)
    assert again == snap


# --- characterization of the committed snapshots (CI, no data) ----------------

_COMMITTED = sorted(FIXTURE_DIR.glob("*.json"))


def test_expected_fixtures_are_committed():
    names = {p.stem for p in _COMMITTED}
    assert {"jev", "hani", "dorgau"} <= names, f"missing blessed snapshots; found {names}"


@pytest.mark.parametrize("path", _COMMITTED, ids=lambda p: p.stem)
def test_committed_snapshot_is_honest(path):
    snap = load_snapshot(path)
    assert snap.panels, f"{path.name} has no panels"
    assert snap.n_panels == len(snap.panels)
    assert all(p.status in HONEST_STATUSES for p in snap.panels), \
        [p.status for p in snap.panels if p.status not in HONEST_STATUSES]
    tally: dict[str, int] = {}
    for p in snap.panels:
        tally[p.status] = tally.get(p.status, 0) + 1
    assert snap.summary == tally
    assert snap.n_driven == sum(1 for p in snap.panels if p.status == DRIVEN)
    assert snap.selom_defects == 0                     # the load-bearing honesty invariant
    for p in snap.panels:                              # a non-driven gap has no number to reproduce
        if p.status != DRIVEN:
            assert p.metrics == {}


# --- opt-in real re-drive (owner machine only; skips without the staged PDF) --


@pytest.mark.parametrize("paper_id", list(FIXTURE_PAPERS))
def test_real_cold_drive_reproduces_snapshot(paper_id):
    main, supplements = FIXTURE_PAPERS[paper_id]
    snap_path = FIXTURE_DIR / f"{paper_id}.json"
    if not main or not Path(main).exists():
        pytest.skip(f"{paper_id}: main PDF not staged (owner machine only)")
    if not snap_path.exists():
        pytest.skip(f"{paper_id}: no committed snapshot (run scripts.regen_reproduction_fixtures)")
    from reproduction.drive import reproduce

    result = reproduce(main, supplements, paper_id=paper_id)
    assert_reproduces(load_snapshot(snap_path), result)
