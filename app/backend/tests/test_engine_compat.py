"""engine/compat.py — the data-fit scorer (Slice 2: "is this dropped data good for this analysis?").

Real files on disk so the classifier + QC actually run (not stubbed): the fit score is only honest
if it reflects what ``engine.ingest`` truly reads. The load-bearing assertions are the **honesty
rule** — a certain payload-class mismatch gates (a flat table → a single-cell skill), while an
unreadable / modality-unclear file stays optimistic (never gated on a guess).
"""

from __future__ import annotations

import pandas as pd

from engine import compat
from engine.models import BULK_COUNTS, DE_RESULTS, GENERIC_TABLE


# --- fixtures: real tabular files the engine can classify ----------------------


def _de_csv(tmp_path):
    p = tmp_path / "de.csv"
    pd.DataFrame({"gene": ["A", "B", "C"], "log2FoldChange": [2.0, -1.5, 0.1],
                  "padj": [0.001, 0.02, 0.9]}).to_csv(p, index=False)
    return str(p)


def _counts_csv(tmp_path):
    p = tmp_path / "counts.csv"
    pd.DataFrame({"gene": ["A", "B"], "s1": [10, 0], "s2": [5, 3], "s3": [8, 1]}).to_csv(p, index=False)
    return str(p)


def _qc_table_csv(tmp_path):
    # a single-cell QC summary (the dogfood meta-finding shape): sample names + mixed numerics.
    p = tmp_path / "qc.csv"
    pd.DataFrame({"sample": ["s1", "s2"], "estimated_cells": [5000, 6200],
                  "median_genes": [1500.5, 1480.2], "frac_mito": [0.08, 0.11]}).to_csv(p, index=False)
    return str(p)


# --- per-file assessment -------------------------------------------------------


def test_assess_file_classifies_and_scores_quality(tmp_path):
    fa = compat.assess_file(_de_csv(tmp_path))
    assert fa.loadable and fa.kind == DE_RESULTS and fa.quality == 100 and fa.qc_ok
    assert fa.filename == "de.csv"


def test_assess_file_unreadable_is_honest_not_a_raise(tmp_path):
    fa = compat.assess_file(str(tmp_path / "does-not-exist.csv"))
    assert not fa.loadable and fa.kind == "unknown" and fa.quality == 0
    assert "couldn't read" in fa.note


def test_assess_counts_table_is_bulk(tmp_path):
    fa = compat.assess_file(_counts_csv(tmp_path))
    assert fa.kind == BULK_COUNTS and fa.loadable


# --- per-(file, skill) fit + the honesty rule ----------------------------------


def test_de_table_fits_volcano(tmp_path):
    f = compat.fit("volcano", compat.assess_file(_de_csv(tmp_path)))
    assert f.compatible is True and f.verdict == "fit" and f.score == 100 and not f.gated


def test_flat_table_is_a_certain_mismatch_for_a_single_cell_skill(tmp_path):
    # the Yoshimura case: a QC table can NEVER be the single-cell matrix umap_scrna needs.
    f = compat.fit("umap_scrna", compat.assess_file(_qc_table_csv(tmp_path)))
    assert f.compatible is False and f.verdict == "wrong_modality" and f.gated
    assert "single-cell matrix" in f.reason


def test_unreadable_file_stays_optimistic_never_gated(tmp_path):
    f = compat.fit("umap_scrna", compat.assess_file(str(tmp_path / "nope.h5ad")))
    assert f.compatible is None and f.verdict == "unreadable" and not f.gated


def test_skill_without_a_modality_constraint_is_never_gated(tmp_path):
    # pca has no modality requirement → any loadable table is optimistic, never a certain mismatch.
    f = compat.fit("pca", compat.assess_file(_qc_table_csv(tmp_path)))
    assert f.compatible is None and not f.gated


def test_schema_layer_gates_a_table_missing_the_required_columns(tmp_path):
    # the owner's L1 ask: recognize the actual COLUMNS. A generic table without a fold-change /
    # p-value column can't feed volcano — gate it with an actionable reason, don't force a run.
    p = tmp_path / "g.csv"
    pd.DataFrame({"name": ["x", "y"], "score": [1.2, 3.4]}).to_csv(p, index=False)
    fa = compat.assess_file(str(p))
    assert fa.kind == GENERIC_TABLE
    f = compat.fit("volcano", fa)
    assert f.compatible is False and f.verdict == "missing_columns" and f.gated
    assert "fold-change" in f.reason and "significance" in f.reason


def test_schema_layer_upgrades_an_unclassified_table_that_has_the_columns(tmp_path):
    # symmetric: a table the modality classifier left GENERIC but which DOES carry log2FC + padj is
    # recognized as a fit by the column schema (precise > coarse).
    p = tmp_path / "deish.csv"
    pd.DataFrame({"name": ["A", "B"], "avg_log2FC": [1.1, -2.0], "p_val_adj": [0.01, 0.2],
                  "note": ["x", "y"]}).to_csv(p, index=False)
    f = compat.fit("volcano", compat.assess_file(str(p)))
    assert f.compatible is True and f.verdict == "fit" and "fits volcano" in f.reason


