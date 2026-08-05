"""What the `deg` / `diff_abundance` companions may and may not CLAIM.

`deg` is four engines behind one `mode` knob (`deg/run_real.py:30-40`), and until 2026-08-05 one
paragraph described all of them at once. Six claims were false on live paths, all green through
nine gates, because the prose↔param guard checks that a param is MENTIONED — not that the sentence
is TRUE. The peer of `test_violin_grouping.py` and `test_erg_adaptation.py`: one file per
printed-vs-computed family, pinning the claim rather than the wording.

The shared shape: **a claim about the run is made from the run's recorded outcome, not from the
param.** Four of the six could not be fixed by quoting a param at all — `mode="auto"` resolves from
the file extension, a missing `groupby` column makes the runner cluster the cells itself, a blank
`sample_col` resolves through an alias list, and the engine can silently degrade twice over. The
runner records each in `layout.meta.deg`; `build_body` / `legends._facts` lift them.
"""

from __future__ import annotations

import sys

import anndata as _ad
import numpy as np
import pandas as pd
import pytest

from companions import legends, methods
from skills.contract import load_skill
from skills.deg.run_real import LFC_LABEL, _bulk, _scrna, scrna_statistic_label

try:
    _ad.settings.allow_write_nullable_strings = True
except Exception:  # older/newer anndata without the setting
    pass

DEG = load_skill("deg")
DA = load_skill("diff_abundance")


def _prose(spec, params, figure=None):
    return methods.build_body(spec, params, figure=figure)


@pytest.fixture
def no_pydeseq2(monkeypatch):
    """Hide pyDESeq2 so the bulk engine takes its CPM-log2FC fallback — no model, no p-values."""
    for mod in ("pydeseq2", "pydeseq2.dds", "pydeseq2.ds"):
        monkeypatch.setitem(sys.modules, mod, None)


def _counts_csv(tmp_path, n_genes=40, seed=0):
    """A genes x samples raw-count CSV whose column names carry the group (`ctrl_1` -> `ctrl`)."""
    rng = np.random.default_rng(seed)
    cols = ["ctrl_1", "ctrl_2", "ctrl_3", "treat_1", "treat_2", "treat_3"]
    data = rng.integers(20, 200, size=(n_genes, len(cols)))
    df = pd.DataFrame(data, index=[f"G{i}" for i in range(n_genes)], columns=cols)
    path = tmp_path / "counts.csv"
    df.to_csv(path)
    return str(path)


def _adata(tmp_path, groupby_col="celltype", n_cells=60, n_genes=40, seed=1):
    """A small AnnData carrying ONE categorical obs column, named by `groupby_col`."""
    import anndata as ad

    rng = np.random.default_rng(seed)
    x = rng.integers(0, 40, size=(n_cells, n_genes)).astype(float)
    obs = pd.DataFrame(
        {groupby_col: [("A" if i % 2 else "B") for i in range(n_cells)]},
        index=[f"c{i}" for i in range(n_cells)],
    )
    var = pd.DataFrame(index=[f"G{i}" for i in range(n_genes)])
    path = tmp_path / "cells.h5ad"
    ad.AnnData(X=x, obs=obs, var=var).write_h5ad(path)
    return str(path)


# ---------------------------------------------------------------- the figure's own axis
def test_scrna_bar_names_the_statistic_it_plots_not_a_fold_change(tmp_path):
    """⚑ `_scrna` plots `rank_genes_groups`'s `scores` — scanpy's own docstring calls it "the
    z-score underlying the computation of a p-value", and exposes `logfoldchanges` SEPARATELY (and
    only for t-test-like methods). The axis and the Statistics column both read "log2 fold-change",
    on the default path of the flagship DE skill and on its corpus smoke case."""
    pytest.importorskip("scanpy")
    fig = _scrna(_adata(tmp_path), {"groupby": "celltype", "method": "wilcoxon", "top_n": 5,
                                    "normalize": False})
    assert fig["layout"]["xaxis"]["title"]["text"] == "Wilcoxon z-score"
    assert fig["table"]["columns"] == ["gene", "Wilcoxon z-score"]
    assert LFC_LABEL not in str(fig["layout"]["xaxis"])


def test_the_statistic_label_follows_the_method(tmp_path):
    """`method` reaches `rank_genes_groups` untouched, so the label cannot be hard-coded either."""
    assert scrna_statistic_label("wilcoxon") == "Wilcoxon z-score"
    assert scrna_statistic_label("t-test") == "t-statistic"
    assert scrna_statistic_label("logreg") == "logistic-regression coefficient"


