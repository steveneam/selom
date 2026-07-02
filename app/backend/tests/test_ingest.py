"""P1 step 2 — the ingest registry: drop any supported file -> a classified DataBundle.

Round-trips real on-disk formats (csv/tsv/xlsx/h5ad) through ``ingest`` and asserts the
modality + provenance, mirroring how the staged datasets arrive ([[selom-real-datasets]]).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine import BULK_COUNTS, DE_RESULTS, SC_COUNTS, ingest, ingest_many

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


# --- messy-real-input robustness (WS2.4): encoding / delimiter sniffing + honest parse errors ------

def test_ingest_semicolon_csv_parses_into_columns(tmp_path):
    """A European semicolon-delimited .csv parses into columns, not one blob."""
    p = tmp_path / "eu.csv"
    p.write_bytes(b"gene;s0;s1;s2\n" + b"".join(
        f"g{i};{i};{i + 1};{i + 2}\n".encode() for i in range(15)))
    db = ingest(p)
    assert db.payload.shape[1] == 4   # sniffed ';' -> 4 columns, not a single blob
    assert db.kind == BULK_COUNTS


def test_ingest_latin1_encoding_loads(tmp_path):
    """A cp1252/latin-1 byte in the header (µ = 0xB5) must not crash the default UTF-8 read."""
    p = tmp_path / "dose.csv"
    p.write_bytes("gene,ctrl,\xb5M_dose\n".encode("cp1252") + b"".join(
        f"g{i},{i},{i + 1}\n".encode() for i in range(12)))
    db = ingest(p)                    # must not raise UnicodeDecodeError
    assert "gene" in [str(c) for c in db.payload.columns]


def test_ingest_utf8_bom_first_header_clean(tmp_path):
    """A UTF-8 BOM is stripped (utf-8-sig) so the first column name isn't mangled with ﻿."""
    p = tmp_path / "bom.csv"
    p.write_bytes(b"\xef\xbb\xbfgene,s0,s1\n" + b"".join(
        f"g{i},{i},{i + 1}\n".encode() for i in range(12)))
    db = ingest(p)
    assert list(db.payload.columns)[0] == "gene"


def test_ingest_empty_csv_raises(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_bytes(b"   \n")
    with pytest.raises(ValueError, match="empty"):
        ingest(p)


def test_ingest_ragged_csv_raises_valueerror(tmp_path):
    """Rows with more fields than the header are a genuine parse failure -> an honest ValueError
    (which the router turns into a 400), never a raw ParserError bubbling up as a 500."""
    p = tmp_path / "ragged.csv"
    p.write_bytes(b"a,b,c\n1,2,3\n4,5,6\n7,8,9,10,11\n")   # inconsistent row widths -> ParserError
    with pytest.raises(ValueError):
        ingest(p)


def test_ingest_corrupt_xlsx_raises_valueerror(tmp_path):
    """A file wearing .xlsx that isn't a real workbook fails with a clear ValueError, not a 500."""
    p = tmp_path / "broken.xlsx"
    p.write_bytes(b"definitely not a zip-based spreadsheet")
    with pytest.raises(ValueError):
        ingest(p)


# --- ingest_many (C6 multi-file combine) ------------------------------------------------

def _erg_csv(path, condition, sample_ids):
    """A tiny single-condition ERG waveform table (its own `condition` column + sample_ids)."""
    rows = []
    for sid in sample_ids:
        for t in range(3):
            rows.append({"sample_id": sid, "condition": condition, "intensity_group": "Group1",
                         "time_ms": float(t), "voltage_uv": float(t + len(sid)), "role": "representative"})
    pd.DataFrame(rows).to_csv(path, index=False)


def test_ingest_many_keeps_each_files_condition(tmp_path):
    """Each file's own `condition` column is kept (precedence 2) → a cohort grouping (C57 vs Rd10),
    not one-condition-per-file; condition_order follows file order; rows concatenate."""
    a = tmp_path / "c57.csv"
    b = tmp_path / "rd10.csv"
    _erg_csv(a, "C57", ["643_LE", "643_RE"])
    _erg_csv(b, "Rd10", ["247_LE", "247_RE", "254_LE"])
    db = ingest_many([a, b])
    df = db.payload
    assert set(df["condition"].unique()) == {"C57", "Rd10"}
    assert db.meta["conditions"] == ["C57", "Rd10"]  # first-seen = file order
    assert dict(zip(df["condition"], df["condition_order"]))["C57"] == 0
    assert df[df.condition == "Rd10"]["sample_id"].nunique() == 3
    assert "source_file" in df.columns


def test_ingest_many_explicit_label_overrides(tmp_path):
    a = tmp_path / "f1.csv"
    b = tmp_path / "f2.csv"
    _erg_csv(a, "C57", ["m1"])
    _erg_csv(b, "Rd10", ["m2"])
    db = ingest_many([a, b], labels=["Wild-type", ""])  # blank → falls through to the file's own
    conds = set(db.payload["condition"].unique())
    assert conds == {"Wild-type", "Rd10"}


def test_ingest_many_namespaces_colliding_sample_ids(tmp_path):
    """Same sample_id from two files → prefixed with the file stem so replicates stay distinct;
    a non-colliding id is left clean."""
    a = tmp_path / "day1.csv"
    b = tmp_path / "day2.csv"
    _erg_csv(a, "Rd10", ["OD", "uniqueA"])
    _erg_csv(b, "Rd10", ["OD", "uniqueB"])
    db = ingest_many([a, b])
    ids = set(db.payload["sample_id"].unique())
    assert "day1::OD" in ids and "day2::OD" in ids  # collision namespaced
    assert "uniqueA" in ids and "uniqueB" in ids     # singletons untouched


def test_ingest_many_filename_stem_when_no_condition(tmp_path):
    a = tmp_path / "Control.csv"
    pd.DataFrame({"sample_id": ["s1"], "intensity_group": ["Group1"], "time_ms": [0.0],
                  "voltage_uv": [1.0]}).to_csv(a, index=False)
    db = ingest_many([a])
    assert db.payload["condition"].iloc[0] == "Control"  # stem (no condition column)


def test_ingest_many_empty_raises():
    with pytest.raises(ValueError, match="no inputs"):
        ingest_many([])
