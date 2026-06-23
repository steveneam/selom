"""engine.cleaning — the layered data-type profile + the dynamic cleaning plan.

The profile must NEVER false-positive a specific type (the honesty rule): a plain table stays a
neutral "Data table", and ERG is claimed only on a certain (format) or high-precision (a-/b-wave +
intensity columns) signal. The cleaning plan must be *dynamic*: a count matrix gets the real
proposed steps; a results / generic / ERG table gets an honest EMPTY plan (no gene-subset cleaning).
"""

import pandas as pd

from engine.cleaning import ERG, plan_cleaning, profile_data
from engine.databundle import DataBundle
from engine.models import BULK_COUNTS, DE_RESULTS, GENERIC_TABLE, SC_COUNTS
from engine.models import SourceRef


def _bundle(df: pd.DataFrame, kind: str, filename: str = "x.csv") -> DataBundle:
    return DataBundle(payload=df, kind=kind, source=SourceRef(filename=filename))


# --- profile: layered + honest ----------------------------------------------------------

def test_profile_erg_from_columns_high_precision():
    df = pd.DataFrame({"condition": ["A"], "intensity_log_cd_s_m2": [1.0], "b_wave_uv": [200.0]})
    p = profile_data(_bundle(df, GENERIC_TABLE))
    assert p.code == ERG and p.confidence == "likely"
    assert "wave" in p.reason.lower()


def test_profile_erg_from_iwxdata_format_is_certain():
    # Format is certain about the type regardless of (here, irrelevant) contents.
    df = pd.DataFrame({"t": [0.0, 1.0], "v": [1.0, 2.0]})
    p = profile_data(_bundle(df, GENERIC_TABLE, filename="run01.iwxdata"))
    assert p.code == ERG and p.confidence == "certain"


def test_profile_generic_table_is_not_falsely_typed():
    # A plain numeric table with no ERG signature must stay a neutral "Data table" — never a guess.
    df = pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]})
    p = profile_data(_bundle(df, GENERIC_TABLE))
    assert p.code == GENERIC_TABLE and p.label == "Data table" and p.confidence == "unsure"


def test_profile_kind_fallback_labels():
    p = profile_data(_bundle(pd.DataFrame({"gene": ["A"], "logFC": [1.0], "padj": [0.01]}), DE_RESULTS))
    assert p.code == DE_RESULTS and p.label == "Differential-expression results"


def test_profile_user_override_wins():
    df = pd.DataFrame({"x": [1.0]})
    p = profile_data(_bundle(df, GENERIC_TABLE), override="erg")
    assert p.code == ERG and p.confidence == "certain" and p.overridden is True


# --- profile: general candidates + filename layer (all modalities, not ERG-only) --------

def test_profile_returns_ranked_candidates_with_source_and_reason():
    # Every profile carries a ranked candidate list; the top equals the flat verdict, and each
    # candidate is self-describing (source signal + why) so the FE can offer alternatives.
    p = profile_data(_bundle(pd.DataFrame({"gene": ["A"], "logFC": [1.0], "padj": [0.01]}), DE_RESULTS))
    assert p.candidates and p.candidates[0].code == p.code == DE_RESULTS
    assert all(c.source and c.reason for c in p.candidates)


def test_profile_filename_hint_fills_neutral_gap():
    # Content can't type it (generic), but the NAME says single-cell → propose sc_counts at low
    # confidence (general across modalities, not an ERG special-case), never a false "certain".
    df = pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]})
    p = profile_data(_bundle(df, GENERIC_TABLE, filename="GSE123_scRNA_counts.csv"))
    assert p.code == SC_COUNTS and p.confidence == "unsure"
    chosen = p.candidates[0]
    assert chosen.source == "filename" and "scrna" in chosen.reason.lower()
    # the neutral "Data table" stays available as a lower-ranked alternative
    assert any(c.code == GENERIC_TABLE for c in p.candidates)


