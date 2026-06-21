"""P1a — the canonical DataBundle + the layered modality classifier.

The synthetic frames here encode the *real* column/dtype signatures of Selom's staged
datasets ([[selom-real-datasets]]): DESeq2/Seurat DE tables, integer bulk count matrices,
proteomics intensity matrices with MNAR missingness, single-cell AnnData. See
``docs/engine-spine/spec.md`` Sec 3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine import (
    BULK_COUNTS,
    DE_RESULTS,
    GENERIC_TABLE,
    METABOLOMICS,
    SC_COUNTS,
    UNKNOWN,
    DataBundle,
    classify,
)
from engine.models import PROTEOMICS, QCReport, SourceRef

RNG = np.random.default_rng(0)


def test_anndata_is_single_cell():
    ad = pytest.importorskip("anndata")
    X = RNG.poisson(1.0, size=(12, 6)).astype("float32")
    adata = ad.AnnData(X)
    assert classify(adata) == SC_COUNTS


def test_deseq2_table_is_de_results():
    df = pd.DataFrame(
        {
            "gene": ["RHO", "RPGR", "PRPH2"],
            "baseMean": [120.0, 88.0, 45.0],
            "log2FoldChange": [1.4, -2.1, 0.3],
            "pvalue": [0.001, 0.02, 0.4],
            "padj": [0.01, 0.05, 0.6],
        }
    )
    assert classify(df) == DE_RESULTS


def test_seurat_markers_table_is_de_results():
    # Seurat FindMarkers signature: avg_log2FC + p_val + p_val_adj.
    df = pd.DataFrame(
        {
            "gene": ["A", "B"],
            "avg_log2FC": [0.8, -0.5],
            "p_val": [1e-9, 0.3],
            "p_val_adj": [1e-6, 0.9],
        }
    )
    assert classify(df) == DE_RESULTS


def test_integer_matrix_is_bulk_counts():
    df = pd.DataFrame(
        RNG.integers(0, 500, size=(40, 6)),
        index=[f"ENSG{i:05d}" for i in range(40)],
        columns=[f"sample{j}" for j in range(6)],
    )
    assert classify(df) == BULK_COUNTS


def test_intensity_matrix_with_missing_is_proteomics():
    arr = RNG.normal(20.0, 2.0, size=(60, 6))
    mask = RNG.random((60, 6)) < 0.2  # ~20% MNAR missing (below detection)
    arr[mask] = np.nan
    df = pd.DataFrame(
        arr, index=[f"P{i:04d}" for i in range(60)], columns=[f"s{j}" for j in range(6)]
    )
    assert classify(df) == PROTEOMICS


def test_mz_labelled_matrix_is_metabolomics():
    df = pd.DataFrame(
        RNG.normal(5.0, 1.0, size=(20, 4)),
        index=[f"{120 + i}.1834" for i in range(20)],  # m/z-like feature labels
        columns=list("abcd"),
    )
    assert classify(df) == METABOLOMICS


def test_mixed_table_is_generic():
    df = pd.DataFrame(
        {"name": ["x", "y", "z"], "category": ["a", "b", "a"], "score": [0.5, 0.7, 0.2]}
    )
    assert classify(df) == GENERIC_TABLE


def test_non_table_is_unknown():
    assert classify([1, 2, 3]) == UNKNOWN
    assert classify("a paper title") == UNKNOWN
    assert classify(None) == UNKNOWN


def test_hint_overrides_detection():
    df = pd.DataFrame({"name": ["x"], "score": [0.5]})
    assert classify(df) == GENERIC_TABLE
    assert classify(df, hint=BULK_COUNTS) == BULK_COUNTS


def test_databundle_defaults_are_honest():
    df = pd.DataFrame({"a": [1]})
    db = DataBundle(payload=df)
    assert db.kind == UNKNOWN          # not classified until asked
    assert db.qc.ran is False          # QC not run yet
    assert db.qc.ok is True
    assert db.source.filename == ""
    assert db.design is None


def test_databundle_carries_classification_and_source():
    df = pd.DataFrame(
        {"gene": ["A"], "log2FoldChange": [1.0], "padj": [0.01]}
    )
    db = DataBundle(
        payload=df,
        kind=classify(df),
        source=SourceRef(filename="ST6.csv", sheet="DE"),
        qc=QCReport(ran=True, ok=True),
    )
    assert db.kind == DE_RESULTS
    assert db.source.filename == "ST6.csv"
    assert db.qc.blocked is False
