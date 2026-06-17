"""Reproduction Engine core — verdict, blame, scorecard, validate/run loop, ledger I/O.

The blame cases are the two real dogfoods encoded as fixtures (no heavy deps): RPGRIP1
Fig 5 (paper-irreproducible) + Fig 6E/6D (engine-delta / upstream-delta / structural-limit).
The stub engine is forced for the one live ``run_panel`` wiring test.
"""

import pytest

import reproduction as R
from reproduction import (
    Golden,
    Ledger,
    MethodSub,
    OracleResult,
    Panel,
    Paper,
)


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


# --- verdict logic (D4) -------------------------------------------------------


def test_int_golden_is_strict_exact():
    assert R.classify_metric(1133, 1133)[0] == R.EXACT          # universe = 1,133, exact
    assert R.classify_metric(1133, 1130)[0] == R.CLOSE          # tiny int miss → close band
    assert R.classify_metric(78, 19)[0] == R.FAIL              # 78 vs adj-p<0.05 yields 19


def test_float_exact_within_one_percent():
    assert R.classify_metric(0.645, 0.650)[0] == R.EXACT       # 0.78% ≤ 1%
    assert R.classify_metric(0.645, 0.66)[0] == R.CLOSE        # 2.3% → close
    assert R.classify_metric(0.645, 0.99)[0] == R.FAIL         # 53% → fail


def test_rho_percentage_is_close():
    # RHO −71% (golden) vs Selom −73% → close (≤ ~4 pts), not exact.
    assert R.classify_metric(-71, -73)[0] == R.CLOSE


def test_direction_close_for_abundance():
    # 6D: golden ≥2×, Selom 1.1× — magnitude misses but the direction agrees.
    assert R.classify_metric(2.0, 1.1, direction_close=True)[0] == R.CLOSE
    assert R.classify_metric(2.0, 1.1, direction_close=False)[0] == R.FAIL


def test_string_and_missing():
    assert R.classify_metric("RHO", "RHO")[0] == R.EXACT
    assert R.classify_metric("RHO", "PDE6B")[0] == R.FAIL
    assert R.classify_metric(78, None) == (R.FAIL, None)


# --- blame decision procedure (D10 — the R-oracle pattern) --------------------


def test_blame_exact_is_none():
    assert R.assign_blame(R.EXACT) is None


def test_blame_wet_lab_and_structural():
    assert R.assign_blame(R.FAIL, scope=R.WET_LAB) == R.OUT_OF_SCOPE
    assert R.assign_blame(R.FAIL, structural=True) == R.STRUCTURAL_LIMIT


def test_blame_data_not_deposited_is_out_of_scope():
    # JEV Fig 8: a real modality Selom handles, but the study's data was never deposited —
    # reproducible only as a pipeline demo, so out-of-scope (not wet-lab, not structural).
    assert R.assign_blame(R.FAIL, scope=R.DATA_NOT_DEPOSITED) == R.OUT_OF_SCOPE
    assert R.WET_LAB in R.OUT_OF_SCOPE_SCOPES and R.DATA_NOT_DEPOSITED in R.OUT_OF_SCOPE_SCOPES


def test_blame_paper_irreproducible():
    # Fig 5 78/181/49: edgeR on the deposited raw data misses the golden too.
    oracle = OracleResult(tool="edgeR", ran_on=R.DEPOSITED_RAW, agrees_with_paper=False)
    assert R.assign_blame(R.FAIL, oracle=oracle) == R.PAPER_IRREPRODUCIBLE


def test_blame_engine_delta_and_selom_bug_on_raw():
    # Authors' tool reproduces the paper on raw; Selom differs.
    oracle = OracleResult(tool="edgeR", ran_on=R.DEPOSITED_RAW, agrees_with_paper=True)
    assert R.assign_blame(R.FAIL, oracle=oracle, substituted=True) == R.ENGINE_DELTA
    assert R.assign_blame(R.FAIL, oracle=oracle, substituted=False) == R.SELOM_ENGINE


