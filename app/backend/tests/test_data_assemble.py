"""POST /data/assemble-scrna — the scRNA sibling of /data/combine (wire contract).

Drop a SET of per-sample 10x matrices whose design lives in the filenames → get back ONE assembled
.h5ad (bytes) + an ``X-Assemble-Summary`` header, the same shape /data/combine returns its merged CSV
(the FE then materializes it as a normal dataset). Asserts the summary AND that the returned h5ad
carries the filename-encoded obs.
"""

from __future__ import annotations

import gzip
import io
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _triplet_files(prefix, n_cells, n_genes):
    """Return the three (field, (filename, bytes, content_type)) multipart tuples for one synthetic
    per-sample 10x triplet, named the GEO ``<prefix>_{matrix,barcodes,features}.gz`` way."""
    scipy_io = pytest.importorskip("scipy.io")
    sp = pytest.importorskip("scipy.sparse")
    m = sp.csr_matrix(np.arange(1, n_genes * n_cells + 1).reshape(n_genes, n_cells).astype(float))
    mbuf = io.BytesIO()
    with gzip.GzipFile(fileobj=mbuf, mode="wb") as gz:
        scipy_io.mmwrite(gz, m)
    barcodes = gzip.compress(("\n".join(f"CELL{i}-1" for i in range(n_cells)) + "\n").encode())
    features = gzip.compress(
        ("\n".join(f"ENSG{i}\tGENE{i}\tGene Expression" for i in range(n_genes)) + "\n").encode())
    return [
        ("files", (f"{prefix}_matrix.mtx.gz", mbuf.getvalue(), "application/gzip")),
        ("files", (f"{prefix}_barcodes.tsv.gz", barcodes, "application/gzip")),
        ("files", (f"{prefix}_features.tsv.gz", features, "application/gzip")),
    ]


def test_assemble_scrna_endpoint_returns_h5ad_and_summary(tmp_path):
    pytest.importorskip("scanpy")
    ad = pytest.importorskip("anndata")
    files = _triplet_files("GSM100_LINEa-1", 2, 3) + _triplet_files("GSM200_LINEb-2", 4, 3)
    obs_map = {"GSM100_LINEa-1": {"line": "LINEa", "condition": "treated"},
               "GSM200_LINEb-2": {"line": "LINEb", "condition": "control"}}
    r = client.post("/data/assemble-scrna", files=files, data={"obs_map": json.dumps(obs_map)})
    assert r.status_code == 200, r.text

    summary = json.loads(r.headers["X-Assemble-Summary"])
    assert summary["n_files"] == 6 and summary["n_samples"] == 2 and summary["n_cells"] == 6
    assert set(summary["samples"]) == {"GSM100_LINEa-1", "GSM200_LINEb-2"}
    assert summary["per_sample_n"] == {"GSM100_LINEa-1": 2, "GSM200_LINEb-2": 4}
    assert "sample_id" in summary["obs_columns"] and "line" in summary["obs_columns"]

    # the returned bytes ARE a real assembled AnnData with the filename-encoded obs
    out = tmp_path / "assembled.h5ad"
    out.write_bytes(r.content)
    adata = ad.read_h5ad(out)
    assert adata.n_obs == 6
    assert dict(zip(adata.obs["sample_id"].astype(str), adata.obs["condition"].astype(str))) == {
        "GSM100_LINEa-1": "treated", "GSM200_LINEb-2": "control"}


def test_assemble_scrna_endpoint_filename_only(tmp_path):
    """No obs_map → the endpoint still assembles, sample_id derived from the filenames."""
    pytest.importorskip("scanpy")
    files = _triplet_files("GSM100_LINEa-1", 3, 3)
    r = client.post("/data/assemble-scrna", files=files)
    assert r.status_code == 200, r.text
    summary = json.loads(r.headers["X-Assemble-Summary"])
    assert summary["samples"] == ["GSM100_LINEa-1"] and summary["n_cells"] == 3


def test_assemble_scrna_endpoint_bad_obs_map_is_400():
    pytest.importorskip("scanpy")
    files = _triplet_files("GSM100_LINEa-1", 2, 3)
    r = client.post("/data/assemble-scrna", files=files, data={"obs_map": "not-json"})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "assemble_bad_obs_map"


def test_assemble_scrna_endpoint_incomplete_triplet_is_400():
    """A sample missing its features file is a clean 400 in the shared run-error envelope."""
    pytest.importorskip("scanpy")
    files = _triplet_files("GSM100_LINEa-1", 2, 3)[:2]  # matrix + barcodes only
    r = client.post("/data/assemble-scrna", files=files)
    assert r.status_code == 400
    body = r.json()["detail"]
    assert body["error"] == "assemble_failed" and body["category"] == "bad_input"
