"""P1 step 3 — "is-my-data-clean?" QC: honest, modality-aware problem flags (E3).

Each test drives a DataBundle with an explicit kind so the QC logic is exercised
independently of classify(). A `block` flag means a misleading-analysis risk (warn +
override, D-e5); `warn`/`info` annotate but proceed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine import BULK_COUNTS, DE_RESULTS, SC_COUNTS, DataBundle, run_qc
from engine.models import PROTEOMICS

RNG = np.random.default_rng(2)


def _codes(report):
    return {f.code for f in report.flags}


def test_clean_bulk_counts_is_ok():
    df = pd.DataFrame(
        RNG.integers(0, 400, size=(50, 6)),
        index=[f"g{i}" for i in range(50)],
        columns=[f"s{j}" for j in range(6)],
    )
    rep = run_qc(DataBundle(payload=df, kind=BULK_COUNTS))
    assert rep.ran is True
    assert rep.ok is True
    assert rep.blocked is False
    assert rep.stats["n_numeric_cols"] == 6


def test_non_integer_counts_blocks():
    df = pd.DataFrame(
        RNG.normal(5.0, 1.0, size=(20, 4)),  # fractional -> not raw counts
        columns=[f"s{j}" for j in range(4)],
    )
    rep = run_qc(DataBundle(payload=df, kind=BULK_COUNTS))
    assert rep.blocked is True
    assert "non_integer_counts" in _codes(rep)


def test_negative_counts_block():
    df = pd.DataFrame(
        RNG.integers(-5, 5, size=(20, 4)), columns=[f"s{j}" for j in range(4)]
    )
    rep = run_qc(DataBundle(payload=df, kind=BULK_COUNTS))
    assert rep.blocked is True
    assert "negative_counts" in _codes(rep)


def test_proteomics_all_missing_row_warns():
    arr = RNG.normal(20.0, 2.0, size=(30, 6))
    arr[0, :] = np.nan  # a never-detected protein
    arr[RNG.random((30, 6)) < 0.1] = np.nan
    df = pd.DataFrame(arr, columns=[f"s{j}" for j in range(6)])
    rep = run_qc(DataBundle(payload=df, kind=PROTEOMICS))
    assert "all_missing_rows" in _codes(rep)
    assert rep.ok is False  # a warn drops ok, but does not block
    assert rep.blocked is False


def test_de_results_pvalue_out_of_range_warns():
    df = pd.DataFrame(
        {"gene": ["A", "B"], "log2FoldChange": [1.0, -1.0], "padj": [0.01, 3.5]}
    )
    rep = run_qc(DataBundle(payload=df, kind=DE_RESULTS))
    assert "pvalue_out_of_range" in _codes(rep)


def test_empty_table_blocks():
    df = pd.DataFrame({"name": ["x", "y"]})  # no numeric columns
    rep = run_qc(DataBundle(payload=df, kind=BULK_COUNTS))
    assert rep.blocked is True
    assert "empty" in _codes(rep)


def test_wide_bulk_matrix_warns_maybe_transposed():
    # 3 rows (samples) x 20 numeric columns (genes): a count matrix is genes x samples (tall),
    # so far more numeric columns than rows means the table was probably dropped transposed.
    df = pd.DataFrame(RNG.integers(0, 100, size=(3, 20)), columns=[f"g{j}" for j in range(20)])
    rep = run_qc(DataBundle(payload=df, kind=BULK_COUNTS))
    assert "maybe_transposed" in _codes(rep)
    assert rep.ok is False        # a warn drops ok
    assert rep.blocked is False   # but does not hard-block — the user can override


def test_tall_bulk_matrix_no_transpose_warning():
    df = pd.DataFrame(RNG.integers(0, 400, size=(50, 6)), columns=[f"s{j}" for j in range(6)])
    rep = run_qc(DataBundle(payload=df, kind=BULK_COUNTS))
    assert "maybe_transposed" not in _codes(rep)


def test_anndata_clean_counts_ok():
    ad = pytest.importorskip("anndata")
    X = RNG.poisson(1.0, size=(40, 8)).astype("float32")
    adata = ad.AnnData(X)
    rep = run_qc(DataBundle(payload=adata, kind=SC_COUNTS))
    assert rep.ok is True
    assert rep.stats["n_cells"] == 40


def test_anndata_normalized_warns_not_raw_counts():
    ad = pytest.importorskip("anndata")
    X = RNG.random((30, 6)).astype("float32") * 4.0  # fractional -> normalized
    adata = ad.AnnData(X)
    rep = run_qc(DataBundle(payload=adata, kind=SC_COUNTS))
    assert "not_raw_counts" in _codes(rep)


def test_anndata_high_mito_warns():
    ad = pytest.importorskip("anndata")
    base = RNG.poisson(1.0, size=(20, 5)).astype("float32")
    mito = RNG.poisson(20.0, size=(20, 2)).astype("float32")  # dominant MT- counts
    X = np.hstack([base, mito])
    var = pd.DataFrame(index=["GENE1", "GENE2", "GENE3", "GENE4", "GENE5", "MT-ND1", "MT-CO1"])
    adata = ad.AnnData(X, var=var)
    rep = run_qc(DataBundle(payload=adata, kind=SC_COUNTS))
    assert "high_mito" in _codes(rep)
    assert rep.stats["median_pct_mito"] > 20.0