def test_blame_engine_vs_upstream_on_intermediate():
    # 6E counts: fgsea on the SAME Cepo ranking ≈ paper, gseapy ≪ → engine-delta.
    eng = OracleResult(tool="fgsea", ran_on=R.SELOM_INTERMEDIATE,
                       agrees_with_paper=True, agrees_with_selom=False)
    assert R.assign_blame(R.FAIL, oracle=eng) == R.ENGINE_DELTA
    # 6E 52-core: fgsea on Selom's rod subtypes ALSO misses → upstream-delta.
    ups = OracleResult(tool="fgsea", ran_on=R.SELOM_INTERMEDIATE, agrees_with_paper=False)
    assert R.assign_blame(R.FAIL, oracle=ups) == R.UPSTREAM_DELTA


def test_blame_delta_unmeasured_without_oracle():
    assert R.assign_blame(R.FAIL) == R.DELTA_UNMEASURED


# --- validate_panel + scorecard (composition: fixture panel + fixture oracle) --


def _fig5_panel() -> Panel:
    return Panel(
        paper_id="rpgrip1",
        figure="5",
        panel="sig",
        chart_form="count",
        skill_id="deg",
        method_subs=[MethodSub(paper_tool="edgeR", selom_tool="pyDESeq2",
                               delta_measured="near-exact vs oracle")],
        golden=[
            Golden(metric="universe", value=1133, source=R.SOURCE_METHODS, deterministic=True),
            Golden(metric="signature.count", value=78, source=R.SOURCE_FIGURE),
            Golden(metric="RHO.delta_pct", value=-71, unit="%"),
        ],
    )


def test_validate_panel_assigns_per_metric_blame():
    panel = _fig5_panel()
    computed = {"universe": 1133, "signature.count": 19, "RHO.delta_pct": -73}
    oracles = {
        "signature.count": OracleResult(tool="edgeR", ran_on=R.DEPOSITED_RAW,
                                        agrees_with_paper=False),
    }
    val = R.validate_panel(panel, computed, run_id="r1", oracles=oracles,
                           guards_fired=["filter_ceiling"])
    by_metric = {r.metric: r for r in val.results}
    assert by_metric["universe"].verdict == R.EXACT
    assert by_metric["universe"].blame is None
    assert by_metric["signature.count"].verdict == R.FAIL
    assert by_metric["signature.count"].blame == R.PAPER_IRREPRODUCIBLE
    assert by_metric["RHO.delta_pct"].verdict == R.CLOSE
    assert val.panel_verdict == R.FAIL  # worst in-scope metric
    assert val.guards_fired == ["filter_ceiling"]


def test_scorecard_is_findings_first():
    paper = Paper(id="rpgrip1", slug="rpgrip1", title="RPGRIP1")
    panel = _fig5_panel()
    wet = Panel(paper_id="rpgrip1", figure="5", panel="D", scope=R.WET_LAB,
                golden=[Golden(metric="ihc", value=1)])
    ledger = Ledger(paper=paper, panels=[panel, wet])
    computed = {"universe": 1133, "signature.count": 19, "RHO.delta_pct": -73}
    oracles = {"signature.count": OracleResult(tool="edgeR", ran_on=R.DEPOSITED_RAW,
                                               agrees_with_paper=False)}
    ledger.validations.append(R.validate_panel(panel, computed, run_id="r1", oracles=oracles))
    ledger.validations.append(R.validate_panel(wet, {"ihc": None}, run_id="r2"))
    sc = R.build_scorecard(ledger)
    assert sc.n_panels == 2
    assert sc.n_in_scope == 1  # the wet-lab panel is excluded from the denominator
    assert sc.findings["paper_irreproducible"] == 1
    assert sc.findings["reproduced"] == 2  # universe (exact) + RHO.delta_pct (close, unattributed)
    assert sc.totals_by_blame[R.OUT_OF_SCOPE] == 1
    assert sc.totals_by_verdict[R.EXACT] == 1


