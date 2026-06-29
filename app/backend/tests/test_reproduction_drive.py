"""Live-reproduction drive (reproduction_drive.py) — orchestration + honest classification.

The skill run is injected (a fake ``runner``) so these are deterministic and stack-free; the merge
(gap #1) is exercised through a constructed ``PaperBundle`` so route+golden run for real. The
load-bearing assertions are the **honest classification** (data_unmatched / needs_recipe / no_golden
/ out_of_scope never become a Selom defect) and **no silent caps** (every panel gets a heatmap cell).
A real-skill, real-data end-to-end belongs in a skipif live test, like the hand ledgers' drive_live.
"""

from __future__ import annotations

import reproduction as R
from extract.ingest import SUPP_CSV, IngestedPaper, IngestedSupplement, PaperBundle
from reproduction.drive import (
    DATA_UNMATCHED,
    DRIVEN,
    NEEDS_RECIPE,
    NO_GOLDEN,
    NO_SKILL,
    OUT_OF_SCOPE,
    RUN_FAILED,
    build_merged_ledger,
    drive_bundle,
    drive_panel,
    match_data,
)


# --- fixtures -----------------------------------------------------------------


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


def _raising_runner(skill_id, data_path, params):
    raise ValueError("could not parse data")


def _ledger(*panels):
    return R.Ledger(paper=R.Paper(id="t", slug="t"), panels=list(panels))


def _de_panel(skill_id="volcano", figure="4"):
    return R.Panel(paper_id="t", figure=figure, panel="", skill_id=skill_id, golden=[
        R.Golden(metric="de_up", value=1), R.Golden(metric="de_down", value=1),
        R.Golden(metric="de_total", value=2)])


# --- gap #2: data matching ----------------------------------------------------


def test_match_data_override_wins():
    p = _de_panel()
    path, note = match_data(p, ["a.csv", "b.csv"], {p.key: "chosen.csv"})
    assert path == "chosen.csv" and "override" in note


def test_match_data_single_then_ambiguous_then_none():
    p = _de_panel()
    assert match_data(p, ["only.csv"], None)[0] == "only.csv"
    path, note = match_data(p, ["a.csv", "b.csv"], None)
    assert path == "a.csv" and "ambiguous" in note
    assert match_data(p, [], None)[0] is None


# --- the per-panel drive: every classification branch -------------------------


def test_drive_out_of_scope_never_runs():
    p = R.Panel(paper_id="t", figure="6", panel="", skill_id=None, scope=R.WET_LAB)
    led = _ledger(p)
    d = drive_panel(led, p, tabular=["d.csv"], data_map=None, runner=_raising_runner, params=None)
    assert d.status == OUT_OF_SCOPE and not led.runs  # oos decided before any run → no crash


def test_drive_no_skill():
    p = R.Panel(paper_id="t", figure="2", panel="", skill_id=None)
    d = drive_panel(_ledger(p), p, tabular=["d.csv"], data_map=None, runner=_volcano_runner, params=None)
    assert d.status == NO_SKILL


def test_drive_data_unmatched_for_golden_panel():
    p = _de_panel()
    d = drive_panel(_ledger(p), p, tabular=[], data_map=None, runner=_volcano_runner, params=None)
    assert d.status == DATA_UNMATCHED


def test_drive_run_failed_is_not_a_defect():
    p = _de_panel()
    led = _ledger(p)
    d = drive_panel(led, p, tabular=["d.csv"], data_map=None, runner=_raising_runner, params=None)
    assert d.status == RUN_FAILED and not led.validations  # never validated → never a FAIL


def test_drive_no_golden_records_a_run():
    p = R.Panel(paper_id="t", figure="1", panel="", skill_id="umap_scrna")  # no golden
    led = _ledger(p)
    d = drive_panel(led, p, tabular=["d.csv"], data_map=None, runner=_volcano_runner, params=None)
    assert d.status == NO_GOLDEN and len(led.runs) == 1 and not led.validations


def test_drive_needs_recipe_when_reader_cannot_read():
    p = R.Panel(paper_id="t", figure="3", panel="", skill_id="gsea",
                golden=[R.Golden(metric="nes_named_term", value=2.0)])
    led = _ledger(p)
    d = drive_panel(led, p, tabular=["d.csv"], data_map=None, runner=_empty_runner, params=None)
    assert d.status == NEEDS_RECIPE and len(led.runs) == 1 and not led.validations


def test_drive_driven_validates_against_golden():
    p = _de_panel()
    led = _ledger(p)
    d = drive_panel(led, p, tabular=["d.csv"], data_map=None, runner=_volcano_runner, params=None)
    assert d.status == DRIVEN and set(d.metrics_read) == {"de_up", "de_down", "de_total"}
    assert len(led.validations) == 1
    led.scorecard = R.build_scorecard(led)
    ps = led.scorecard.panel_scores[0]
    assert ps.reproducibility == 100 and ps.selom_confidence == 100  # exact match, no substitution


# --- L2/L4 invariants: honest classification, no silent caps ------------------


