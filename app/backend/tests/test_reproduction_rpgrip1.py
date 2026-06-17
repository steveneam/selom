"""RPGRIP1 end-to-end integration: build the real ledger + drive it through the engine.

The first integration test of the Reproduction Engine on a real paper (R0+R1+R2+R3 together).
It does NOT touch real data or R — it replays the verified session-11/12 dogfood observations
(``reproduction_rpgrip1._captured``) through the engine and asserts the scorecard the engine
*produces* equals the verdicts/blame reached by hand in ``docs/rpgrip1-figrepro.md``. The live
re-run on the real GSE293982 deposit is the dev CLI (``python -m reproduction_rpgrip1 --live-fig5``).
"""

import reproduction as R
import reproduction_rpgrip1 as RP


# --- ledger construction (the structured target spec) -------------------------


def test_build_ledger_shape():
    ledger = RP.build_ledger()
    assert ledger.paper.id == "rpgrip1"
    assert ledger.paper.geo == ["GSE293982", "GSE293984"]
    assert ledger.paper.methods_digest["signature"].startswith("MSigDB C5")
    assert len(ledger.panels) == 13
    in_scope = [p for p in ledger.panels if p.scope != R.WET_LAB]
    wet = [p for p in ledger.panels if p.scope == R.WET_LAB]
    assert len(in_scope) == 10
    assert len(wet) == 3  # 5D/5E/5F: IHC / RT-qPCR / PROTEOSTAT
    # The universe golden is the deterministic anchor (must-be-exact ID-set count).
    sig = ledger.panel("5sig")
    assert any(g.metric == "universe" and g.deterministic and g.value == 1133 for g in sig.golden)


def test_form_claim_panels_have_notes_not_goldens():
    # 5A/5B/6C are reproduced by form+claim — no printed number to match.
    ledger = RP.build_ledger()
    for key in ("5A", "5B", "6C"):
        panel = ledger.panel(key)
        assert panel.golden == []
        assert panel.note  # the engine records WHY there's no golden


# --- the captured drive = the findings-first scorecard ------------------------


def test_captured_scorecard_matches_the_dogfood_verdicts():
    ledger = RP.drive_captured()
    sc = ledger.scorecard
    assert sc.n_panels == 13
    assert sc.n_in_scope == 10
    # Findings-first headline — what the engine SURFACED (not buried under failures).
    assert sc.findings["reproduced"] == 9             # faithful in-scope metrics (universe/5C/6A/6F/6G)
    assert sc.findings["paper_irreproducible"] == 2   # signature.count + signature.down_both
    assert sc.findings["structural_limit"] == 2       # 6D rod2_fold LCA-1 + MS-VUS
    assert sc.findings["engine_delta"] == 1           # 6E rod2_enriched_terms (gseapy << fgsea)
    assert sc.findings["upstream_delta"] == 1         # 6E allthree_core (52-term core)
    assert sc.findings["selom_engine_bugs"] == 0      # the engine found NO real Selom bug
    # Blame + verdict totals (18 in-scope-or-wet metrics across the ledger).
    assert sc.totals_by_blame[R.OUT_OF_SCOPE] == 3    # 5D/5E/5F wet-lab
    assert sc.totals_by_verdict[R.EXACT] == 2         # universe + n_cell_types
    assert sum(sc.totals_by_verdict.values()) == 18
    # The Fig 5 methods-vs-numbers inconsistency is recorded on the paper.
    assert any(i.kind == "methods_vs_numbers" for i in ledger.paper.inconsistencies)


def _blame(ledger, panel_key, metric):
    val = next(v for v in ledger.validations if v.panel_key == panel_key)
    return next(r for r in val.results if r.metric == metric).blame


def test_captured_per_metric_blame_is_disambiguated():
    ledger = RP.drive_captured()
    # The Fig 5 headline: edgeR (authors' own tool) misses the printed count too.
    assert _blame(ledger, "5sig", "signature.count") == R.PAPER_IRREPRODUCIBLE
    assert _blame(ledger, "5sig", "signature.down_both") == R.PAPER_IRREPRODUCIBLE
    assert _blame(ledger, "5sig", "universe") is None  # deterministic, exact
    # 6E: the engine-vs-upstream split (the mission in one panel).
    assert _blame(ledger, "6E", "rod2_enriched_terms") == R.ENGINE_DELTA
    assert _blame(ledger, "6E", "allthree_core") == R.UPSTREAM_DELTA
    # 6D: batch ≈ genotype from the 1-control deposit — structural, not a Selom error.
    assert _blame(ledger, "6D", "rod2_fold.MSVUS") == R.STRUCTURAL_LIMIT
    # Close-but-not-exact gene magnitudes with no oracle degrade honestly.
    assert _blame(ledger, "5C", "RHO.pct_LCA1") == R.DELTA_UNMEASURED


def test_captured_ledger_round_trips(tmp_path):
    ledger = RP.drive_captured()
    assert R.save_ledger(ledger, root=tmp_path).exists()
    again = R.load_ledger("rpgrip1", root=tmp_path)
    assert again.scorecard.findings["paper_irreproducible"] == 2
    assert _blame(again, "6E", "allthree_core") == R.UPSTREAM_DELTA
    assert len(again.panels) == 13
