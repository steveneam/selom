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

    requested_groupby = str(params.get("groupby") or "sample")
    groupby = requested_groupby
    if groupby not in obs.columns:
        groupby = next((c for c in _GROUP_FALLBACKS if c in obs.columns), None)

    # Adaptive MAD outlier filter (opt-in) — computed on FULL data, before subsampling.
    do_filter = to_bool(params.get("filter", False))
    nmads = float(params.get("nmads", 3.0))
    discard, filter_rows = (_adaptive_filter(obs, groupby, nmads) if do_filter else (None, None))

    # Doublet detection (opt-in) — Scrublet, per capture (batch_key), on the raw counts.
    do_doublets = to_bool(params.get("doublets", False))
    doublet_rows = doublet_thr = None
    if do_doublets:
        doublet_thr = float(params.get("doublet_threshold", 0.25))
        batch_key = groupby if (groupby and groupby in obs.columns) else None
        # The automatic histogram threshold needs scikit-image; pass an explicit cut so the
        # detector stays dependency-free. Scores are computed regardless of the threshold.
        sc.pp.scrublet(adata, threshold=doublet_thr, batch_key=batch_key, random_state=0)
        obs = adata.obs
        doublet_rows = _doublet_rates(obs, groupby)

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
    n_total = int(adata.n_obs)
    notes = []
    if do_filter:
        notes.append(f"removed {int(discard.sum())}/{n_total} (MAD, nmads={nmads:g})")
    if do_doublets:
        n_dbl = int(obs["predicted_doublet"].fillna(False).to_numpy().astype(bool).sum())
        notes.append(f"{n_dbl}/{n_total} doublets (Scrublet, thr={doublet_thr:g})")
    if notes:
        from skills._table import table

        spec["layout"]["title"]["text"] = "Per-cell QC — " + " · ".join(notes)
        if do_filter and do_doublets:
            # One per-group summary combining both QC concerns (rows share group order).
            dbl_by_group = {r[0]: r for r in doublet_rows}
            rows = [[*fr, *(dbl_by_group.get(fr[0], [fr[0], fr[1], 0, 0.0])[2:])] for fr in filter_rows]
            spec["table"] = table(
                ["group", "cells", "kept", "QC outliers", "QC %", "doublets", "doublet %"],
                rows,
                "Adaptive QC filter + doublet detection (per group)",
            )
        elif do_filter:
            spec["table"] = table(
                ["group", "cells", "kept", "removed", "removed %"],
                filter_rows,
                "Adaptive QC filter (per-group MAD outliers)",
            )
        else:
            spec["table"] = table(
                ["group", "cells", "doublets", "doublet %"],
                doublet_rows,
                "Doublet detection (Scrublet, per group)",
            )
    # The two facts the params cannot supply, both of which the paragraph was asserting wrongly
    # (WS1.2 / the `layout.meta` outcome pattern; lifted as `_qc_run` by methods.build_body):
    #   · the grouping column RESOLVED — a requested column that is absent falls back through
    #     _GROUP_FALLBACKS, or to no split at all, while the prose named the column the user asked
    #     for. The same substitute-and-say-nothing shape as `violin`/`deg`.
    #   · how many cells the VIOLINS actually show. `max_cells` randomly subsamples (seeded) what is
    #     plotted, while the filter/doublet counts and the table are computed on every cell — so the
    #     figure and its own table describe different populations, and nothing said so.
    spec["layout"].setdefault("meta", {})["qc"] = {
        "groupby": groupby, "requested_groupby": requested_groupby,
        "shown": int(len(idx)), "total": n_total,
    }
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


def _doublet_rates(obs, groupby):
    """Per-group doublet counts from Scrublet's boolean ``predicted_doublet`` obs column.

    Returns rows ``[group, cells, doublets, doublet %]`` (+ an overall ``all`` row when
    there is more than one group), mirroring the adaptive-filter summary so the two can be
    merged into one per-group QC table. Doublets are simulated and scored per capture
    (``batch_key``) upstream; this only tallies the resulting flags."""
    import numpy as np

    pred = np.asarray(obs["predicted_doublet"].fillna(False).to_numpy(), dtype=bool)
    groups = obs[groupby].astype(str).to_numpy() if groupby else np.array(["all"] * len(obs))
    rows = []
    for g in dict.fromkeys(groups.tolist()):
        m = groups == g
        n, d = int(m.sum()), int(pred[m].sum())
        rows.append([str(g), n, d, round(100.0 * d / max(n, 1), 1)])
    if len(rows) > 1:
        n, d = len(obs), int(pred.sum())
        rows.append(["all", n, d, round(100.0 * d / max(n, 1), 1)])
    return rows


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
