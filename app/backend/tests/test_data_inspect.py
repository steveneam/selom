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
