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


def test_inspect_profile_override_to_erg():
    csv = b"a,b,c\n1,2,3\n4,5,6\n"
    r = client.post("/data/inspect?profile=erg", files={"matrix": ("x.csv", csv, "text/csv")})
    body = r.json()
    assert body["profile"]["code"] == "erg" and body["profile"]["overridden"] is True
    assert body["cleaning_plan"]["applies"] is False


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
    assert "no ingest loader" in r.json()["detail"]
