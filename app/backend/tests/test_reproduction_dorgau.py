"""Dorgau 2024 end-to-end integration: the FOURTH real ledger driven through the engine.

The fourth cross-paper overfit check, and the first on a **broad multi-omic** paper where most
figures are out of Selom's scope (spatial / scATAC / IPA / wet-lab). Asserts the honest
narrow-but-deep scorecard the engine *produces*: the Fig 1 scRNA atlas + RPC->T1->T2/T3 lineage
reproduced (deposit-grounded), the scRNA-derived Fig 3H ratio directional, the 6 out-of-scope
figures greyed out (the new ``modality_unsupported`` category, excluded from the denominator), and
zero Selom-engine bugs. The deposit re-derivations (``--markers`` / ``--qc``) are the dev CLI and
skipped-if-absent integration tests below.
"""

from pathlib import Path

import pytest

import reproduction as R
import reproduction_dorgau as DG


# --- ledger construction (the structured target spec) -------------------------


def test_build_ledger_shape():
    ledger = DG.build_ledger()
    assert ledger.paper.id == "dorgau"
    assert ledger.paper.doi == "10.1038/s41467-024-47933-x"
    assert ledger.paper.geo == ["GSE234971", "GSE234963"]
    assert ledger.paper.modality == "scrna"
    assert len(ledger.panels) == 13
    # Fig 1 (A-G) + Fig 3H are in scope; Figs 2-7 reps are out of scope.
    in_scope = [p for p in ledger.panels if p.scope not in R.OUT_OF_SCOPE_SCOPES]
    assert len(in_scope) == 7
    assert {p.key for p in in_scope} == {"1A", "1B", "1C", "1D", "1E", "1G", "3H"}
    # The Melody dogfood: Fig 1A integrates with a recorded Harmony->Melody substitution.
    sub = ledger.panel("1A").method_subs[0]
    assert "Harmony" in sub.paper_tool and "Melody" in sub.selom_tool
    # Pseudotime is the recorded Monocle3 -> DPT engine substitution (panels 1D/1E/1G).
    assert "Monocle" in ledger.panel("1E").method_subs[0].paper_tool
    assert ledger.panel("1E").skill_id == "trajectory"


def test_out_of_scope_modalities_are_classified_honestly():
    ledger = DG.build_ledger()
    # The new modality_unsupported category: spatial (2/3), scATAC (4/5), IPA GRN (6).
    for key in ("2C", "3A", "4B", "5A", "6A"):
        assert ledger.panel(key).scope == R.MODALITY_UNSUPPORTED
    # Fig 7 is the wet-lab functional/IF validation.
    assert ledger.panel("7A").scope == R.WET_LAB
    # All six are out of the denominator.
    oos = [p for p in ledger.panels if p.scope in R.OUT_OF_SCOPE_SCOPES]
    assert len(oos) == 6


# --- the captured drive = the findings-first scorecard ------------------------


def test_captured_scorecard_is_narrow_but_deep():
    ledger = DG.drive_captured()
    sc = ledger.scorecard
    assert sc.n_panels == 13
    assert sc.n_in_scope == 7                          # 6 out-of-scope figures leave the denominator
    assert sc.findings["reproduced"] == 9              # 9 in-scope golden metrics reproduce
    assert sc.findings["paper_irreproducible"] == 0
    assert sc.findings["structural_limit"] == 0
    assert sc.findings["engine_delta"] == 0
    assert sc.findings["upstream_delta"] == 0
    assert sc.findings["selom_engine_bugs"] == 0       # cross-paper: no overfit, no engine defect
    assert sc.totals_by_blame[R.OUT_OF_SCOPE] == 6     # the 6 out-of-scope representative panels
    assert sc.provenance_divergences == []             # nothing diverges from its figure


def _blame(ledger, panel_key, metric):
    val = next(v for v in ledger.validations if v.panel_key == panel_key)
    return next(r for r in val.results if r.metric == metric).blame


def test_fig1_atlas_reproduces_and_substitution_is_recorded():
    # Fig 1A: 43 clusters (res 2.2) / 4 removed — deposit-grounded, faithful (un-blamed).
    ledger = DG.drive_captured()
    assert _blame(ledger, "1A", "n_clusters") is None
    assert _blame(ledger, "1B", "rpc_top_marker") is None
    # The out-of-scope figures are blamed out-of-scope, never a Selom defect.
    assert _blame(ledger, "4B", "out_of_scope_claim") == R.OUT_OF_SCOPE
    assert _blame(ledger, "6A", "out_of_scope_claim") == R.OUT_OF_SCOPE


