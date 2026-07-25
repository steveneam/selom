"""engine.assemble.assemble_scrna — multi-sample scRNA assembly (the scRNA sibling of ingest_many).

A GEO scRNA deposit arrives as a SET of per-sample 10x matrices with NO per-cell design in obs —
the design lives in the filenames (``GSM…_<sample>_matrix.mtx.gz``). These round-trip synthetic
per-sample triplets (and per-sample .h5ad) through ``assemble_scrna`` and assert the concatenation +
the filename-encoded obs (``sample_id`` / ``line`` / ``condition``), mirroring how the real Hani
GSE201356 RAW triplets arrive.
"""

from __future__ import annotations

import gzip
import importlib

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


# --- A14: the gene axis is honest — no fabricated zeros, no silent drop -----------------------
# Before this, ``ad.concat(join="outer", fill_value=0)`` wrote a hard 0 for every gene a sample's
# features.tsv never carried, and nothing measured or reported the overlap. Those 0s are
# indistinguishable from measured zero counts downstream, and with obs['sample'] mirrored to the
# batch key a gene present in only one reference reads as a perfect sample-specific marker. The old
# tests built both samples with IDENTICAL gene sets, so the disjoint case never ran — these run it.

def _write_10x_triplet_named(dirpath, prefix, n_cells, gene_names, *, gz=True):
    """Like :func:`_write_10x_triplet` but with an explicit gene list, so two samples can be written
    against DIFFERENT references (the real hazard: a mixed deposit, or `GRCh38_`-prefixed symbols)."""
    scipy_io = pytest.importorskip("scipy.io")
    sp = pytest.importorskip("scipy.sparse")
    n_genes = len(gene_names)
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
        f.write("\n".join(f"ENS_{g}\t{g}\tGene Expression" for g in gene_names) + "\n")
    return [mpath, bpath, fpath]


def _disjoint_pair(tmp_path):
    """Two samples whose references overlap on 2 of 4 genes (shared_fraction 0.5)."""
    a = _write_10x_triplet_named(tmp_path, "GSM100_A", 2, ["SHARED1", "SHARED2", "ONLY_A"])
    b = _write_10x_triplet_named(tmp_path, "GSM200_B", 2, ["SHARED1", "SHARED2", "ONLY_B"])
    return a + b


def test_default_join_is_inner_so_no_count_is_fabricated(tmp_path):
    _require_scrna_deps()
    adata = assemble_scrna(_disjoint_pair(tmp_path))
    # only the genes measured in EVERY sample survive — every value in the matrix is a real count
    assert sorted(str(v) for v in adata.var_names) == ["SHARED1", "SHARED2"]
    assert adata.n_vars == 2 and adata.n_obs == 4


def test_overlap_verdict_is_measured_and_reported(tmp_path):
    """The verdict travels on uns and surfaces through summarize() — the endpoint header carries it."""
    _require_scrna_deps()
    from engine.assemble import summarize

    adata = assemble_scrna(_disjoint_pair(tmp_path))
    v = adata.uns["selom_gene_overlap"]
    assert (v["n_genes_union"], v["n_genes_shared"], v["shared_fraction"]) == (4, 2, 0.5)
    assert v["join"] == "inner" and v["dropped_genes"] == 2 and v["zero_filled_genes"] == 0
    assert v["level"] == "warn" and "DIFFERENT references" in v["fix"]
    assert v["per_sample_n_genes"] == {"GSM100_A": 3, "GSM200_B": 3}

    s = summarize(adata)
    assert s["gene_overlap"] == v
    # the flat keys the finding names, alongside the post-join n_genes
    assert (s["n_genes"], s["n_genes_union"], s["n_genes_shared"]) == (2, 4, 2)
    assert s["per_sample_n_genes"] == {"GSM100_A": 3, "GSM200_B": 3}


def test_outer_join_is_opt_in_and_discloses_the_zero_fill(tmp_path):
    """`outer` still exists — it just cannot be quiet about what it invented."""
    _require_scrna_deps()
    adata = assemble_scrna(_disjoint_pair(tmp_path), join="outer")
    assert adata.n_vars == 4  # the union
    v = adata.uns["selom_gene_overlap"]
    assert v["join"] == "outer" and v["zero_filled_genes"] == 2 and v["dropped_genes"] == 0
    assert v["level"] == "warn"
    assert "ZERO-FILLED" in v["message"] and "NOT measured counts" in v["message"]