def test_schema_layer_checks_gsea_needs_a_ranked_list(tmp_path):
    ranked = tmp_path / "rank.csv"
    pd.DataFrame({"gene": ["A", "B", "C"], "score": [3.1, 0.2, -1.4]}).to_csv(ranked, index=False)
    assert compat.fit("gsea", compat.assess_file(str(ranked))).compatible is True
    nolabel = tmp_path / "nolabel.csv"
    pd.DataFrame({"x": [1, 2], "y": [3, 4]}).to_csv(nolabel, index=False)
    bad = compat.fit("gsea", compat.assess_file(str(nolabel)))
    assert bad.compatible is False and "gene" in bad.reason


def test_dirty_data_lowers_the_fit_score(tmp_path):
    # negative values where bulk counts are expected → a QC block → fit drops below a clean fit.
    p = tmp_path / "neg.csv"
    pd.DataFrame({"gene": ["A", "B"], "s1": [-3, 2], "s2": [4, 1]}).to_csv(p, index=False)
    f = compat.fit("deg", compat.assess_file(str(p)))
    assert f.compatible is True and f.verdict == "fit_dirty" and f.score < 100 and not f.qc_ok


# --- ranking + best_match (the matcher entry point) ----------------------------


def test_rank_orders_fit_over_wrong(tmp_path):
    fits = compat.rank("volcano", [_de_csv(tmp_path), _qc_table_csv(tmp_path)])
    assert fits[0].kind == DE_RESULTS and fits[0].compatible is True
    assert fits[-1].gated  # the non-DE table sinks to the bottom


def test_best_match_picks_the_compatible_file(tmp_path):
    de, qc = _de_csv(tmp_path), _qc_table_csv(tmp_path)
    path, f, note = compat.best_match("volcano", [qc, de])
    assert path == de and f.compatible is True and "fit" in note


def test_best_match_returns_none_when_every_candidate_is_a_certain_mismatch(tmp_path):
    # a single-cell skill with only a flat QC table → honest data_unmatched, never a forced run.
    path, f, reason = compat.best_match("umap_scrna", [_qc_table_csv(tmp_path)])
    assert path is None and f is not None and f.gated and "needs" in reason


def test_best_match_optimistic_on_unloadable_paths(tmp_path):
    # fake paths (every existing drive unit test) are unloadable → optimistic, still fed.
    path, f, note = compat.best_match("umap_scrna", ["a.csv", "b.csv"])
    assert path == "a.csv" and "ambiguous" in note


def test_confidence_band_translates_the_score(tmp_path):
    # the number must MEAN something: a clean DE table → Confident for volcano; a QC table → Not a fit.
    de = compat.fit("volcano", compat.assess_file(_de_csv(tmp_path)))
    assert de.confidence == compat.CONF_CONFIDENT and "Confident" in de.confidence_label
    qc = compat.fit("umap_scrna", compat.assess_file(_qc_table_csv(tmp_path)))
    assert qc.confidence == compat.CONF_NOT_A_FIT and "Not a fit" in qc.confidence_label
    bad = compat.fit("umap_scrna", compat.assess_file(str(tmp_path / "nope.h5ad")))
    assert bad.confidence == compat.CONF_UNREADABLE


def test_dirty_but_right_data_is_usable_not_confident(tmp_path):
    p = tmp_path / "neg.csv"
    pd.DataFrame({"gene": ["A", "B"], "s1": [-3, 2], "s2": [4, 1]}).to_csv(p, index=False)
    f = compat.fit("deg", compat.assess_file(str(p)))
    assert f.compatible is True and f.confidence == compat.CONF_USABLE


def test_report_files_ranks_dropped_data_with_a_headline_band(tmp_path):
    de, qc = _de_csv(tmp_path), _qc_table_csv(tmp_path)
    rows = compat.report_files([de, qc], ["volcano", "umap_scrna"])
    by_name = {r.filename: r for r in rows}
    assert by_name["de.csv"].confidence == compat.CONF_CONFIDENT and by_name["de.csv"].best_skill == "volcano"
    # the QC table fits neither analysis here → its best is a non-fit, surfaced honestly.
    assert by_name["qc.csv"].confidence in (compat.CONF_NOT_A_FIT, compat.CONF_UNCERTAIN)


def test_inventory_caches_one_assessment_per_path(tmp_path):
    de = _de_csv(tmp_path)
    inv = compat.inventory([de])
    assert set(inv) == {de} and inv[de].kind == DE_RESULTS
    # reused by best_match without re-loading
    path, f, _ = compat.best_match("volcano", [de], assessments=inv)
    assert path == de and f.compatible is True
