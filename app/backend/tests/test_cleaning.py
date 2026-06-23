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