def test_scorecard_reproduced_excludes_out_of_scope_panels():
    # A faithful match in a data-not-deposited panel is NOT a reproduction (no paper data to match).
    paper = Paper(id="p", slug="p", title="P")
    good = Panel(paper_id="p", figure="1", panel="a",
                 golden=[Golden(metric="pc1", value=39.8, ints_exact=False)])
    demo = Panel(paper_id="p", figure="8", panel="a", scope=R.DATA_NOT_DEPOSITED,
                 golden=[Golden(metric="umap", value=1)])
    ledger = Ledger(paper=paper, panels=[good, demo])
    ledger.validations.append(R.validate_panel(good, {"pc1": 39.7}, run_id="r1"))
    ledger.validations.append(R.validate_panel(demo, {"umap": 1}, run_id="r2"))
    sc = R.build_scorecard(ledger)
    assert sc.n_in_scope == 1
    assert sc.findings["reproduced"] == 1  # only the in-scope PCA match counts


def test_source_provenance_tags_and_divergence_surface():
    # D14: a panel reconstructed from a deposit but diverging from the published figure reads as
    # "ST6+ Fig4e−" and is surfaced transparently, never as a blame.
    paper = Paper(id="p", slug="p", title="P")
    panel = Panel(paper_id="p", figure="4", panel="e",
                  sources=[R.SourceTag(ref="ST6", faithful=True),
                           R.SourceTag(ref="Fig4e", faithful=False, note="different replicate")],
                  golden=[Golden(metric="de_total", value=447)])
    ledger = Ledger(paper=paper, panels=[panel])
    ledger.validations.append(R.validate_panel(panel, {"de_total": 447}, run_id="r1"))
    sc = R.build_scorecard(ledger)
    assert panel.provenance == "ST6+ Fig4e−"
    assert panel.diverges_from == ["Fig4e"]
    assert sc.findings["reproduced"] == 1            # faithful to the deposit = a win
    assert sc.findings["paper_irreproducible"] == 0  # the figure gap is provenance, not a blame
    assert sc.provenance_divergences == ["4e: ST6+ Fig4e−"]


# --- metric extraction --------------------------------------------------------


def test_table_extractor_reads_a_cell():
    table = {"columns": ["gene", "log2FC"], "rows": [["RHO", -2.5], ["PDE6B", 1.1]]}
    extract = R.table_extractor({"RHO.lfc": {"key_col": "gene", "key": "RHO", "value_col": "log2FC"}})
    assert extract(None, None, table) == {"RHO.lfc": -2.5}
    assert R.table_extractor({})(None, None, None) == {}  # no table → empty, never crashes


# --- ledger round-trip + live run wiring --------------------------------------


def test_ledger_round_trip(tmp_path):
    ledger = Ledger(paper=Paper(id="rpgrip1", slug="rpgrip1", title="RPGRIP1"),
                    panels=[_fig5_panel()])
    path = R.save_ledger(ledger, root=tmp_path)
    assert path.exists()
    again = R.load_ledger("rpgrip1", root=tmp_path)
    assert again.paper.title == "RPGRIP1"
    assert again.panels[0].golden[0].value == 1133
    assert again.panels[0].method_subs[0].selom_tool == "pyDESeq2"


def test_run_panel_drives_a_real_stub_skill(tmp_path):
    data = tmp_path / "demo.h5ad"
    data.write_bytes(b"dummy")
    panel = Panel(paper_id="p", figure="1", panel="A", skill_id="cluster",
                  params={"resolution": "1.0"},
                  golden=[Golden(metric="x", value=1.0)])
    ledger = Ledger(paper=Paper(id="p", slug="p"), panels=[panel])
    run, val = R.run_panel(
        ledger, panel, str(data), filename="demo.h5ad",
        extractor=lambda p, f, t: {"x": 1.0},  # simulate extraction deterministically
    )
    assert run.figure_spec and run.figure_spec.get("data")
    assert run.provenance and run.provenance["input"]["sha256"]
    assert run.methods_text and run.methods_text.get("text")
    assert run.params["resolution"] == 1.0  # coerced, not "1.0"
    assert val.panel_verdict == R.EXACT
    assert panel.status == "validated"
    assert ledger.scorecard.totals_by_verdict[R.EXACT] == 1