def test_a_deseq2_path_still_says_log2_fold_change(tmp_path, no_pydeseq2):
    """The three DESeq2 paths genuinely produce a fold change — only the scRNA one did not."""
    fig = _bulk(_counts_csv(tmp_path), {"top_n": 5, "min_count": 0})
    assert fig["layout"]["xaxis"]["title"]["text"] == LFC_LABEL


# ---------------------------------------------------------------- (a) the ranking test
def test_prose_names_the_ranking_test_that_actually_ran():
    """The paragraph said "the Wilcoxon rank-sum test" unconditionally while `method` chose."""
    run = {"mode": "scrna", "groupby": "leiden", "method": "t-test"}
    text, _ = _prose(DEG, {}, figure={"layout": {"meta": {"deg": run}}})
    assert "Welch's t-test" in text
    assert "Wilcoxon" not in text


# ---------------------------------------------------------------- (b) the Leiden substitution
def test_prose_says_the_cells_were_clustered_when_the_requested_column_was_absent():
    """The runner clusters the cells itself when `groupby` names no obs column, and the figure title
    has always carried the substituted name while the paragraph carried the REQUESTED one."""
    run = {"mode": "scrna", "groupby": "leiden", "method": "wilcoxon",
           "clustered": True, "requested_groupby": "celltype"}
    text, _ = _prose(DEG, {"groupby": "celltype"}, figure={"layout": {"meta": {"deg": run}}})
    assert "Leiden" in text and "celltype" in text
    assert "ranked per celltype group" not in text


def test_prose_names_the_requested_column_when_no_substitution_happened():
    run = {"mode": "scrna", "groupby": "celltype", "method": "wilcoxon"}
    text, _ = _prose(DEG, {"groupby": "celltype"}, figure={"layout": {"meta": {"deg": run}}})
    assert "ranked per celltype group" in text
    assert "Leiden" not in text


# ---------------------------------------------------------------- (c) the resolved obs columns
def test_pseudobulk_prose_names_the_RESOLVED_replicate_column():
    """A blank `sample_col` falls through `_SAMPLE_FALLBACKS`; the paragraph used to default to the
    literal word "sample", naming a column an h5ad keyed `orig.ident` does not have."""
    run = {"mode": "pseudobulk", "engine": "pyDESeq2 (Wald)",
           "sample_col": "orig.ident", "condition_col": "genotype"}
    text, _ = _prose(DEG, {"mode": "pseudobulk"}, figure={"layout": {"meta": {"deg": run}}})
    assert "orig.ident" in text and "genotype" in text
    assert "(sample)" not in text


# ---------------------------------------------------------------- (d)+(e) the engine fallback
def test_prose_claims_no_test_and_cites_nothing_when_pydeseq2_was_absent():
    """⚑ The sharpest one. `_bulk_deseq` catches ImportError and returns a log2 of mean CPM — no
    model, no test, no p-value — while the paragraph claimed a PyDESeq2 Wald test AND
    Benjamini-Hochberg correction, and CITED all three. The `_boxplot` family, third occurrence."""
    run = {"mode": "bulk", "engine": "CPM log2FC (pyDESeq2 absent)"}
    text, cites = _prose(DEG, {"mode": "bulk"}, figure={"layout": {"meta": {"deg": run}}})
    assert "Wald" not in text and "Benjamini" not in text
    assert "no p-values were computed" in text
    assert not any("DESeq2" in c or "Benjamini" in c for c in cites)


def test_prose_discloses_a_silent_TMM_degrade():
    """`_fit_deseq_with_tmm` falls back to median-of-ratios inside a bare `except Exception`, and
    said so only in the figure subtitle."""
    run = {"mode": "bulk", "engine": "pyDESeq2 (Wald, TMM unavailable)"}
    text, _ = _prose(DEG, {"mode": "bulk", "normalization": "tmm"},
                     figure={"layout": {"meta": {"deg": run}}})
    assert "unavailable" in text and "median-of-ratios" in text


def test_prose_names_TMM_when_TMM_actually_ran():
    run = {"mode": "bulk", "engine": "pyDESeq2 (Wald, TMM norm)"}
    text, cites = _prose(DEG, {"mode": "bulk", "normalization": "tmm"},
                         figure={"layout": {"meta": {"deg": run}}})
    assert "TMM size factors" in text and "unavailable" not in text
    assert any("DESeq2" in c for c in cites)


# ---------------------------------------------------------------- (f) one engine, not two
def test_prose_describes_ONE_engine_when_the_run_says_which():
    """`mode="auto"` resolves to exactly one engine; the sentence claimed both at once."""
    text, _ = _prose(DEG, {}, figure={"layout": {"meta": {"deg": {"mode": "bulk"}}}})
    assert "Scanpy" not in text and "rank_genes_groups" not in text


