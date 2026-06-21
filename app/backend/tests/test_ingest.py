"""P1 step 2 — the ingest registry: drop any supported file -> a classified DataBundle.

Round-trips real on-disk formats (csv/tsv/xlsx/h5ad) through ``ingest`` and asserts the
modality + provenance, mirroring how the staged datasets arrive ([[selom-real-datasets]]).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine import BULK_COUNTS, DE_RESULTS, SC_COUNTS, ingest

RNG = np.random.default_rng(1)


def test_ingest_csv_de_results(tmp_path):
    p = tmp_path / "ST6_de.csv"
    pd.DataFrame(
        {"gene": ["RHO", "RPGR"], "log2FoldChange": [1.2, -0.7], "padj": [0.01, 0.04]}
    ).to_csv(p, index=False)

    db = ingest(p)
    assert db.kind == DE_RESULTS
    assert db.source.filename == "ST6_de.csv"
    assert db.source.n_bytes > 0
    assert len(db.source.sha256) == 64  # full sha256 hex digest
    assert isinstance(db.payload, pd.DataFrame)


def test_ingest_tsv_uses_tab_delimiter(tmp_path):
    p = tmp_path / "counts.tsv"
    pd.DataFrame(
        RNG.integers(0, 300, size=(20, 4)),
        index=[f"g{i}" for i in range(20)],
        columns=[f"s{j}" for j in range(4)],
    ).to_csv(p, sep="\t")
    db = ingest(p)
    assert db.kind == BULK_COUNTS
    assert db.payload.shape[1] >= 4  # parsed as columns, not one blob


def test_ingest_xlsx_first_sheet(tmp_path):
    pytest.importorskip("openpyxl")
    p = tmp_path / "supp.xlsx"
    pd.DataFrame(
        RNG.integers(0, 100, size=(15, 5)),
        index=[f"g{i}" for i in range(15)],
        columns=[f"c{j}" for j in range(5)],
    ).to_excel(p)
    db = ingest(p)
    assert db.kind == BULK_COUNTS


def test_ingest_xlsx_named_sheet(tmp_path):
    pytest.importorskip("openpyxl")
    p = tmp_path / "two_sheet.xlsx"
    with pd.ExcelWriter(p) as xw:
        pd.DataFrame({"note": ["readme"]}).to_excel(xw, sheet_name="info", index=False)
        pd.DataFrame(
            {"gene": ["A"], "avg_log2FC": [1.0], "p_val_adj": [0.001]}
        ).to_excel(xw, sheet_name="DE", index=False)
    db = ingest(p, sheet="DE")
    assert db.kind == DE_RESULTS
    assert db.source.sheet == "DE"


def test_ingest_h5ad_single_cell(tmp_path):
    ad = pytest.importorskip("anndata")
    pytest.importorskip("h5py")
    # pandas-3 indices materialize as nullable StringArray; opt in to writing them (env quirk,
    # write-side only — the ingest/read path under test is unaffected).
    ad.settings.allow_write_nullable_strings = True
    adata = ad.AnnData(RNG.poisson(1.0, size=(10, 5)).astype("float32"))
    p = tmp_path / "cells.h5ad"
    adata.write_h5ad(p)
    db = ingest(p)
    assert db.kind == SC_COUNTS


def test_ingest_unrecognized_raises(tmp_path):
    p = tmp_path / "mystery.bin"
    p.write_bytes(b"\x00\x01\x02")
    with pytest.raises(ValueError, match="no ingest loader"):
        ingest(p)
