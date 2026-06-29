"""Honest-edge hardening (live-reproduction-spec §10.4) — the two-axis credibility guard.

The load-bearing invariant of the whole feature ([[selom-reproducibility-score]], L2/L4): a figure
we can't reproduce **because of the paper or its data** must score LOW on the *reproducibility* axis
and **never** as a *Selom-confidence* defect. These tests drive deliberately-irreproducible inputs
END-TO-END (through the drive, not hand-built validations) and assert the guard holds — so a hard
paper can never read as a Selom failure once the UI exposes it.
"""

from __future__ import annotations

import reproduction as R
from extract.ingest import SUPP_CSV, IngestedPaper, IngestedSupplement, PaperBundle
from reproduction.drive import DRIVEN, drive_bundle, drive_panel


# A paper that PRINTS DE counts (180/61/119, Figure 4) the deposited data won't reproduce.
_TEXT = (
    "Methods. Differential gene expression analysis was performed with DESeq2 and visualised as "
    "volcano plots. Principal component analysis (PCA) summarised sample variation. "
    "Results. In total, 180 genes were differentially expressed, with 61 upregulated and 119 "
    "downregulated (Figure 4). The PCA of all samples is presented in Figure 2."
)


def _bundle(with_data: bool):
    main = IngestedPaper(path="main.pdf", n_pages=1, text=_TEXT)
    supps = []
    if with_data:
        supps = [IngestedSupplement(path="de.csv", kind=SUPP_CSV, role="tables",
                                    sheets={"de": ["gene", "log2FC", "padj"]})]
    return PaperBundle(paper_id="hard", main=main, supplements=supps)


def _de_table(up, down, ns=0):
    rows = ([["u%d" % i, 2.0, 0.001, "up"] for i in range(up)]
            + [["d%d" % i, -2.0, 0.001, "down"] for i in range(down)]
            + [["n%d" % i, 0.1, 0.9, "n.s."] for i in range(ns)])
    return {"columns": ["gene", "log2FC", "padj", "direction"], "rows": rows,
            "title": "Differential expression"}


def _mismatch_runner(skill_id, data_path, params):
    # the deposited data gives a totally different DE count than the figure printed (10/5 vs 61/119).
    return {"data": [], "layout": {}}, _de_table(10, 5)


def _no_selom_bugs(sc) -> None:
    assert sc.findings["selom_engine_bugs"] == 0
    assert sc.totals_by_blame.get(R.SELOM_ENGINE, 0) == 0


# --- the figure prints a number its own data can't reproduce (the JEV Fig4e shape) ------------


def test_irreproducible_value_is_low_reproducibility_not_a_selom_defect():
    res = drive_bundle(_bundle(with_data=True), paper_id="hard", runner=_mismatch_runner)
    sc = res.ledger.scorecard
    driven = [d for d in res.panel_drives if d.status == DRIVEN]
    assert driven, "expected the DE figure to drive (volcano on the attached data)"
    val = next(v for v in res.ledger.validations if v.panel_key == driven[0].panel_key)
    assert val.panel_verdict == R.FAIL                       # the printed number did not reproduce
    assert all(r.blame == R.DELTA_UNMEASURED for r in val.results)  # no oracle → honestly unattributed
    _no_selom_bugs(sc)                                       # ← the guard: NOT a Selom bug
    ps = next(p for p in sc.panel_scores if p.panel_key == driven[0].panel_key)
    assert ps.reproducibility == 50 and ps.tier != R.DISCREPANT  # low reproducibility, not "Selom wrong"
    assert ps.selom_confidence == 60                         # honest uncertainty about our own value


# --- the paper's data simply isn't attached (every golden panel data_unmatched) ---------------


def test_unmatched_data_paper_scores_zero_defects_all_grey():
    res = drive_bundle(_bundle(with_data=False), paper_id="hard", runner=_mismatch_runner)
    sc = res.ledger.scorecard
    _no_selom_bugs(sc)
    assert sc.score.n_scored == 0                            # nothing was scorable
    assert all(ps.reproducibility is None for ps in sc.panel_scores)  # every panel greyed
    assert {d.status for d in res.panel_drives} <= {"data_unmatched", "no_golden", "out_of_scope"}
    # and no panel was silently dropped.
    assert len(sc.panel_scores) == len(res.ledger.panels)


# --- a structural limit: the deposit CAN'T reach the number → paper/data side, Selom ✓ ---------


def test_structural_limit_is_paper_side_high_confidence():
    panel = R.Panel(paper_id="hard", figure="4", panel="e", skill_id="volcano",
                    golden=[R.Golden(metric="de_total", value=180, structural_limit=True)])
    led = R.Ledger(paper=R.Paper(id="hard", slug="hard"), panels=[panel])
    drive_panel(led, panel, tabular=["de.csv"], data_map=None, runner=_mismatch_runner, params=None)
    led.scorecard = R.build_scorecard(led)
    ps = led.scorecard.panel_scores[0]
    # the textbook two-axis split: figure unreachable (low repro) BUT Selom did its job (high conf).
    assert ps.reproducibility == 38 and ps.tier == R.IRREPRODUCIBLE
    assert ps.selom_confidence == 100 and ps.attribution == R.ATTR_DATA
    _no_selom_bugs(led.scorecard)


# --- ran, but no layer can read the printed metric → needs_recipe, never a fabricated fail -----


def test_needs_recipe_never_validates_a_missing_metric():
    panel = R.Panel(paper_id="hard", figure="3", panel="", skill_id="gsea",
                    golden=[R.Golden(metric="nes_of_some_term", value=2.1)])
    led = R.Ledger(paper=R.Paper(id="hard", slug="hard"), panels=[panel])

    def _opaque_runner(skill_id, data_path, params):  # output the reader can't map to the golden
        return {"data": [], "layout": {"title": {"text": "GSEA"}}}, None

    d = drive_panel(led, panel, tabular=["x.csv"], data_map=None, runner=_opaque_runner, params=None)
    assert d.status == "needs_recipe" and not led.validations  # never invented a FAIL
    led.scorecard = R.build_scorecard(led)
    _no_selom_bugs(led.scorecard)
    assert led.scorecard.score.n_scored == 0