def test_prose_states_the_SELECTION_RULE_when_the_engine_is_genuinely_unknown():
    """With no figure (the jobs queue, litsynth replay) the engine is not knowable. Describing both
    as though both ran is a lie; guessing one is a lie in the other direction. State the rule."""
    text, cites = _prose(DEG, {})
    assert "selected from the input" in text
    assert "Scanpy" in text and "PyDESeq2" in text
    assert any("DESeq2" in c for c in cites)


# ---------------------------------------------------------------- the undisclosed exclusions
def test_prose_reports_the_gene_filter_every_deseq2_path_applies():
    text, _ = _prose(DEG, {"mode": "bulk", "min_count": 25},
                     figure={"layout": {"meta": {"deg": {"mode": "bulk", "engine": "pyDESeq2 (Wald)"}}}})
    assert "25" in text and "excluded before fitting" in text


def test_prose_reports_dropped_replicates_only_when_some_were_dropped():
    base = {"mode": "pseudobulk", "engine": "pyDESeq2 (Wald)", "sample_col": "sample",
            "condition_col": "condition", "min_cells": 10}
    dropped, _ = _prose(DEG, {"mode": "pseudobulk"},
                        figure={"layout": {"meta": {"deg": {**base, "n_dropped": 2}}}})
    kept, _ = _prose(DEG, {"mode": "pseudobulk"},
                     figure={"layout": {"meta": {"deg": {**base, "n_dropped": 0}}}})
    assert "2 replicate(s)" in dropped and "excluded" in dropped
    assert "replicate(s) with fewer than" not in kept


def test_timecourse_prose_states_whether_the_covariate_adjustment_ACTUALLY_ran():
    """Setting `covariate_col` is not the same as adjusting: the design gains the term only when the
    column resolves to >=2 distinct levels, so a constant column is silently ignored."""
    params = {"mode": "timecourse", "covariate_col": "genotype"}
    on, _ = _prose(DEG, params, figure={"layout": {"meta": {"deg": {
        "mode": "timecourse", "engine": "pyDESeq2 (continuous-time Wald)",
        "covariate_adjusted": True}}}})
    off, _ = _prose(DEG, params, figure={"layout": {"meta": {"deg": {
        "mode": "timecourse", "engine": "pyDESeq2 (continuous-time Wald)",
        "covariate_adjusted": False}}}})
    assert "~genotype + time" in on
    assert "single value" in off and "no adjustment was applied" in off


# ---------------------------------------------------------------- the caption
def test_caption_does_not_call_a_MARKER_ranking_a_differential_expression_contrast():
    """⚑ The caption said "differentially expressed genes for T versus R" on every run. On the
    single-cell path scanpy ranks MARKERS for one cluster against the rest and reads NEITHER
    `reference` NOR `treatment` — so a contrast typed for a later bulk run was printed onto a
    marker figure."""
    figure = {"layout": {"meta": {"deg": {"mode": "scrna", "groupby": "leiden", "group": "0"}}}}
    caption = legends.build(DEG, {"top_n": 15, "reference": "ctrl", "treatment": "treat"},
                           figure=figure)
    assert "marker genes" in caption["text"]
    assert "differentially expressed" not in caption["text"]
    assert "treat" not in caption["text"] and "ctrl" not in caption["text"]


def test_caption_keeps_the_contrast_on_a_real_contrast():
    figure = {"layout": {"meta": {"deg": {"mode": "bulk", "engine": "pyDESeq2 (Wald)"}}}}
    caption = legends.build(DEG, {"top_n": 15, "reference": "ctrl", "treatment": "treat"},
                           figure=figure)
    assert "differentially expressed genes for treat versus ctrl" in caption["text"]


# ---------------------------------------------------------------- diff_abundance
def test_diff_abundance_prose_drops_DESeq2_on_its_own_fallback():
    """Its fallback is a different test on a different quantity — per-sample proportions + Welch."""
    run = {"mode": "diff_abundance", "engine": "proportion log2FC + Welch t (pyDESeq2 absent)",
           "sample_col": "sample", "condition_col": "condition", "label_col": "cell_type"}
    text, cites = _prose(DA, {}, figure={"layout": {"meta": {"deg": run}}})
    assert "Welch's t-test" in text and "PyDESeq2 was not available" in text
    assert "Wald" not in text
    assert not any("DESeq2" in c for c in cites)


def test_diff_abundance_prose_names_the_resolved_columns_and_the_exclusion():
    run = {"mode": "diff_abundance", "engine": "pyDESeq2 (Wald, TMM norm)",
           "sample_col": "orig.ident", "condition_col": "genotype", "label_col": "major_type",
           "min_cells": 25}
    text, _ = _prose(DA, {}, figure={"layout": {"meta": {"deg": run}}})
    assert "major_type" in text and "orig.ident" in text
    assert "fewer than 25 cells" in text and "excluded" in text
