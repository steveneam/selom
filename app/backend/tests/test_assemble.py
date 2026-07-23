"""engine.assemble.assemble_scrna — multi-sample scRNA assembly (the scRNA sibling of ingest_many).

A GEO scRNA deposit arrives as a SET of per-sample 10x matrices with NO per-cell design in obs —
the design lives in the filenames (``GSM…_<sample>_matrix.mtx.gz``). These round-trip synthetic
per-sample triplets (and per-sample .h5ad) through ``assemble_scrna`` and assert the concatenation +
the filename-encoded obs (``sample_id`` / ``line`` / ``condition``), mirroring how the real Hani
GSE201356 RAW triplets arrive.
"""

from __future__ import annotations

import gzip

import numpy as np
import pytest

from engine import assemble_scrna


def _write_10x_triplet(dirpath, prefix, n_cells, n_genes, *, gz=True):
    """Write a synthetic 10x Cell-Ranger triplet named ``<prefix>_{matrix,barcodes,features}`` (the
    GEO per-sample shape) and return the three paths. Matrix is genes x cells (MatrixMarket), which
    ``scanpy.read_10x_mtx`` transposes to cells x genes."""
    scipy_io = pytest.importorskip("scipy.io")
    sp = pytest.importorskip("scipy.sparse")
    ext = ".gz" if gz else ""
    m = sp.csr_matrix(np.arange(1, n_genes * n_cells + 1).reshape(n_genes, n_cells).astype(float))
    mpath = dirpath / f"{prefix}_matrix.mtx{ext}"
    bpath = dirpath / f"{prefix}_barcodes.tsv{ext}"
    fpath = dirpath / f"{prefix}_features.tsv{ext}"
    with (gzip.open(mpath, "wb") if gz else open(mpath, "wb")) as f:
        scipy_io.mmwrite(f, m)
    with (gzip.open(bpath, "wt") if gz else open(bpath, "w")) as f:
        f.write("\n".join(f"CELL{i}-1" for i in range(n_cells)) + "\n")
    with (gzip.open(fpath, "wt") if gz else open(fpath, "w")) as f:
        f.write("\n".join(f"ENSG{i}\tGENE{i}\tGene Expression" for i in range(n_genes)) + "\n")
    return [mpath, bpath, fpath]


def _require_scrna_deps():
    pytest.importorskip("scanpy")
    pytest.importorskip("anndata")


def test_assemble_two_samples_derives_obs_from_filenames(tmp_path):
    """Two per-sample triplets → ONE AnnData; sample_id + line/condition come from the filenames via
    obs_map, cells concatenate, genes union, barcodes stay distinct across samples."""
    _require_scrna_deps()
    a = _write_10x_triplet(tmp_path, "GSM100_LINEa-1", n_cells=2, n_genes=3)
    b = _write_10x_triplet(tmp_path, "GSM200_LINEb-2", n_cells=4, n_genes=3)
    obs_map = {
        "GSM100_LINEa-1": {"line": "LINEa", "condition": "treated"},
        "GSM200_LINEb-2": {"line": "LINEb", "condition": "control"},
    }
    adata = assemble_scrna(a + b, obs_map=obs_map)

    assert adata.n_obs == 6 and adata.n_vars == 3
    assert set(adata.obs["sample_id"].astype(str)) == {"GSM100_LINEa-1", "GSM200_LINEb-2"}
    # the design materialized per cell, keyed off the filename
    by_sid = dict(zip(adata.obs["sample_id"].astype(str), adata.obs["line"].astype(str)))
    assert by_sid == {"GSM100_LINEa-1": "LINEa", "GSM200_LINEb-2": "LINEb"}
    assert (adata.obs["sample_id"].astype(str) == "GSM100_LINEa-1").sum() == 2
    assert (adata.obs["sample_id"].astype(str) == "GSM200_LINEb-2").sum() == 4
    assert adata.obs_names.is_unique
    # barcodes namespaced by sample so origin is legible and collisions can't merge cells
    assert all(n.startswith(("GSM100_LINEa-1_", "GSM200_LINEb-2_")) for n in adata.obs_names)