def test_two_axis_guard_grey_panels_are_zero_defects():
    p_driven, p_unmatched = _de_panel(figure="4"), _de_panel(figure="5")
    p_oos = R.Panel(paper_id="t", figure="6", panel="", skill_id=None, scope=R.WET_LAB)
    p_recipe = R.Panel(paper_id="t", figure="3", panel="", skill_id="gsea",
                       golden=[R.Golden(metric="nes_x", value=2.0)])
    led = _ledger(p_driven, p_unmatched, p_oos, p_recipe)
    drive_panel(led, p_driven, tabular=["d.csv"], data_map=None, runner=_volcano_runner, params=None)
    drive_panel(led, p_unmatched, tabular=[], data_map=None, runner=_volcano_runner, params=None)
    drive_panel(led, p_oos, tabular=["d.csv"], data_map=None, runner=_volcano_runner, params=None)
    drive_panel(led, p_recipe, tabular=["d.csv"], data_map=None, runner=_empty_runner, params=None)
    led.scorecard = R.build_scorecard(led)
    from reproduction.drive import _append_grey_cells
    _append_grey_cells(led, [])
    sc = led.scorecard
    assert sc.findings["selom_engine_bugs"] == 0                 # no panel is a Selom defect
    assert sc.score.selom_confidence == 100                      # the only scored panel is exact
    assert sc.score.n_scored == 1 and sc.score.n_in_scope == 3   # 3 in-scope (one oos), 1 driven
    # no silent caps: every panel has exactly one heatmap cell.
    keys = [ps.panel_key for ps in sc.panel_scores]
    assert sorted(keys) == ["3", "4", "5", "6"]
    grey = {ps.panel_key for ps in sc.panel_scores if ps.reproducibility is None}
    assert grey == {"3", "5", "6"}                              # recipe, unmatched, oos all greyed


# --- gap #1: merge auto-ledger + extracted goldens ----------------------------


def _bundle(text):
    main = IngestedPaper(path="main.pdf", n_pages=1, text=text)
    supp = IngestedSupplement(path="data.csv", kind=SUPP_CSV, role="tables", sheets={"data": ["gene"]})
    return PaperBundle(paper_id="t", main=main, supplements=[supp])


_TEXT = (
    "Methods. Differential gene expression analysis was performed with DESeq2 and visualised as "
    "volcano plots. Principal component analysis (PCA) summarised sample variation. "
    "Results. In total, 180 genes were differentially expressed, with 61 upregulated and 119 "
    "downregulated (Figure 4). The PCA of all samples is presented in Figure 2."
)


def test_build_merged_ledger_dedups_golden_figures():
    led = build_merged_ledger(_bundle(_TEXT), "t")
    # the DE figure carries extracted goldens and a routed skill (drivable).
    golden_panels = [p for p in led.panels if p.golden]
    assert golden_panels, "expected the DE figure to carry extracted DE-count goldens"
    gp = golden_panels[0]
    assert {g.metric for g in gp.golden} >= {"de_total", "de_up", "de_down"}
    # a DE-count golden is forced to volcano (the only clean DE-count source) even if the
    # per-figure route picked another skill — the inventory-backed override.
    assert gp.skill_id == "volcano"
    # no figure is double-counted (skeleton panel for a golden figure was dropped).
    figs = [p.figure for p in led.panels]
    assert len(figs) == len(set(figs))
    # the paper-level inventory rode along on methods_digest.
    assert led.paper.methods_digest.get("skills")


def test_drive_bundle_end_to_end_is_honest():
    res = drive_bundle(_bundle(_TEXT), paper_id="t", runner=_volcano_runner)
    assert res.ledger.scorecard is not None
    assert res.ledger.scorecard.findings["selom_engine_bugs"] == 0
    # every panel is accounted for — one drive record + one heatmap cell each.
    assert len(res.panel_drives) == len(res.ledger.panels)
    assert len(res.ledger.scorecard.panel_scores) == len(res.ledger.panels)


# --- Slice 1: the analyzed-dataset-size (n_cells) loop, extractor → grade ------

_UMAP_TEXT = ("Results. After quality control, the integrated atlas resulted in 1,234 cells after "
              "filtering, visualised as a UMAP embedding in Figure 1.")


def _umap_runner(n):
    def runner(skill_id, data_path, params):
        # umap_scrna's real shape: one scatter trace per cluster, n plotted points == the cell count.
        return {"data": [{"type": "scatter", "x": list(range(n)), "y": list(range(n))}]}, None
    return runner


def test_drive_n_cells_closes_the_loop_extractor_to_grade():
    # Slice 1 end-to-end: the printed dataset size is extracted (n_cells), its golden panel is
    # backfilled to umap_scrna, and the matched run's UMAP point count is read back and graded —
    # the new family drives a real score with no hand ledger, exactly like the DE-count loop.
    res = drive_bundle(_bundle(_UMAP_TEXT), paper_id="t", runner=_umap_runner(1234))
    driven = [d for d in res.panel_drives if d.status == DRIVEN and "n_cells" in d.metrics_read]
    assert driven, res.summary               # the n_cells figure reached a real score
    assert driven[0].skill_id == "umap_scrna"  # skill backfilled from the n_cells metric
    assert res.ledger.scorecard.findings["selom_engine_bugs"] == 0


def test_drive_n_cells_mismatch_is_honest_not_a_defect():
    # If the recount disagrees with the printed size, it scores honestly on the reproducibility
    # axis but is never a Selom-side defect (the two-axis guard, same as every other metric).
    res = drive_bundle(_bundle(_UMAP_TEXT), paper_id="t", runner=_umap_runner(900))
    assert res.ledger.scorecard.findings["selom_engine_bugs"] == 0