def test_substituted_panels_cap_at_reproduced_not_verified():
    # A recorded engine substitution (Melody/DPT/scanpy-markers) caps an exact match at
    # "reproduced", never "verified" — honest. The two no-substitution exact panels (1C, 3H) verify.
    ledger = DG.drive_captured()
    scores = {ps.panel_key: ps for ps in ledger.scorecard.panel_scores}
    assert scores["1A"].tier == R.REPRODUCED and scores["1A"].reproducibility == 92
    assert scores["1C"].tier == R.VERIFIED and scores["1C"].reproducibility == 100
    assert scores["3H"].tier == R.VERIFIED
    # Out-of-scope cells are grey (None reproducibility), excluded from the rollup.
    assert scores["4B"].reproducibility is None and scores["4B"].in_scope is False


def test_reproducibility_score_is_high_and_zero_defect():
    # Four papers now span the spectrum: RPGRIP1 63 / JEV 86 / Hani ~96 / Dorgau ~94 (narrow-but-deep:
    # the in-scope scRNA core reproduces; the spatial/ATAC/IPA/wet-lab figures grey out honestly).
    ledger = DG.drive_captured()
    score = ledger.scorecard.score
    assert score.selom_confidence == 100               # zero Selom defects
    assert score.reproducibility >= 90
    assert score.n_in_scope == 7 and score.n_out_of_scope == 6


def test_captured_ledger_round_trips(tmp_path):
    ledger = DG.drive_captured()
    assert R.save_ledger(ledger, root=tmp_path).exists()
    again = R.load_ledger("dorgau", root=tmp_path)
    assert again.scorecard.findings["reproduced"] == 9
    assert len(again.panels) == 13
    assert again.panel("1A").method_subs[0].selom_tool.startswith("Selom Melody")
    assert _blame(again, "1A", "n_clusters") is None


# --- live deposit re-derivations (skipped if the supplements are absent) -------

DORGAU = Path("C:/Users/seamegdool/Desktop/Claude code and website tips/Data/Dorgau")
SUPP1 = DORGAU / "Supplementary Data 1.xlsx"
SUPP2 = DORGAU / "Supplementary Data 2.xlsx"


@pytest.mark.skipif(not SUPP2.exists(), reason="Dorgau Supp Data 2 not present (owner machine only)")
def test_live_marker_table_matches_the_deposit():
    ledger, summary = DG.drive_live_markers(xlsx_path=SUPP2)
    assert summary["captured_matches_live"] is True
    mt = summary["marker_table"]
    assert mt["n_clusters"] == 43
    assert mt["n_cell_type_labels"] == 17
    assert mt["rpc_top_marker"] == "CCND1"
    assert mt["n_branches"] == 4
    # Driven live from the deposit, Fig 1A/B are still faithful (un-blamed) reproductions.
    assert _blame(ledger, "1A", "n_clusters") is None
    assert _blame(ledger, "1B", "n_cell_type_labels") is None


@pytest.mark.skipif(not SUPP1.exists(), reason="Dorgau Supp Data 1 not present (owner machine only)")
def test_live_cohort_qc_matches_the_deposit():
    qc = DG.drive_live_qc(SUPP1)
    assert qc["n_samples"] == 24 and qc["n_samples_matches"] is True
    assert qc["spot_matches"] is True                  # sample 15046: 8073 -> 4713
    assert 0.5 < qc["fraction_retained"] < 0.8         # QC retains a sensible majority of cells


# --- live Fig-1 drive on the raw GSE234963 subset (the Melody dogfood; skipped if absent) -------

FIG1_H5AD = Path("D:/selom-data/dorgau/processed/dorgau_subset.h5ad")


@pytest.mark.skipif(not FIG1_H5AD.exists(),
                    reason="Dorgau scRNA subset not staged (run scripts.stage_dorgau_subset)")
def test_live_fig1_melody_integrates_and_recovers_cell_types():
    ledger, summary = DG.drive_live_fig1(h5ad_path=FIG1_H5AD)
    # The Melody dogfood: batch mixing must increase after integration (the paper used Harmony).
    mix = summary["melody_mixing"]
    assert mix["improved"] is True and mix["after"] > mix["before"]
    # A multi-sample subset with the canonical retinal lineages recovered.
    assert summary["scrna_subset"]["n_samples"] >= 3
    assert summary["n_cell_types_recovered"] >= 4
    # Selom's own integration skill rendered the editable UMAP (one trace per Leiden cluster).
    assert summary["scrna_subset"]["integration_figure_traces"] >= 2
    # The measured live mixing is recorded on the Harmony->Melody substitution.
    assert "batch-mixing" in ledger.panel("1A").method_subs[0].delta_measured
    # Still zero Selom-engine defects, driven live.
    assert ledger.scorecard.findings["selom_engine_bugs"] == 0
