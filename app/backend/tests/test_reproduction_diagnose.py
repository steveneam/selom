"""Cold-drive diagnostic (reproduction_diagnose.py) — the gap-report projection (Slice 0, D1).

Pure projection over a constructed ``DriveResult`` (stub runners, no PDF / no scientific stack), so
these are deterministic and fast. The real Harmony cold drive is a one-off findings note, not a CI
test (too heavy). The load-bearing assertions: the counts + ``auto_grade_rate`` are right, the n/a
guard holds (no divide-by-zero), and **every panel gets a row** (no silent caps, mirroring the heatmap
invariant in ``test_reproduction_drive``).
"""

from __future__ import annotations

import reproduction as R
from reproduction_diagnose import diagnose, to_markdown
from reproduction_drive import (
    DATA_UNMATCHED,
    DRIVEN,
    NEEDS_RECIPE,
    NO_GOLDEN,
    OUT_OF_SCOPE,
    DriveResult,
    _append_grey_cells,
    drive_panel,
)


# --- fixtures (mirror test_reproduction_drive.py) -----------------------------


def _de_table(up=1, down=1, ns=1):
    rows = ([["u%d" % i, 2.0, 0.001, "up"] for i in range(up)]
            + [["d%d" % i, -2.0, 0.002, "down"] for i in range(down)]
            + [["n%d" % i, 0.1, 0.9, "n.s."] for i in range(ns)])
    return {"columns": ["gene", "log2FC", "padj", "direction"], "rows": rows,
            "title": "Differential expression"}


def _volcano_runner(skill_id, data_path, params):
    return {"data": [], "layout": {}}, _de_table()


def _empty_runner(skill_id, data_path, params):
    return {"data": [], "layout": {}}, None


def _de_panel(figure):
    return R.Panel(paper_id="t", figure=figure, panel="", skill_id="volcano", golden=[
        R.Golden(metric="de_up", value=1), R.Golden(metric="de_down", value=1),
        R.Golden(metric="de_total", value=2)])


def _driven_result() -> DriveResult:
    """A constructed drive over one of every honest outcome → a real DriveResult to project."""
    p_driven = _de_panel("4")                                          # driven
    p_unmatched = _de_panel("5")                                       # data_unmatched (no tabular)
    p_oos = R.Panel(paper_id="t", figure="6", panel="", skill_id=None, scope=R.WET_LAB)  # out_of_scope
    p_recipe = R.Panel(paper_id="t", figure="3", panel="", skill_id="gsea",
                       golden=[R.Golden(metric="nes_x", value=2.0)])   # needs_recipe (reader can't read)
    p_nogold = R.Panel(paper_id="t", figure="1", panel="", skill_id="umap_scrna")  # no_golden (no golden)
    led = R.Ledger(paper=R.Paper(id="harmony-test", slug="t"),
                   panels=[p_driven, p_unmatched, p_oos, p_recipe, p_nogold])
    drives = [
        drive_panel(led, p_driven, tabular=["d.csv"], data_map=None, runner=_volcano_runner, params=None),
        drive_panel(led, p_unmatched, tabular=[], data_map=None, runner=_volcano_runner, params=None),
        drive_panel(led, p_oos, tabular=["d.csv"], data_map=None, runner=_volcano_runner, params=None),
        drive_panel(led, p_recipe, tabular=["d.csv"], data_map=None, runner=_empty_runner, params=None),
        drive_panel(led, p_nogold, tabular=["d.csv"], data_map=None, runner=_volcano_runner, params=None),
    ]
    led.scorecard = R.build_scorecard(led)
    _append_grey_cells(led, drives)
    return DriveResult(ledger=led, panel_drives=drives)


# --- the projection -----------------------------------------------------------


