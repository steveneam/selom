"""DEV-only: stage a stage-spanning subset of the Dorgau GSE234963 scRNA for the live Fig-1 drive.

The deposited per-sample matrices are genes x cells CSVs (gene names in column 0, cell barcodes
as the header) plus a ``_md.csv.gz`` carrying per-cell ``percent.mt`` and the authors' DoubletFinder
calls (``DF.classifications``). This builds one concatenated AnnData (cells x genes) over a handful
of developmental stages, tagged with ``sample`` (the batch key for Melody) + ``stage`` + the authors'
QC metadata, subsampled per sample for a tractable live drive.

Not shipped runtime — a reproducible staging recipe (like ``stage_panel_assets.py``). Run once::

    python -m scripts.stage_dorgau_subset            # -> D:/selom-data/dorgau/processed/dorgau_subset.h5ad
"""

from __future__ import annotations

import gzip
import io
import pathlib
import tarfile

DATA = pathlib.Path("D:/selom-data/dorgau")
TAR = DATA / "GSE234963_RAW.tar"
OUT = DATA / "processed" / "dorgau_subset.h5ad"
CELLS_PER_SAMPLE = 1500  # cap per sample for a tractable Melody/UMAP drive

# A stage-spanning subset (GSM member, sample id, PCW stage, tissue) — 7.5 -> 21 PCW, Eye + Retina,
# a real multi-batch structure for the Melody integration dogfood.
SUBSET = [
    ("GSM7486878_15046_Eye", "15046", "7.5", "Eye"),
    ("GSM7486879_14817_Eye", "14817", "8", "Eye"),
    ("GSM7486868_14849_Eye", "14849", "10", "Eye"),
    ("GSM7486869_14680_Retina", "14680", "12", "Retina"),
    ("GSM7486874_15184_Retina", "15184", "21", "Retina"),
]


def _read_gz_member(tar: tarfile.TarFile, name: str):
    member = tar.getmember(name)
    return gzip.decompress(tar.extractfile(member).read())


def _load_sample(tar, gsm, sample, stage, tissue, rng):
    import anndata as ad
    import numpy as np
    import pandas as pd

    counts = pd.read_csv(io.BytesIO(_read_gz_member(tar, f"{gsm}_counts.csv.gz")), index_col=0)
    md = pd.read_csv(io.BytesIO(_read_gz_member(tar, f"{gsm}_md.csv.gz")), index_col=0)
    # counts is genes x cells; cap cells (columns) for speed, then transpose to cells x genes.
    cols = list(counts.columns)
    if len(cols) > CELLS_PER_SAMPLE:
        cols = list(rng.choice(cols, CELLS_PER_SAMPLE, replace=False))
    X = counts[cols].T  # cells x genes
    a = ad.AnnData(X.astype(np.float32))
    a.obs_names = [f"{sample}_{c}" for c in X.index]
    a.var_names = [str(g) for g in X.columns]
    # align the authors' per-cell metadata (barcode index uses '-1'; counts header uses '.1')
    md_idx = {str(i).replace("-", ".") : i for i in md.index}
    pct, dfc = [], []
    for c in X.index:
        key = md_idx.get(str(c))
        pct.append(float(md.at[key, "percent.mt"]) if key is not None and "percent.mt" in md else np.nan)
        dfc.append(str(md.at[key, "DF.classifications"]) if key is not None and "DF.classifications" in md else "NA")
    a.obs["sample"] = sample
    a.obs["stage_pcw"] = stage
    a.obs["tissue"] = tissue
    a.obs["percent_mt"] = pct
    a.obs["df_class"] = dfc
    return a


def main() -> None:
    import anndata as ad
    import numpy as np

    rng = np.random.default_rng(0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(TAR) as tar:
        parts = []
        for gsm, sample, stage, tissue in SUBSET:
            a = _load_sample(tar, gsm, sample, stage, tissue, rng)
            print(f"  {sample} ({stage} PCW {tissue}): {a.n_obs} cells x {a.n_vars} genes")
            parts.append(a)
    combined = ad.concat(parts, join="outer", fill_value=0)
    combined.obs_names_make_unique()
    # pandas 3 hands AnnData nullable StringArray obs columns/index; opt in to writing them
    # (read_anndata reads them back fine) so the h5ad serialises.
    ad.settings.allow_write_nullable_strings = True
    combined.write_h5ad(OUT)
    print(f"WROTE {OUT}  ({combined.n_obs} cells x {combined.n_vars} genes; "
          f"{combined.obs['sample'].nunique()} samples)")


if __name__ == "__main__":
    main()
