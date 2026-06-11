"""Generate the P0 demo dataset: ``app/frontend/sample-data/demo.h5ad`` from pbmc3k.

Run from ``app/backend`` with the scRNA stack installed::

    uv run --extra scrna python scripts/make_demo.py

Writes scanpy's pbmc3k (raw counts, ~2700 cells x ~32738 genes) as an .h5ad that a
user can upload to drive the P0 hello-UMAP end-to-end. pbmc3k downloads once from the
scanpy datasets host, then is cached locally.
"""

import pathlib

import anndata as ad
import scanpy as sc

# pandas 3.0 stores string columns (e.g. the obs index) as a nullable StringArray;
# anndata gates writing those behind an opt-in for back-compat with readers < 0.11.
# Our runtime is anndata 0.12+, so opting in is safe and keeps the demo writable.
ad.settings.allow_write_nullable_strings = True


def main() -> None:
    out = (
        pathlib.Path(__file__).resolve().parents[2]
        / "frontend"
        / "sample-data"
        / "demo.h5ad"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    adata = sc.datasets.pbmc3k()
    adata.write_h5ad(out)
    print(f"wrote {out}  ({adata.n_obs} cells x {adata.n_vars} genes)")


if __name__ == "__main__":
    main()
