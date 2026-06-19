"""Real differential-abundance engine (cells-per-cluster counts -> DESeq2 + TMM).

Tests whether each cluster / cell-type changes in proportion between two conditions, the
statistically correct way (OSCA multi-sample): build the **cells-per-(cluster x sample)**
count table, then model it with the same DESeq2 engine the DE skills use — each *sample*
is the replicate, not each cell. Normalization defaults to TMM (the edgeR differential-
abundance convention), which blunts the compositional artefact whereby one cluster
expanding makes every other cluster look like it shrank. Reuses the shipped
``deg.run_real.deseq_results`` (pyDESeq2 + TMM); a proportion + Welch-t fallback runs when
pyDESeq2 is unavailable.
"""

# Obs columns that commonly carry the cluster / cell-type label, tried in order.
_LABEL_FALLBACKS = ("cell_type", "celltype", "CellType", "major_type", "cell_type9",
                    "leiden", "cluster", "clusters", "louvain", "label")


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    from skills._genes import read_anndata
    from skills._plotly import jsonable
    from skills._table import table
    from skills.deg.run_real import _CONDITION_FALLBACKS, _SAMPLE_FALLBACKS, _resolve_obs_col
    from skills.diff_abundance.run import _da_spec

    adata = read_anndata(data_path)
    obs = adata.obs
    sample_col = _resolve_obs_col(obs, params.get("sample_col"), _SAMPLE_FALLBACKS, "sample_col")
    condition_col = _resolve_obs_col(obs, params.get("condition_col"), _CONDITION_FALLBACKS, "condition_col")
    label_col = _resolve_obs_col(obs, params.get("label_col"), _LABEL_FALLBACKS, "label_col")

    samples = obs[sample_col].astype(str).to_numpy()
    conds = obs[condition_col].astype(str).to_numpy()
    labels = obs[label_col].astype(str).to_numpy()
    sample_order = list(dict.fromkeys(samples.tolist()))

    # Each sample must map to exactly one condition (it is the biological replicate).
    cond_of = {}
    for s in sample_order:
        here = set(conds[samples == s].tolist())
        if len(here) != 1:
            raise ValueError(
                f"sample '{s}' spans multiple {condition_col} values {sorted(here)} — "
                "each replicate must map to exactly one condition"
            )
        cond_of[s] = here.pop()

    reference, treatment = _pick_contrast(params, sorted({cond_of[s] for s in sample_order}), condition_col)
    keep_samples = [s for s in sample_order if cond_of[s] in (reference, treatment)]
    cond = [cond_of[s] for s in keep_samples]
    n_ref, n_treat = cond.count(reference), cond.count(treatment)
    if min(n_ref, n_treat) < 2:
        raise ValueError(
            f"differential abundance needs >=2 sample-replicates per condition "
            f"(got {reference}={n_ref}, {treatment}={n_treat})"
        )

    # cells-per-(cluster x sample) count table.
    counts = pd.crosstab(labels, samples).reindex(columns=keep_samples, fill_value=0)
    min_cells = int(params.get("min_cells", 10))
    counts = counts[counts.sum(axis=1) >= min_cells]  # drop near-absent clusters
    if counts.shape[0] < 1:
        raise ValueError(f"no cluster has >={min_cells} cells across the kept samples")

    normalization = str(params.get("normalization") or "tmm").strip().lower()
    clusters, lfc, padj, engine = _abundance_test(counts, cond, reference, treatment, normalization)

    n_cells = counts.sum(axis=1)
    subtitle = (
        f"{engine} · {treatment} (n={n_treat}) vs {reference} (n={n_ref}) · "
        f"{counts.shape[0]} clusters · cells-per-(cluster×sample); proportions are compositional"
    )
    spec = _da_spec(clusters, lfc, f"Differential abundance — {treatment} vs {reference}", subtitle)

    rows = []
    for c, fc, q in sorted(zip(clusters, lfc, padj), key=lambda t: abs(t[1]), reverse=True):
        direction = "expanding" if fc >= 0 else "shrinking"
        rows.append([c, round(float(fc), 4), (float(f"{q:.3g}") if q is not None else None),
                     int(n_cells.get(c, 0)), direction])
    spec["table"] = table(
        ["cluster", "log2FC abundance", "adj p", "cells", "direction"], rows,
        "Differential abundance (cells per cluster per sample)",
    )
    return jsonable(spec)


def _pick_contrast(params, groups, condition_col):
    """Resolve (reference, treatment); default the only two groups, else require both."""
    reference = str(params.get("reference") or "").strip()
    treatment = str(params.get("treatment") or "").strip()
    if not reference and not treatment:
        if len(groups) == 2:
            return groups[0], groups[1]
        raise ValueError(
            f"differential abundance needs a 2-group contrast but {len(groups)} {condition_col} "
            f"groups were found ({groups}); set `reference` and `treatment` to two of them."
        )
    for role, g in (("reference", reference), ("treatment", treatment)):
        if g not in groups:
            raise ValueError(f"{role} group '{g}' not among {condition_col} groups {groups}")
    if reference == treatment:
        raise ValueError("reference and treatment must be different groups")
    return reference, treatment


def _abundance_test(counts, cond, reference, treatment, normalization):
    """DESeq2 (TMM) on the cluster x sample count table -> (clusters, log2FC, padj, engine).

    Falls back to a per-sample-proportion log2FC + Welch t-test (BH-adjusted) when pyDESeq2
    is unavailable, so the skill still returns a sensible result.
    """
    import numpy as np
    import pandas as pd

    from skills.deg.run_real import deseq_results

    try:
        res, engine = deseq_results(counts, cond, reference, treatment, normalization)
        res = res.dropna(subset=["log2FoldChange"]).reindex(counts.index).dropna(subset=["log2FoldChange"])
        clusters = [str(c) for c in res.index]
        lfc = [float(v) for v in res["log2FoldChange"]]
        padj = [float(v) if pd.notna(v) else None for v in res["padj"]]
        return clusters, lfc, padj, engine
    except ImportError:
        from scipy.stats import ttest_ind

        prop = counts.div(counts.sum(axis=0), axis=1)  # per-sample proportions (cols sum to 1)
        ref_cols = [c for c, g in zip(counts.columns, cond) if g == reference]
        treat_cols = [c for c, g in zip(counts.columns, cond) if g == treatment]
        clusters, lfc, pvals = [], [], []
        for cl in counts.index:
            a, b = prop.loc[cl, ref_cols].to_numpy(float), prop.loc[cl, treat_cols].to_numpy(float)
            clusters.append(str(cl))
            lfc.append(float(np.log2((b.mean() + 1e-9) / (a.mean() + 1e-9))))
            pvals.append(float(ttest_ind(b, a, equal_var=False).pvalue))
        padj = [float(v) for v in _bh(np.nan_to_num(np.asarray(pvals), nan=1.0))]
        return clusters, lfc, padj, "proportion log2FC + Welch t (pyDESeq2 absent)"


def _bh(pvals):
    """Vectorized Benjamini-Hochberg adjusted p-values (step-up, monotone-enforced)."""
    import numpy as np

    p = np.asarray(pvals, dtype=float)
    n = p.size
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1.0)
    adj = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(adj, 0.0, 1.0)
    return out