def test_matching_references_report_ok_and_change_nothing(tmp_path):
    """The common case stays quiet: same reference → nothing dropped, nothing filled, level 'ok'."""
    _require_scrna_deps()
    a = _write_10x_triplet(tmp_path, "GSM100_LINEa-1", n_cells=2, n_genes=3)
    b = _write_10x_triplet(tmp_path, "GSM200_LINEb-2", n_cells=4, n_genes=3)
    adata = assemble_scrna(a + b)
    assert adata.n_obs == 6 and adata.n_vars == 3  # identical to the pre-A14 outer-join result
    v = adata.uns["selom_gene_overlap"]
    assert v["level"] == "ok" and v["dropped_genes"] == 0 and v["zero_filled_genes"] == 0
    assert v["shared_fraction"] == 1.0


def test_a_mild_reference_difference_is_info_not_warn(tmp_path):
    """Above the 0.9 threshold the samples plausibly share a reference — report it, don't alarm."""
    _require_scrna_deps()
    common = [f"G{i}" for i in range(19)]
    a = _write_10x_triplet_named(tmp_path, "GSM100_A", 2, [*common, "ONLY_A"])
    b = _write_10x_triplet_named(tmp_path, "GSM200_B", 2, common)
    v = assemble_scrna(a + b).uns["selom_gene_overlap"]
    assert v["n_genes_union"] == 20 and v["n_genes_shared"] == 19
    assert v["level"] == "info" and "DIFFERENT references" not in v["fix"]


def test_unknown_join_is_refused(tmp_path):
    _require_scrna_deps()
    a = _write_10x_triplet(tmp_path, "GSM100_A", 2, 3)
    with pytest.raises(ValueError, match="join must be one of"):
        assemble_scrna(a, join="left")


def test_the_verdict_survives_the_h5ad_round_trip(tmp_path):
    """The endpoint returns .h5ad BYTES; a verdict that doesn't survive the write is not reachable."""
    ad = pytest.importorskip("anndata")
    _require_scrna_deps()
    from engine.assemble import to_h5ad_bytes

    out = tmp_path / "assembled.h5ad"
    out.write_bytes(to_h5ad_bytes(assemble_scrna(_disjoint_pair(tmp_path))))
    v = ad.read_h5ad(out).uns["selom_gene_overlap"]
    assert (int(v["n_genes_union"]), int(v["n_genes_shared"])) == (4, 2)
    assert str(v["level"]) == "warn"


# --- A21: ONE format-decision point, not two -------------------------------------------------
# engine/assemble.py used to re-declare the 10x detector (byte-identical to engine.ingest._is_10x)
# and re-implement the 10x/h5ad reads. Two decision points that agreed only by coincidence: the day
# ingest gained a format or changed 10x detection, /data/assemble-scrna would start refusing inputs
# the rest of the engine accepts, with the hard ValueError('unrecognized file(s)').

def test_assemble_shares_the_single_10x_detector():
    # engine/__init__.py re-exports the ingest() FUNCTION under the name `engine.ingest`, so both
    # `from engine import ingest` AND `import engine.ingest as x` bind the function — the module has
    # to come from sys.modules.
    from engine import assemble

    ingest_mod = importlib.import_module("engine.ingest")

    assert assemble._is_10x_dir is ingest_mod.is_10x_dir


def test_assemble_reads_through_the_ingest_loader_registry():
    """No second reader: assemble must call the registry, not scanpy/anndata directly."""
    import ast
    import inspect

    from engine import assemble

    ingest_mod = importlib.import_module("engine.ingest")

    assert assemble._load_unit is ingest_mod.load_unit
    # No direct format READ anywhere in the module (AST, so a docstring mentioning the name is not a
    # false positive). assemble still WRITES h5ad — that is a different call and stays.
    tree = ast.parse(inspect.getsource(assemble))
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not called & {"read_10x_mtx", "read_h5ad"}, sorted(called & {"read_10x_mtx", "read_h5ad"})


def test_a_new_ingest_format_reaches_assemble(tmp_path):
    """The regression the fork made possible, run forwards: a directory the registry recognizes as
    10x is loadable by assemble WITHOUT assemble knowing anything new about the format."""
    _require_scrna_deps()
    ingest_mod = importlib.import_module("engine.ingest")

    d = tmp_path / "sampleDir"
    d.mkdir()
    _write_10x_triplet_named(d, "", 2, ["G1", "G2"])
    # the staged names are what the registry recognizes
    for f in d.iterdir():
        f.rename(d / f.name.lstrip("_"))
    assert ingest_mod.is_10x_dir(d)
    adata = assemble_scrna([d])
    assert adata.n_obs == 2 and adata.n_vars == 2
    assert set(adata.obs["sample_id"].astype(str)) == {"sampleDir"}
