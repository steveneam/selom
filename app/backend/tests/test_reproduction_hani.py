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
from reproduction.papers import hani as HN


# --- ledger construction (the structured target spec) -------------------------


def test_build_ledger_shape():
    ledger = HN.build_ledger()
    assert ledger.paper.id == "hani"
    assert ledger.paper.doi == "10.1016/j.stemcr.2022.12.002"
    assert ledger.paper.geo == ["GSE201356"]
    assert len(ledger.panels) == 8
    in_scope = [p for p in ledger.panels if p.scope not in R.OUT_OF_SCOPE_SCOPES]
    assert len(in_scope) == 7
    # Fig 4C (maturation scatter) is wired to the regression skill with a directional figure-read
    # golden. Fig 2B is deliberately NOT wired — its caption (pairwise PVCA batch-effect heatmap)
    # does not match the pvca-bar skill or a "cell type dominates" claim (figure-repro discipline).
    assert ledger.panel("4C").skill_id == "regression"
    assert ledger.panel("4C").golden[0].metric == "age_association"
    assert all(p.key != "2B" for p in ledger.panels)
    # Fig 3 (verified against the panel screenshots): there is NO UpSet in the paper. 3A is the
    # PubMed known/novel split (the violin skill, ★B); 3C is the deposited Cepo marker matrix.
    assert ledger.panel("3A").skill_id == "violin"
    assert ledger.panel("3C").skill_id == "cepo" and ledger.panel("3C").chart_form == "dotplot"
    assert all(p.key != "3B" for p in ledger.panels)  # 3B is the Cepo-stats violin, not wired
    # The IHC panel (Fig 6E) is the one wet-lab readout (guard 7), excluded from the denominator.
    assert ledger.panel("6E").scope == R.WET_LAB
    # Every panel carries source provenance; nothing diverges from its figure (a clean paper).
    assert ledger.panel("3C").provenance == "mmc2+ Fig3C+"
    assert all(p.diverges_from == [] for p in ledger.panels)


# --- the captured drive = the findings-first scorecard ------------------------


def test_captured_scorecard_is_a_clean_reproducible_paper():
    ledger = HN.drive_captured()
    sc = ledger.scorecard
    assert sc.n_panels == 8
    assert sc.n_in_scope == 7                          # the IHC panel is out of the denominator
    assert sc.findings["reproduced"] == 13            # faithful golden metrics across in-scope panels
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
    # Fig 3C: the deposited Cepo marker matrix (mmc2) reproduced exactly — the headline win
    # (Selom's proprietary cepo skill was validated against this deposited oracle).
    ledger = HN.drive_captured()
    for metric in ("markers_per_type", "n_marker_genes", "n_type_specific", "n_shared"):
        assert _blame(ledger, "3C", metric) is None
    # The wet-lab IHC panel (Fig 6E) is out of scope, not a blame.
    assert _blame(ledger, "6E", "ihc") == R.OUT_OF_SCOPE


def test_known_novel_marker_split_reproduces():
    # Fig 3A: the known-vs-novel literature split (★B's annotate=pubmed) — known markers carry
    # higher PubMed query counts than novel markers. A faithful directional figure-read.
    ledger = HN.drive_captured()
    assert _blame(ledger, "3A", "known_vs_novel_citations") is None


def test_maturation_panel_reproduces_directionally():
    # Fig 4C (regression scatter) is a directional figure-read golden read off the caption: Cepo
    # cell-identity statistics are associated with developmental age in BOTH directions — a faithful
    # (un-blamed) string match, not an exact number, and not the (unsupported) single-positive trend.
    ledger = HN.drive_captured()
    assert _blame(ledger, "4C", "age_association") is None


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
    assert again.scorecard.findings["reproduced"] == 13
    assert again.panel("3C").provenance == "mmc2+ Fig3C+"
    assert _blame(again, "3C", "n_marker_genes") is None
    assert len(again.panels) == 8


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
    assert _blame(ledger, "3C", "n_marker_genes") is None


# --- live organoid drive on the deposited GSE201356 scRNA (skipped if absent) --

ORGANOID_H5AD = Path("D:/selom-data/hani/processed/hani_irpe_subset.h5ad")


@pytest.mark.skipif(not ORGANOID_H5AD.exists(),
                    reason="Hani organoid h5ad not present (owner machine only)")
def test_live_organoid_drive_reproduces_fig6a():
    ledger, summary = HN.drive_live_organoid(h5ad_path=ORGANOID_H5AD)
    # The 4 deposited 10x libraries + rod-dominance are re-derived straight from the data.
    assert summary["organoid_scrna"]["n_libraries"] == 4
    assert summary["organoid_scrna"]["n_cells"] > 0
    assert summary["organoid_scrna"]["n_clusters"] >= 2
    assert summary["rod_dominance"]["dominant_lineage"] == "Rods"
    assert summary["live_matches_deposit"] is True
    # The live-derived Fig 6A metrics are faithful (un-blamed); the cohort facts stay figure-read.
    assert _blame(ledger, "6A", "n_libraries") is None
    assert _blame(ledger, "6A", "dominant_lineage") is None
