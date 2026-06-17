"""Kim/Hani end-to-end integration: the THIRD real ledger driven through the engine.

The second cross-paper overfit check, and the first on a paper whose quantitative content is
figure-/deposit-borne rather than printed DE counts (a retinal-cell-identity meta-atlas + an
organoid-fidelity benchmark; Cepo markers, correlation heatmaps, an UpSet). Replays the verified
observations — the Cepo marker matrix re-derived from the deposited mmc2.csv, the atlas
composition, the benchmark cohort — through the engine and asserts the scorecard it *produces*.
The live marker recount from the deposited csv is the dev CLI (``python -m reproduction_hani
--live``) and a skipped-if-absent integration test below.
"""

from pathlib import Path

import pytest

import reproduction as R
import reproduction_hani as HN


# --- ledger construction (the structured target spec) -------------------------


def test_build_ledger_shape():
    ledger = HN.build_ledger()
    assert ledger.paper.id == "hani"
    assert ledger.paper.doi == "10.1016/j.stemcr.2022.12.002"
    assert ledger.paper.geo == ["GSE201356"]
    assert len(ledger.panels) == 6
    in_scope = [p for p in ledger.panels if p.scope not in R.OUT_OF_SCOPE_SCOPES]
    assert len(in_scope) == 5
    # The IHC panel is the one wet-lab readout (guard 7), excluded from the denominator.
    assert ledger.panel("6D").scope == R.WET_LAB
    # Every panel carries source provenance; nothing diverges from its figure (a clean paper).
    assert ledger.panel("3B").provenance == "mmc2+ Fig3+"
    assert all(p.diverges_from == [] for p in ledger.panels)


# --- the captured drive = the findings-first scorecard ------------------------


def test_captured_scorecard_is_a_clean_reproducible_paper():
    ledger = HN.drive_captured()
    sc = ledger.scorecard
    assert sc.n_panels == 6
    assert sc.n_in_scope == 5                          # the IHC panel is out of the denominator
    assert sc.findings["reproduced"] == 9             # faithful golden metrics across in-scope panels
    assert sc.findings["paper_irreproducible"] == 0
    assert sc.findings["structural_limit"] == 0
    assert sc.findings["engine_delta"] == 0
    assert sc.findings["upstream_delta"] == 0
    assert sc.findings["selom_engine_bugs"] == 0      # cross-paper: no overfit, no engine defect
    assert sc.totals_by_blame[R.OUT_OF_SCOPE] == 1    # the wet-lab IHC panel
    assert sc.provenance_divergences == []            # nothing diverges from its figure


def _blame(ledger, panel_key, metric):
    val = next(v for v in ledger.validations if v.panel_key == panel_key)
    return next(r for r in val.results if r.metric == metric).blame


def test_cepo_marker_matrix_is_deposit_faithful():
    # Fig 3B: the deposited Cepo marker matrix (mmc2) reproduced exactly — the headline win
    # (Selom's cepo skill was validated against this oracle; the upset skill renders it).
    ledger = HN.drive_captured()
    for metric in ("markers_per_type", "n_marker_genes", "n_type_specific", "n_shared"):
        assert _blame(ledger, "3B", metric) is None
    # The wet-lab IHC panel is out of scope, not a blame.
    assert _blame(ledger, "6D", "ihc") == R.OUT_OF_SCOPE


def test_reproducibility_score_is_high_and_zero_defect():
    # Three papers now span the spectrum: RPGRIP1 63 (hard) / JEV 86 / Hani ~96 (clean deposit).
    ledger = HN.drive_captured()
    score = ledger.scorecard.score
    assert score.selom_confidence == 100              # zero Selom defects
    assert score.reproducibility >= 90                # a cleanly reproducible paper


def test_captured_ledger_round_trips(tmp_path):
    ledger = HN.drive_captured()
    assert R.save_ledger(ledger, root=tmp_path).exists()
    again = R.load_ledger("hani", root=tmp_path)
    assert again.scorecard.findings["reproduced"] == 9
    assert again.panel("3B").provenance == "mmc2+ Fig3+"
    assert _blame(again, "3B", "n_marker_genes") is None
    assert len(again.panels) == 6


# --- live marker recount from the deposited mmc2.csv (skipped if absent) -------

MMC2 = Path("C:/Users/seamegdool/Desktop/Claude code and website tips/Data/Hani/"
            "1-s2.0-S2213671122005914-mmc2.csv")


@pytest.mark.skipif(not MMC2.exists(), reason="Hani mmc2.csv not present (owner machine only)")
def test_live_marker_recount_matches_the_deposit():
    ledger, summary = HN.drive_live_markers(csv_path=MMC2)
    assert summary["captured_matches_live"] is True
    mm = summary["marker_matrix"]
    assert mm["markers_per_type"] == 50 and mm["n_cell_types"] == 9
    assert mm["n_marker_genes"] == 405
    assert mm["n_type_specific"] == 360 and mm["n_shared"] == 45
    assert mm["n_assignments"] == 450
    # Driven live, the deposit panel is still a faithful (un-blamed) reproduction.
    assert _blame(ledger, "3B", "n_marker_genes") is None
