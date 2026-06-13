"""ShinyCell bundle -> AnnData (.h5ad) converter (real-world data prep, dev-time tool).

Steven's real RPGRIP1 retinal-organoid scRNA-seq arrived as ShinyCell exports (an R/Shiny
viewer bundle per sample), not as ingestable AnnData. This reconstructs a single merged
`.h5ad` Selom can run its skills on. Off the hot path — a one-off prep script, not part of
the FastAPI runtime; reads `.rds` with the MIT-licensed pure-Python `rdata` (no R, no AGPL).

Per sample it reads:
  * sc1gexpr.h5  -> HDF5 `grp/data` = (cells x genes), log-normalized float32 -> sparse X
  * sc1gene.rds  -> named int vector (names = gene symbols) -> ordered var_names
  * sc1meta.rds  -> per-cell metadata (clusters, celltypes, QC, t-SNE coords) -> obs

It adds clean `sample` / `genotype` / `seq_batch` obs, keeps the ShinyCell t-SNE in obsm,
concatenates all samples, and writes the merged AnnData.

Run (rdata is dev-only, pulled transiently so it never enters the runtime deps):
    uv run --with rdata --directory app/backend python scripts/shinycell_to_h5ad.py

Defaults read D:/selom-data/rpgrip1/raw and write D:/selom-data/rpgrip1/processed
(kept outside the repo so large data survives even if the source share goes away).
"""

from __future__ import annotations

import argparse
import pathlib
import re

import anndata
import h5py
import numpy as np
import pandas as pd
import rdata
from scipy import sparse

# RPGRIP1 cohort: sample folder (sans "shiny_batchN_") -> genotype. Explicit because the
# replicate suffix is inconsistent (WT uses digits, C3/PT use letters, C3's "3" is part of
# the genotype). Printed at the end so a wrong call is easy to spot and fix.
_GENOTYPE = {
    "WT1": "WT", "WT2": "WT", "WT3": "WT",
    "C3a": "C3", "C3b": "C3", "C3c": "C3",
    "PTa": "PT", "PTb": "PT",
    "FS": "FS",
}


def _read_genes(path: pathlib.Path) -> list[str]:
    """sc1gene.rds -> gene symbols in column order. rdata returns a DataArray whose
    coordinate holds the names (symbols) and whose values are the 1-based column index."""
    da = rdata.read_rds(str(path))
    symbols = [str(s) for s in da.coords[da.dims[0]].values]
    positions = np.asarray(da.values, dtype=int)
    genes: list[str | None] = [None] * len(symbols)
    for sym, pos in zip(symbols, positions):
        genes[pos - 1] = sym
    if any(g is None for g in genes):  # fall back to coordinate order if positions are odd
        genes = symbols
    return [str(g) for g in genes]


def _read_meta(path: pathlib.Path) -> pd.DataFrame:
    meta = rdata.read_rds(str(path))
    if not isinstance(meta, pd.DataFrame):
        raise TypeError(f"{path.name}: expected a data.frame, got {type(meta).__name__}")
    meta = meta.reset_index(drop=True)
    meta.columns = [str(c) for c in meta.columns]
    return meta


def _read_expr(path: pathlib.Path) -> sparse.csr_matrix:
    """sc1gexpr.h5 `grp/data` (cells x genes, dense log-norm float32) -> CSR sparse."""
    with h5py.File(path, "r") as h:
        dense = h["grp"]["data"][:]
    return sparse.csr_matrix(dense, dtype="float32")


def _sample_name(folder: str) -> str:
    # "shiny_batch1_WT1" -> "WT1"
    return re.sub(r"^shiny_batch\d+_", "", folder)


def _seq_batch(folder: str) -> str:
    m = re.search(r"batch(\d+)", folder)
    return f"batch{m.group(1)}" if m else "unknown"


def _build_sample(sample_dir: pathlib.Path) -> anndata.AnnData:
    folder = sample_dir.name
    sample = _sample_name(folder)
    genes = _read_genes(sample_dir / "sc1gene.rds")
    meta = _read_meta(sample_dir / "sc1meta.rds")
    X = _read_expr(sample_dir / "sc1gexpr.h5")

    if X.shape[0] != len(meta):
        raise ValueError(f"{folder}: {X.shape[0]} cells in h5 != {len(meta)} rows in meta")
    if X.shape[1] != len(genes):
        raise ValueError(f"{folder}: {X.shape[1]} genes in h5 != {len(genes)} gene symbols")

    var = pd.DataFrame(index=pd.Index(genes, name="gene"))
    ad = anndata.AnnData(X=X, obs=meta.copy(), var=var)

    # Globally-unique cell ids (sampleID already carries the sample prefix).
    if "sampleID" in meta.columns:
        ad.obs_names = meta["sampleID"].astype(str).to_numpy()
    else:
        ad.obs_names = [f"{sample}_{i}" for i in range(ad.n_obs)]

    ad.obs["sample"] = sample
    ad.obs["genotype"] = _GENOTYPE.get(sample, sample)
    ad.obs["seq_batch"] = _seq_batch(folder)

    for x, y, key in (
        ("fastTSNE1_qc_all", "fastTSNE2_qc_all", "X_tsne_all"),
        ("fastTSNEqcsample_1", "fastTSNEqcsample_2", "X_tsne_sample"),
    ):
        if x in meta.columns and y in meta.columns:
            ad.obsm[key] = meta[[x, y]].to_numpy(dtype="float32")

    return ad


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert ShinyCell bundles to a merged .h5ad")
    ap.add_argument("--raw", default="D:/selom-data/rpgrip1/raw")
    ap.add_argument("--out", default="D:/selom-data/rpgrip1/processed/rpgrip1_merged.h5ad")
    args = ap.parse_args()

    raw = pathlib.Path(args.raw)
    sample_dirs = sorted(
        d for d in raw.rglob("shiny_batch*")
        if d.is_dir() and (d / "sc1gexpr.h5").exists() and "__MACOSX" not in d.parts
    )
    if not sample_dirs:
        raise SystemExit(f"no ShinyCell sample dirs under {raw}")

    print(f"Found {len(sample_dirs)} samples:")
    adatas = []
    for d in sample_dirs:
        ad = _build_sample(d)
        print(f"  {ad.obs['sample'].iloc[0]:>4}  {ad.n_obs:>6} cells x {ad.n_vars} genes  "
              f"genotype={ad.obs['genotype'].iloc[0]}  batch={ad.obs['seq_batch'].iloc[0]}")
        adatas.append(ad)

    merged = anndata.concat(adatas, join="inner", merge="same")
    merged.obs_names_make_unique()

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    anndata.settings.allow_write_nullable_strings = True
    merged.write_h5ad(out)

    nnz = merged.X.nnz if sparse.issparse(merged.X) else int(np.count_nonzero(merged.X))
    density = nnz / (merged.n_obs * merged.n_vars)
    xmax = float(merged.X.max())
    print("\nMERGED:")
    print(f"  {merged.n_obs} cells x {merged.n_vars} genes  density={density:.1%}  X.max={xmax:.2f} "
          f"({'log-normalized' if xmax < 20 else 'raw-counts?'})")
    print("  genotype:", merged.obs["genotype"].value_counts().to_dict())
    print("  sample:  ", merged.obs["sample"].value_counts().to_dict())
    if "celltypes" in merged.obs.columns:
        print(f"  celltypes: {merged.obs['celltypes'].nunique()} unique")
    print(f"  wrote -> {out}  ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
