"""Cioanca/JEV end-to-end integration: the SECOND real ledger driven through the engine.

The cross-paper overfit check. RPGRIP1 was a paper Selom under-called whose printed counts were
irreproducible; JEV is the opposite shape — proteomics + miRNA reproduced faithfully against the
deposited tables, a published figure (4e) that diverges from its own deposit (a different
replicate, recorded as the neutral provenance tag ST6+ Fig4e−, not a blame), and a single-cell
pipeline whose data was never deposited. This replays the verified dogfood observations (validated
against the deposit) through the engine and asserts the scorecard it *produces*. The live DE
recount from the workbook is the dev CLI (``python -m reproduction_jev --live``).
"""

import reproduction as R
import reproduction_jev as JV


# --- ledger construction (the structured target spec) -------------------------


def test_build_ledger_shape():
    ledger = JV.build_ledger()
    assert ledger.paper.id == "jev"
    assert ledger.paper.doi == "10.1002/jev2.12393"
    assert len(ledger.panels) == 11
    in_scope = [p for p in ledger.panels if p.scope not in R.OUT_OF_SCOPE_SCOPES]
    demo = [p for p in ledger.panels if p.scope == R.DATA_NOT_DEPOSITED]
    assert len(in_scope) == 7
    assert len(demo) == 4  # Fig 8 single-cell: data never deposited (run on a reference)
    # The two deposit_vs_figure inconsistencies are recorded up front on the paper.
    assert len(ledger.paper.inconsistencies) == 2
    assert all(i.kind == "deposit_vs_figure" for i in ledger.paper.inconsistencies)
    # Every panel carries source provenance (+/−); only Fig 4e diverges from its figure.
    assert ledger.panel("4c").provenance == "ST6+ Fig4c+"
    assert ledger.panel("4e").provenance == "ST6+ Fig4e−"
    assert ledger.panel("4e").diverges_from == ["Fig4e"]
    assert ledger.panel("4c").diverges_from == []


def test_single_cell_panels_are_data_not_deposited():
    # The new scope the JEV paper forced: transcriptomic but not publicly deposited.
    ledger = JV.build_ledger()
    for key in ("8a", "8ann", "8d", "8e"):
        panel = ledger.panel(key)
        assert panel.scope == R.DATA_NOT_DEPOSITED
        assert panel.method_subs and panel.method_subs[0].delta_measured is None


# --- the captured drive = the findings-first scorecard ------------------------


def test_captured_scorecard_is_a_reproducible_paper():
    ledger = JV.drive_captured()
    sc = ledger.scorecard
    assert sc.n_panels == 11
    assert sc.n_in_scope == 7  # the 4 method-demo panels are out of the denominator
    # The headline that RPGRIP1 could not express: a wall of faithful reproductions of the deposit.
    assert sc.findings["reproduced"] == 14
    assert sc.findings["paper_irreproducible"] == 0   # the figure gap is provenance, not a blame
    assert sc.findings["structural_limit"] == 0
    assert sc.findings["engine_delta"] == 0
    assert sc.findings["upstream_delta"] == 0
    assert sc.findings["selom_engine_bugs"] == 0      # Selom faithfully reproduced the deposit
    assert sc.totals_by_blame[R.OUT_OF_SCOPE] == 4    # the single-cell method demo
    # The one figure divergence is surfaced transparently, not blamed.
    assert sc.provenance_divergences == ["4e: ST6+ Fig4e−"]


def _blame(ledger, panel_key, metric):
    val = next(v for v in ledger.validations if v.panel_key == panel_key)
    return next(r for r in val.results if r.metric == metric).blame


def test_captured_faithful_to_deposit_with_provenance_tag():
    ledger = JV.drive_captured()
    # Fig 4e: reconstructed faithfully from the deposited ST6 → a win (no blame); the figure
    # divergence lives in the ST6+ Fig4e− provenance tag, not a paper-error verdict.
    assert _blame(ledger, "4e", "de_total") is None
    assert _blame(ledger, "4e", "de_up") is None
    assert _blame(ledger, "4e", "top_up_protein") is None        # B2M reproduced (exact)
    assert ledger.panel("4e").provenance == "ST6+ Fig4e−"
    # Fig 4c PCA: the cleanest genuine reproduction (Selom computed it from the matrix).
    assert _blame(ledger, "4c", "pc1_var") is None               # 39.7 ≈ 39.8 → exact
    # Fig 1c miRNA: reproduced against ST2 exactly (the figure's +1 is in the Fig1c tag note).
    assert _blame(ledger, "1c", "de_up") is None                 # 12 == 12
    assert _blame(ledger, "1c", "de_down") is None               # 22 == ST2 (figure says 23)
    # Fig 8: out-of-scope because the study's own scRNA was never deposited.
    assert _blame(ledger, "8a", "a") == R.OUT_OF_SCOPE


def test_proteome_sweep_is_the_evidence_behind_fig4e_tag():
    # The sweep is recorded as the evidence behind the neutral Fig4e− provenance tag (the SOP's
    # sweep-before-verdict step): no threshold on the complete deposited Table S6 reaches the
    # figure's printed 180 — most likely a different replicate, not a paper error.
    ledger = JV.drive_captured()
    sweep = next(s for s in ledger.sweeps if s.panel_key == "4e")
    assert sweep.irreproducible is True
    assert sweep.reproducing_setting is None
    assert sweep.stated_value == JV.SEL_PROT_TOTAL       # 447 reconstructed from ST6 @p<0.05
    assert sweep.golden_value == JV.GOLD_PROT_TOTAL      # vs the figure's 180
    assert all(c.value != JV.GOLD_PROT_TOTAL for c in sweep.grid)  # no grid point hits 180


def test_captured_ledger_round_trips(tmp_path):
    ledger = JV.drive_captured()
    assert R.save_ledger(ledger, root=tmp_path).exists()
    again = R.load_ledger("jev", root=tmp_path)
    assert again.scorecard.findings["reproduced"] == 14
    assert again.scorecard.provenance_divergences == ["4e: ST6+ Fig4e−"]
    assert again.panel("4e").provenance == "ST6+ Fig4e−"  # SourceTags survive the round-trip
    assert _blame(again, "4e", "de_total") is None
    assert len(again.panels) == 11
