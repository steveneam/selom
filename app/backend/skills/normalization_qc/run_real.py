"""Real per-cell QC engine (scanpy).

Computes standard per-cell QC metrics (total counts, genes per cell, mitochondrial
percentage) with ``sc.pp.calculate_qc_metrics`` on the raw matrix, splits them by a
sample/batch obs column (auto-detected if the requested one is absent), subsamples for
a light editable figure, and feeds the shared ``qc_panel_spec``.

With ``filter=true`` it also applies the adaptive median-absolute-deviation (MAD)
outlier procedure (scater/OSCA): per group, flag cells whose log library size or log
genes-detected sit more than ``nmads`` MADs BELOW the median, or whose mitochondrial %
sits ``nmads`` MADs ABOVE it. Adaptive thresholds adapt to per-batch depth/capture
without manual cutoffs. The figure gains a per-group kept/removed summary table; the
metrics are still shown for ALL cells so biased removal across batches is visible.
"""

from skills._engine import to_bool
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

    # Adaptive MAD outlier filter (opt-in) — computed on FULL data, before subsampling.
    do_filter = to_bool(params.get("filter", False))
    nmads = float(params.get("nmads", 3.0))
    discard, filter_rows = (_adaptive_filter(obs, groupby, nmads) if do_filter else (None, None))

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

    spec = qc_panel_spec(panels, "Per-cell QC")
    if do_filter:
        from skills._table import table

        n_total, n_removed = int(adata.n_obs), int(discard.sum())
        spec["layout"]["title"]["text"] = (
            f"Per-cell QC + adaptive filter — removed {n_removed}/{n_total} cells "
            f"(MAD, nmads={nmads:g})"
        )
        spec["table"] = table(
            ["group", "cells", "kept", "removed", "removed %"],
            filter_rows,
            "Adaptive QC filter (per-group MAD outliers)",
        )
    return jsonable(spec)


def _adaptive_filter(obs, groupby, nmads):
    """Per-group adaptive MAD outlier mask (scater/OSCA procedure).

    Flags cells with a LOW log library size or log genes-detected, or a HIGH
    mitochondrial %, more than ``nmads`` MADs from the per-group median. Returns the
    full-length boolean discard mask + a per-group ``[group, n, kept, removed, %]`` table
    (with an overall ``all`` row when there is more than one group)."""
    import numpy as np

    total = obs["total_counts"].to_numpy(dtype=float)
    genes = obs["n_genes_by_counts"].to_numpy(dtype=float)
    mito = (obs["pct_counts_mt"].to_numpy(dtype=float)
            if "pct_counts_mt" in obs.columns else np.zeros(len(obs)))
    log_total, log_genes = np.log1p(total), np.log1p(genes)

    groups = obs[groupby].astype(str).to_numpy() if groupby else np.array(["all"] * len(obs))
    discard = np.zeros(len(obs), dtype=bool)
    rows = []
    for g in dict.fromkeys(groups.tolist()):
        m = groups == g
        d = m & (_below(log_total, m, nmads) | _below(log_genes, m, nmads) | _above(mito, m, nmads))
        discard |= d
        n, rem = int(m.sum()), int(d.sum())
        rows.append([str(g), n, n - rem, rem, round(100.0 * rem / max(n, 1), 1)])
    if len(rows) > 1:
        n, rem = len(obs), int(discard.sum())
        rows.append(["all", n, n - rem, rem, round(100.0 * rem / max(n, 1), 1)])
    return discard, rows


def _mad_thresholds(values, mask, nmads):
    """Per-group (median, scaled-MAD) on the masked subset — MAD scaled to be
    comparable to a standard deviation (matching R's ``mad()`` default)."""
    import numpy as np
    from scipy.stats import median_abs_deviation

    sub = values[mask]
    return float(np.median(sub)), float(median_abs_deviation(sub, scale="normal"))


def _below(values, mask, nmads):
    """Full-length mask of group cells more than ``nmads`` MADs below the group median.
    A zero MAD (degenerate/constant metric) flags nothing rather than everything."""
    import numpy as np

    med, mad = _mad_thresholds(values, mask, nmads)
    out = np.zeros(len(values), dtype=bool)
    if mad > 0:
        out[mask] = values[mask] < (med - nmads * mad)
    return out


def _above(values, mask, nmads):
    """Full-length mask of group cells more than ``nmads`` MADs above the group median."""
    import numpy as np

    med, mad = _mad_thresholds(values, mask, nmads)
    out = np.zeros(len(values), dtype=bool)
    if mad > 0:
        out[mask] = values[mask] > (med + nmads * mad)
    return out