def test_projection_statuses_counts_and_rate():
    rep = diagnose(_driven_result())
    by_key = {p.panel_key: p for p in rep.panels}

    assert rep.n_panels == 5                                     # every panel projected (no silent caps)
    assert by_key["4"].status == DRIVEN
    assert by_key["5"].status == DATA_UNMATCHED
    assert by_key["6"].status == OUT_OF_SCOPE
    assert by_key["3"].status == NEEDS_RECIPE
    assert by_key["1"].status == NO_GOLDEN

    assert rep.n_in_scope == 4                                   # only fig6 (wet-lab) is out of scope
    # gradable = in-scope AND ≥1 printed golden → fig4, fig5, fig3 (NOT fig1 = no golden, NOT fig6 = oos)
    assert rep.n_gradable == 3
    assert rep.n_driven == 1
    assert rep.auto_grade_rate is not None
    assert abs(rep.auto_grade_rate - 1 / 3) < 1e-9
    assert rep.summary == {DRIVEN: 1, DATA_UNMATCHED: 1, OUT_OF_SCOPE: 1, NEEDS_RECIPE: 1, NO_GOLDEN: 1}


def test_projection_panel_detail():
    rep = diagnose(_driven_result(), paper_id="harmony")
    by_key = {p.panel_key: p for p in rep.panels}
    assert rep.paper_id == "harmony"

    driven = by_key["4"]
    assert set(driven.goldens_expected) == {"de_up", "de_down", "de_total"}
    assert set(driven.metrics_read) == {"de_up", "de_down", "de_total"}
    assert driven.in_scope and driven.fix_hint == ""            # a driven panel needs no fix

    oos = by_key["6"]
    assert not oos.in_scope and oos.fix_hint                     # out-of-scope carries an honest hint

    unmatched = by_key["5"]
    assert unmatched.goldens_expected and not unmatched.metrics_read
    assert "Slice 2" in unmatched.fix_hint                       # routed to the data-picker slice


def test_auto_grade_rate_na_when_nothing_gradable():
    """A paper with no in-scope golden panel → n/a, never a divide-by-zero (R2 / Error Behavior)."""
    p_oos = R.Panel(paper_id="t", figure="6", panel="", skill_id=None, scope=R.WET_LAB)
    p_nogold = R.Panel(paper_id="t", figure="1", panel="", skill_id="umap_scrna")
    led = R.Ledger(paper=R.Paper(id="t", slug="t"), panels=[p_oos, p_nogold])
    drives = [
        drive_panel(led, p_oos, tabular=["d.csv"], data_map=None, runner=_volcano_runner, params=None),
        drive_panel(led, p_nogold, tabular=["d.csv"], data_map=None, runner=_volcano_runner, params=None),
    ]
    led.scorecard = R.build_scorecard(led)
    _append_grey_cells(led, drives)
    rep = diagnose(DriveResult(ledger=led, panel_drives=drives))
    assert rep.n_gradable == 0
    assert rep.auto_grade_rate is None
    assert rep.auto_grade_label.startswith("n/a")


def test_to_markdown_is_readable_and_complete():
    md = to_markdown(diagnose(_driven_result(), paper_id="harmony"))
    assert "auto-grade rate" in md and "| panel |" in md
    # no silent caps: every panel key appears in the rendered table.
    for key in ("1", "3", "4", "5", "6"):
        assert f"| {key} |" in md


# --- Slice 5: cited-dataset provenance surfaced in the report -----------------


def test_accessions_surface_in_report_and_markdown():
    from extract.accessions import find_accessions

    accs = find_accessions("Data Availability. The data are in GEO: GSE213152 (77).")
    rep = diagnose(_driven_result(), paper_id="harmony", accessions=accs)
    assert [a.id for a in rep.accessions] == ["GSE213152"]
    assert "1 accession" in rep.data_provenance and "fetchable" in rep.data_provenance
    md = to_markdown(rep)
    assert "Cited datasets" in md and "GSE213152" in md and "cited data (Slice 5)" in md


def test_no_accessions_reports_honest_empty_provenance():
    rep = diagnose(_driven_result(), paper_id="harmony")   # no accessions passed
    assert rep.accessions == []
    assert rep.data_provenance == "no dataset accession recognized in the paper text"