def test_profile_content_outranks_filename_with_mismatch_nudge():
    # The name says scRNA but the content is a bulk count matrix → content wins; a mismatch nudge
    # is raised (not an overrule). This is the "metrics CSV misread by its name" guard, generalized.
    df = pd.DataFrame({"gene": [f"g{i}" for i in range(20)],
                       **{f"s{j}": [(i + j) % 5 for i in range(20)] for j in range(3)}})
    p = profile_data(_bundle(df, BULK_COUNTS, filename="scRNA_experiment.csv"))
    assert p.code == BULK_COUNTS
    assert p.mismatch and "single-cell" in p.mismatch.lower()


def test_profile_filename_short_token_no_false_positive():
    # Short keys (erg/deg) match whole tokens only — "merge"/"degradation" must NOT trip them.
    df = pd.DataFrame({"x": [1.0], "y": [2.0]})
    p = profile_data(_bundle(df, GENERIC_TABLE, filename="merge_degradation.csv"))
    assert p.code == GENERIC_TABLE and not p.mismatch


def test_profile_override_keeps_auto_detected_candidate():
    # Override wins, but the auto verdict survives in candidates so the FE can offer "reset to auto".
    df = pd.DataFrame({"gene": [f"g{i}" for i in range(10)],
                       **{f"s{j}": [(i + j) % 4 for i in range(10)] for j in range(2)}})
    p = profile_data(_bundle(df, BULK_COUNTS), override="erg")
    assert p.code == ERG and p.overridden is True
    assert any(c.code == BULK_COUNTS for c in p.candidates)


# --- cleaning plan: dynamic --------------------------------------------------------------

def test_plan_erg_is_empty_no_gene_cleaning():
    df = pd.DataFrame({"condition": ["A"], "intensity_log_cd_s_m2": [1.0], "b_wave_uv": [200.0]})
    plan = plan_cleaning(_bundle(df, GENERIC_TABLE))
    assert plan.applies is False and plan.steps == []
    assert plan.obs_label == "rows" and plan.var_label == "columns"
    assert "used as-is" in plan.note.lower()


def test_plan_generic_table_is_empty():
    plan = plan_cleaning(_bundle(pd.DataFrame({"x": [1.0], "y": [2.0]}), GENERIC_TABLE))
    assert plan.applies is False and plan.steps == []


def test_plan_de_results_is_empty():
    plan = plan_cleaning(_bundle(pd.DataFrame({"gene": ["A"], "logFC": [1.0], "padj": [0.01]}), DE_RESULTS))
    assert plan.applies is False and "no cleaning" in plan.note.lower()


def test_plan_bulk_counts_has_real_steps_and_orientation():
    # 50 genes (rows) x 4 samples (numeric cols). Steps must apply; orientation: samples=cols,
    # genes=rows; the drop-low-genes delta is the real count, not a fabricated number.
    df = pd.DataFrame({"gene": [f"g{i}" for i in range(50)],
                       **{f"s{j}": [(i * j) % 7 for i in range(50)] for j in range(4)}})
    plan = plan_cleaning(_bundle(df, BULK_COUNTS))
    assert plan.applies is True
    assert plan.obs_label == "samples" and plan.var_label == "genes"
    assert plan.n_obs == 4 and plan.n_var == 50
    drop = next(s for s in plan.steps if s.id == "drop_low")
    assert drop.var_delta is not None and drop.var_delta <= 0


def test_plan_sc_counts_real_gene_filter_delta():
    import numpy as np
    import anndata as ad

    # 6 cells x 5 genes; gene 4 is detected in only 1 cell -> dropped by the <3-cells filter.
    X = np.array([
        [1, 0, 2, 0, 0],
        [0, 3, 1, 1, 0],
        [2, 0, 0, 1, 0],
        [0, 1, 4, 0, 0],
        [1, 1, 0, 2, 0],
        [0, 0, 1, 0, 5],
    ], dtype="float64")
    adata = ad.AnnData(X)
    plan = plan_cleaning(_bundle(adata, SC_COUNTS, filename="cells.h5ad"))
    assert plan.applies is True and plan.obs_label == "cells" and plan.var_label == "genes"
    assert plan.n_obs == 6 and plan.n_var == 5
    drop = next(s for s in plan.steps if s.id == "filter_genes")
    assert drop.var_delta == -1  # only the last gene (1 cell) is removed
