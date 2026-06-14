"""Real per-cell QC engine (scanpy).

Computes standard per-cell QC metrics (total counts, genes per cell, mitochondrial
percentage) with ``sc.pp.calculate_qc_metrics`` on the raw matrix, splits them by a
sample/batch obs column (auto-detected if the requested one is absent), subsamples for
a light editable figure, and feeds the shared ``qc_panel_spec``.
"""

from skills._genes import read_anndata
from skills._plotly import jsonable
from skills.normalization_qc.run import qc_panel_spec

_GROUP_FALLBACKS = ("sample", "batch", "orig.ident", "Sample", "library", "donor")
_METRICS = [("total_counts", "Total counts"), ("n_genes_by_counts", "Genes per cell"),
            ("pct_counts_mt", "Mito %")]


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import scanpy as sc

    adata = read_anndata(data_path)
    # numpy bool (not a pandas nullable BooleanArray, which scipy sparse can't index with)
    names_up = adata.var_names.str.upper()
    adata.var["mt"] = np.asarray(names_up.str.startswith("MT-") | names_up.str.startswith("MT."), dtype=bool)
    sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], inplace=True, percent_top=None, log1p=False)
    obs = adata.obs

    groupby = params.get("groupby") or "sample"
    if groupby not in obs.columns:
        groupby = next((c for c in _GROUP_FALLBACKS if c in obs.columns), None)

    idx = np.arange(adata.n_obs)
    max_cells = int(params.get("max_cells", 6000))
    if adata.n_obs > max_cells:
        idx = np.sort(np.random.default_rng(0).choice(idx, size=max_cells, replace=False))

    groups = (obs[groupby].astype(str).to_numpy()[idx] if groupby else np.array(["all"] * len(idx)))
    order = list(dict.fromkeys(groups.tolist()))  # stable unique group order

    panels = []
    for key, label in _METRICS:
        if key not in obs.columns:
            continue
        vals = obs[key].to_numpy(dtype=float)[idx]
        by_group = {g: [round(float(v), 3) for v, gg in zip(vals, groups) if gg == g] for g in order}
        panels.append({"label": label, "values_by_group": by_group})

    return jsonable(qc_panel_spec(panels, "Per-cell QC"))
