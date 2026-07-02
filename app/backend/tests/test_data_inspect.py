"""POST /data/inspect — the engine-spine front door (P1, step 4).

Wire contract for Product A's entry: drop a data file -> its modality (Kind) + an
"is-my-data-clean?" QC report. Library-only (no analysis runs), so no engine stub needed.
"""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_inspect_de_results_csv():
    r = client.post(
        "/data/inspect",
        files={"matrix": ("ST6.csv", b"gene,log2FoldChange,padj\nRHO,1.2,0.01\nRPGR,-0.7,0.04\n", "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "de_results"
    assert body["filename"] == "ST6.csv"
    assert body["source"]["filename"] == "ST6.csv"           # honest name, not the temp file
    assert len(body["source"]["sha256"]) == 64
    assert body["qc"]["ran"] is True


def test_inspect_clean_bulk_counts_ok():
    csv = b"gene,s0,s1,s2,s3\n" + b"".join(
        f"g{i},{i},{i+1},{i+2},{i+3}\n".encode() for i in range(20)
    )
    r = client.post("/data/inspect", files={"matrix": ("counts.csv", csv, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "bulk_counts"
    assert body["qc"]["ok"] is True
    assert body["qc"]["blocked"] is False
    # P3 guidance rides along: a registry-validated pipeline for this modality.
    assert body["routing"]["confident"] is True
    assert "deg" in [s["skill_id"] for s in body["routing"]["steps"]]
    # Slice 2 (product-agnostic): own data also gets the data-fit confidence band.
    assert body["data_fit"]["confidence"] == "confident" and body["data_fit"]["quality"] == 100
    assert any(f["skill_id"] == "deg" and f["confidence"] == "confident"
               for f in body["data_fit"]["fits"])
    # Slice 2 (data-aware routing): the table shape rides along so the FE can forward it to
    # /ai/propose as the data context (data_columns / data_n_numeric_cols).
    assert body["data_fit"]["columns"] == ["gene", "s0", "s1", "s2", "s3"]
    assert body["data_fit"]["n_numeric_cols"] == 4   # s0..s3 (gene is the label column)


def test_inspect_bulk_carries_dynamic_cleaning_plan():
    csv = b"gene,s0,s1,s2,s3\n" + b"".join(
        f"g{i},{i},{i+1},{i+2},{i+3}\n".encode() for i in range(20)
    )
    r = client.post("/data/inspect", files={"matrix": ("counts.csv", csv, "text/csv")})
    body = r.json()
    plan = body["cleaning_plan"]
    assert plan["applies"] is True                      # a count matrix gets real cleaning
    assert plan["obs_label"] == "samples" and plan["var_label"] == "genes"
    assert any(s["id"] == "drop_low" for s in plan["steps"])
    assert body["profile"]["code"] == "bulk_counts"


def test_inspect_erg_table_no_gene_cleaning():
    # The headline fix: a long-format ERG metrics table must NOT be force-fed gene-subset cleaning.
    csv = b"condition,intensity_log_cd_s_m2,b_wave_uv,a_wave_uv\nControl,1.0,200,80\nControl,-0.8,150,60\n"
    r = client.post("/data/inspect", files={"matrix": ("erg_metrics_long.csv", csv, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["code"] == "erg"            # high-precision column signature
    assert body["cleaning_plan"]["applies"] is False   # used as-is, no gene cleaning
    assert body["cleaning_plan"]["steps"] == []
    # ERG-aware routing: the electrophysiology figure skills, not the generic table options.
    assert "erg_intensity_response" in [s["skill_id"] for s in body["routing"]["steps"]]


def test_combine_merges_erg_files_into_one_multi_condition_table():
    # C6: drop several single-condition ERG files -> one combined CSV (the FE makes it a dataset).
    import json as _json

    head = b"sample_id,condition,intensity_group,time_ms,voltage_uv,role\n"
    c57 = head + b"".join(f"643_{e},C57,Group1,{t}.0,{t+1}.0,representative\n".encode()
                          for e in ("LE", "RE") for t in range(3))
    rd10 = head + b"".join(f"247_{e},Rd10,Group1,{t}.0,{t}.0,representative\n".encode()
                           for e in ("LE", "RE") for t in range(3))
    r = client.post("/data/combine", files=[
        ("files", ("c57.csv", c57, "text/csv")),
        ("files", ("rd10.csv", rd10, "text/csv")),
    ])
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    summary = _json.loads(r.headers["X-Combine-Summary"])
    assert summary["n_files"] == 2
    assert summary["conditions"] == ["C57", "Rd10"]
    assert summary["per_condition_n"] == {"C57": 2, "Rd10": 2}  # eyes per condition
    # the merged CSV carries both conditions + a condition_order column the grid uses
    text = r.content.decode()
    assert "C57" in text and "Rd10" in text and "condition_order" in text


def test_combine_requires_loadable_inputs():
    r = client.post("/data/combine", files=[
        ("files", ("mystery.bin", b"\x00\x01\x02", "application/octet-stream")),
    ])
    assert r.status_code == 400


def test_inspect_profile_override_to_erg():
    csv = b"a,b,c\n1,2,3\n4,5,6\n"
    r = client.post("/data/inspect?profile=erg", files={"matrix": ("x.csv", csv, "text/csv")})
    body = r.json()
    assert body["profile"]["code"] == "erg" and body["profile"]["overridden"] is True
    assert body["cleaning_plan"]["applies"] is False


def test_inspect_kind_override_wins_in_profile_over_content_signal():
    # A Kind override (hint) is the scientist's explicit choice and must win in the *profile*, not
    # just force the modality — even when a positive content signal (ERG a-/b-wave columns) would
    # otherwise out-rank it. Mirrors the FE override path (engine Kinds ride `hint`, "erg" rides
    # `profile`); without this the label would stay "ERG" after the user picked single-cell.
    csv = b"condition,intensity_log_cd_s_m2,b_wave_uv,a_wave_uv\nControl,1.0,200,80\nControl,-0.8,150,60\n"
    r = client.post("/data/inspect?hint=sc_counts", files={"matrix": ("erg_named.csv", csv, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["code"] == "sc_counts" and body["profile"]["overridden"] is True


def test_inspect_hint_forces_kind_and_qc_blocks_non_integer_counts():
    # A normalized (fractional) matrix declared as counts -> QC blocks it with a fix hint.
    csv = b"gene,s0,s1\n" + b"".join(f"g{i},{i+0.5},{i+1.5}\n".encode() for i in range(10))
    r = client.post(
        "/data/inspect?hint=bulk_counts",
        files={"matrix": ("norm.csv", csv, "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "bulk_counts"
    assert body["qc"]["blocked"] is True
    assert any(f["code"] == "non_integer_counts" for f in body["qc"]["flags"])


def test_inspect_invalid_hint_400():
    r = client.post(
        "/data/inspect?hint=transcriptomics",
        files={"matrix": ("x.csv", b"a,b\n1,2\n", "text/csv")},
    )
    assert r.status_code == 400


def test_inspect_unrecognized_type_400():
    r = client.post(
        "/data/inspect",
        files={"matrix": ("mystery.bin", b"\x00\x01\x02", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "no ingest loader" in r.json()["detail"]["message"]  # WS2.6 taxonomy envelope


# --- messy-real-input robustness (WS2.4): a stranger's odd/broken file never 500s -----------------

def test_inspect_semicolon_csv_parses_into_columns():
    csv = b"gene;s0;s1;s2;s3\n" + b"".join(
        f"g{i};{i};{i + 1};{i + 2};{i + 3}\n".encode() for i in range(20))
    r = client.post("/data/inspect", files={"matrix": ("counts_eu.csv", csv, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "bulk_counts"            # sniffed ';' -> real columns, not one blob
    assert body["data_fit"]["n_numeric_cols"] == 4


def test_inspect_latin1_encoding_no_500():
    # A cp1252 byte (µ = 0xB5) in the header must not crash the UTF-8 default read.
    csv = "gene,ctrl,\xb5M_dose\n".encode("cp1252") + b"".join(
        f"g{i},{i},{i + 1}\n".encode() for i in range(15))
    r = client.post("/data/inspect", files={"matrix": ("dose.csv", csv, "text/csv")})
    assert r.status_code == 200


def test_inspect_wide_matrix_flags_maybe_transposed():
    # 3 rows x 20 gene columns declared as counts -> a wrong-orientation hint, not a crash.
    csv = b"sample," + b",".join(f"g{j}".encode() for j in range(20)) + b"\n"
    csv += b"".join(
        (f"s{i}," + ",".join(str((i + j) % 50) for j in range(20)) + "\n").encode()
        for i in range(3))
    r = client.post("/data/inspect?hint=bulk_counts", files={"matrix": ("wide.csv", csv, "text/csv")})
    assert r.status_code == 200
    body = r.json()
    assert any(f["code"] == "maybe_transposed" for f in body["qc"]["flags"])


def test_inspect_ragged_csv_400_not_500():
    csv = b"a,b,c\n1,2,3\n4,5,6\n7,8,9,10,11\n"   # inconsistent row widths -> ParserError
    r = client.post("/data/inspect", files={"matrix": ("ragged.csv", csv, "text/csv")})
    assert r.status_code == 400


def test_inspect_corrupt_xlsx_400_not_500():
    r = client.post(
        "/data/inspect",
        files={"matrix": ("broken.xlsx", b"definitely not a real workbook",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert r.status_code == 400


def test_inspect_empty_csv_400():
    r = client.post("/data/inspect", files={"matrix": ("empty.csv", b"   \n", "text/csv")})
    assert r.status_code == 400