def test_assemble_mirrors_sample_id_into_batch_key(tmp_path):
    """`sample` is mirrored from sample_id (when the design didn't set it) so the batch-key-reading
    scRNA skills (integration / QC / mixing, which look up 'sample' first) find a batch column."""
    _require_scrna_deps()
    a = _write_10x_triplet(tmp_path, "GSM100_LINEa-1", 2, 3)
    b = _write_10x_triplet(tmp_path, "GSM200_LINEb-2", 2, 3)
    adata = assemble_scrna(a + b)
    assert "sample" in adata.obs.columns
    assert list(adata.obs["sample"].astype(str)) == list(adata.obs["sample_id"].astype(str))
    assert adata.obs["sample"].nunique() == 2


def test_assemble_sample_id_from_filename_without_obs_map(tmp_path):
    """No obs_map → sample_id is the filename prefix (design-free assembly still works); no phantom
    design columns are invented."""
    _require_scrna_deps()
    a = _write_10x_triplet(tmp_path, "GSM100_LINEa-1", 3, 3)
    adata = assemble_scrna(a)
    assert set(adata.obs["sample_id"].astype(str)) == {"GSM100_LINEa-1"}
    assert "line" not in adata.obs.columns and "condition" not in adata.obs.columns


def test_assemble_obs_map_can_refine_sample_id(tmp_path):
    """An obs_map entry may override sample_id to a clean label; the barcode namespace follows it."""
    _require_scrna_deps()
    a = _write_10x_triplet(tmp_path, "GSM100_2niPE2-ANAI-3", 2, 3)
    adata = assemble_scrna(a, obs_map={"GSM100_2niPE2-ANAI-3": {"sample_id": "2niPE2-3", "line": "2niPE2"}})
    assert set(adata.obs["sample_id"].astype(str)) == {"2niPE2-3"}
    assert all(n.startswith("2niPE2-3_") for n in adata.obs_names)


def test_assemble_obs_map_substring_match(tmp_path):
    """obs_map can be keyed by a distinctive substring (the biological name) rather than the full
    GSM-prefixed filename — the longest matching key wins."""
    _require_scrna_deps()
    a = _write_10x_triplet(tmp_path, "GSM100_LINEa-1", 2, 3)
    adata = assemble_scrna(a, obs_map={"LINEa-1": {"line": "LINEa"}})
    assert set(adata.obs["line"].astype(str)) == {"LINEa"}


def test_assemble_per_sample_h5ad(tmp_path):
    """Per-sample .h5ad inputs assemble the same way — one AnnData, sample_id from the file stem."""
    ad = pytest.importorskip("anndata")
    from engine.assemble import to_h5ad_bytes  # serialize via the module's writable-dtype path

    p1, p2 = tmp_path / "sampleA.h5ad", tmp_path / "sampleB.h5ad"
    p1.write_bytes(to_h5ad_bytes(ad.AnnData(np.arange(6).reshape(2, 3).astype("float32"))))
    p2.write_bytes(to_h5ad_bytes(ad.AnnData(np.arange(9).reshape(3, 3).astype("float32"))))
    adata = assemble_scrna([p1, p2], obs_map={"sampleA": {"line": "X"}, "sampleB": {"line": "Y"}})
    assert adata.n_obs == 5
    assert set(adata.obs["sample_id"].astype(str)) == {"sampleA", "sampleB"}
    assert dict(zip(adata.obs["sample_id"].astype(str), adata.obs["line"].astype(str))) == {
        "sampleA": "X", "sampleB": "Y"}


def test_assemble_empty_raises():
    with pytest.raises(ValueError, match="no inputs"):
        assemble_scrna([])


def test_assemble_incomplete_triplet_raises(tmp_path):
    """A sample missing a triplet member is a clear error, never a silently-dropped sample."""
    _require_scrna_deps()
    matrix, barcodes, _features = _write_10x_triplet(tmp_path, "GSM100_LINEa-1", 2, 3)
    with pytest.raises(ValueError, match="missing.*features"):
        assemble_scrna([matrix, barcodes])


def test_assemble_unrecognized_file_raises(tmp_path):
    """An unrecognized file is named and refused (a dropped member would corrupt the design)."""
    _require_scrna_deps()
    stray = tmp_path / "notes.txt"
    stray.write_text("hello")
    with pytest.raises(ValueError, match="unrecognized"):
        assemble_scrna([stray])
