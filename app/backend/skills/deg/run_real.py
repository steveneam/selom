"""Real differential-expression engines — scRNA (scanpy) and bulk (pyDESeq2).

Mode is chosen from the ``mode`` param (``auto`` -> scRNA for ``.h5ad``, bulk for a
counts table). The scRNA + 2-group bulk paths emit a horizontal bar of the top-N
genes by signed score (up = cyan, down = rose); the time-course path emits
mean-expression trajectories across timepoints for the top trending genes.

Bulk input contract: a CSV/XLSX of raw integer counts, genes in rows (first column
= gene id), samples in columns. The sample->condition design is taken from a design
sheet when supplied (``_design_path``, joined on sample id), else inferred from each
column name with the trailing replicate suffix stripped (``ctrl_1``/``treat_2`` ->
``ctrl``/``treat``; ``B7_..._ASO_AK1_1`` -> ``B7_..._ASO_AK1``). For a 2-group
contrast pick ``reference`` + ``treatment`` (logFC = treatment vs reference); with
exactly two groups they default automatically.
"""

import re

UP = "#22d3ee"
DOWN = "#f43f5e"
DEFAULT_REP_REGEX = r"_\d+$"  # trailing replicate suffix: ctrl_1 -> ctrl


def run(data_path: str, params: dict) -> dict:
    mode = (params.get("mode") or "auto").lower()
    if mode == "auto":
        mode = "scrna" if str(data_path).lower().endswith((".h5ad", ".h5")) else "bulk"
    if mode in ("timecourse", "time-course", "time_course"):
        return _timecourse(data_path, params)
    if mode == "bulk":
        return _bulk(data_path, params)
    return _scrna(data_path, params)


def _read_counts(data_path: str):
    """Load a genes x samples raw-count table from CSV or XLSX (gene id = first column)."""
    import pandas as pd

    if str(data_path).lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(data_path, index_col=0)
    return pd.read_csv(data_path, index_col=0)


def _load_design(params: dict):
    """Read the optional design sheet (sample id in the first column or a ``SampleID``/
    ``sample`` column) and return it indexed by sample id, or None if not supplied."""
    import pandas as pd

    design_path = params.get("_design_path")
    if not design_path:
        return None
    if str(design_path).lower().endswith((".xlsx", ".xls")):
        design = pd.read_excel(design_path)
    else:
        design = pd.read_csv(design_path)  # comma-delimited even when named .tsv here
    id_col = next(
        (c for c in design.columns if str(c).strip().lower() in ("sampleid", "sample", "sample_id", "id")),
        design.columns[0],
    )
    return design.set_index(design[id_col].astype(str))


def _labels_from_design_or_names(columns, params: dict):
    """Map each count column -> its group label, from a ``group_col`` of the design
    sheet when available, else by stripping the replicate suffix from the name."""
    design = _load_design(params)
    if design is not None and params.get("group_col"):
        group_col = params["group_col"]
        if group_col not in design.columns:
            raise ValueError(
                f"group_col '{group_col}' not in design columns {list(design.columns)}"
            )
        # The design sheet is the source of truth: count columns with no design row
        # (e.g. QC-dropped samples) are excluded, not errors.
        return {
            c: str(design[group_col].get(str(c)))
            for c in columns
            if str(c) in design.index and str(design[group_col].get(str(c)))
        }
    rep_regex = params.get("group_regex") or DEFAULT_REP_REGEX
    return {c: re.sub(rep_regex, "", str(c)) for c in columns}


def _scrna(data_path: str, params: dict) -> dict:
    import scanpy as sc

    from skills._engine import to_bool
    from skills._plotly import jsonable

    from skills._genes import read_anndata

    adata = read_anndata(data_path)
    sc.pp.filter_genes(adata, min_cells=3)
    if to_bool(params.get("normalize", True)):  # skip if input is already normalized
        sc.pp.normalize_total(adata, target_sum=1e4)
        sc.pp.log1p(adata)

    groupby = params.get("groupby") or "leiden"
    if groupby not in adata.obs.columns:
        n_pcs = max(2, min(50, adata.n_obs - 1, adata.n_vars - 1))
        sc.pp.pca(adata, n_comps=n_pcs)
        sc.pp.neighbors(adata, n_neighbors=15, n_pcs=n_pcs)
        sc.tl.leiden(adata, flavor="igraph", n_iterations=2, directed=False)
        groupby = "leiden"

    sc.tl.rank_genes_groups(adata, groupby, method=params.get("method", "wilcoxon"))
    res = adata.uns["rank_genes_groups"]
    group0 = res["names"].dtype.names[0]
    top_n = int(params["top_n"])
    names = [str(res["names"][group0][i]) for i in range(top_n)]
    scores = [float(res["scores"][group0][i]) for i in range(top_n)]
    title = f"Top markers — {groupby} group {group0}"
    return _bar(names, scores, title, jsonable)


def _bulk(data_path: str, params: dict) -> dict:
    from skills._plotly import jsonable

    counts = _read_counts(data_path)
    labels = _labels_from_design_or_names(counts.columns, params)
    groups = sorted({v for v in labels.values() if v})

    reference = str(params.get("reference") or "").strip()
    treatment = str(params.get("treatment") or "").strip()
    if not reference and not treatment:
        if len(groups) == 2:
            reference, treatment = groups[0], groups[1]
        else:
            raise ValueError(
                f"bulk DEG needs a 2-group contrast but {len(groups)} groups were detected "
                f"({groups}). Set `reference` and `treatment` to two of them "
                f"(logFC = treatment vs reference)."
            )
    for role, g in (("reference", reference), ("treatment", treatment)):
        if g not in groups:
            raise ValueError(f"{role} group '{g}' not among detected groups {groups}")
    if reference == treatment:
        raise ValueError("reference and treatment must be different groups")

    keep = [c for c in counts.columns if labels.get(c) in (reference, treatment)]
    sub = counts[keep].copy()
    cond = [labels[c] for c in keep]
    n_ref, n_treat = cond.count(reference), cond.count(treatment)
    if min(n_ref, n_treat) < 2:
        raise ValueError(
            f"each group needs >=2 replicates for bulk DE (got {reference}={n_ref}, {treatment}={n_treat})"
        )

    # Drop near-zero genes before fitting (pyDESeq2 best practice; stabilises dispersion).
    min_count = int(params.get("min_count", 10))
    sub = sub[sub.sum(axis=1) >= min_count]

    top_n = int(params["top_n"])
    names, scores, engine = _bulk_deseq(sub, cond, reference, treatment, top_n)
    subtitle = f"{engine} · {treatment} (n={n_treat}) vs {reference} (n={n_ref}) · {sub.shape[0]} genes tested"
    return _bar(names, scores, f"Top DE genes — {treatment} vs {reference}", jsonable, subtitle)


def _bulk_deseq(sub, cond, reference, treatment, top_n):
    """pyDESeq2 Wald (treatment vs reference) on raw counts; CPM-log2FC fallback if absent.

    Returns (gene names, signed log2FC scores, engine label) for the top-N by |log2FC|.
    """
    import numpy as np
    import pandas as pd

    try:
        from pydeseq2.dds import DeseqDataSet
        from pydeseq2.ds import DeseqStats

        metadata = pd.DataFrame({"condition": cond}, index=sub.columns)
        dds = DeseqDataSet(
            counts=sub.T, metadata=metadata, design="~condition", ref_level=["condition", reference], quiet=True
        )
        dds.deseq2()
        stat = DeseqStats(dds, contrast=["condition", treatment, reference], quiet=True)
        stat.summary()
        res = stat.results_df.dropna(subset=["log2FoldChange", "padj"])
        res = res.reindex(res["log2FoldChange"].abs().sort_values(ascending=False).index).head(top_n)
        return [str(g) for g in res.index], [float(v) for v in res["log2FoldChange"]], "pyDESeq2 (Wald)"
    except ImportError:
        # Light fallback when pyDESeq2 isn't installed: log2FC of mean CPM per group.
        cpm = sub.div(sub.sum(axis=0), axis=1) * 1e6
        a = cpm.loc[:, [c == reference for c in cond]].mean(axis=1)
        b = cpm.loc[:, [c == treatment for c in cond]].mean(axis=1)
        lfc = np.log2((b + 1.0) / (a + 1.0))
        lfc = lfc.reindex(lfc.abs().sort_values(ascending=False).index).head(top_n)
        return [str(g) for g in lfc.index], [float(v) for v in lfc], "CPM log2FC (pyDESeq2 absent)"


def _bar(names, scores, title, jsonable, subtitle=None) -> dict:
    from skills._table import table

    # Ascending so the strongest |score| sits at the top of the horizontal bar.
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    names = [names[i] for i in order]
    scores = [scores[i] for i in order]
    spec = {
        "data": [
            {
                "type": "bar",
                "orientation": "h",
                "x": scores,
                "y": names,
                "marker": {"color": [UP if s >= 0 else DOWN for s in scores]},
                "name": "score",
            }
        ],
        "layout": {
            "title": {"text": title if not subtitle else f"{title}<br><sub>{subtitle}</sub>"},
            "xaxis": {"title": {"text": "log2 fold-change"}},
            "yaxis": {"title": {"text": "gene"}},
            "bargap": 0.3,
        },
    }
    # Statistics node (Pillar 1) — the top genes, strongest effect first.
    tbl = sorted(range(len(scores)), key=lambda i: abs(scores[i]), reverse=True)
    spec["table"] = table(
        ["gene", "log2 fold-change"],
        [[names[i], round(float(scores[i]), 4)] for i in tbl],
        "Top differential genes",
    )
    return jsonable(spec)


# Map common timepoint labels to a numeric axis: "P14"/"day7"/"6h" -> 14/7/6.
def _numeric_time(value) -> float:
    m = re.search(r"-?\d+(?:\.\d+)?", str(value))
    if not m:
        raise ValueError(f"could not read a number from timepoint '{value}'")
    return float(m.group())


def _timecourse(data_path: str, params: dict) -> dict:
    """Genes whose expression changes across an ordered time-course.

    pyDESeq2 0.5.4 has no LRT, so time is fit as a *continuous* covariate and the
    time coefficient is Wald-tested (a maSigPro-style linear-trend test). Requires a
    design sheet (``_design_path``) with a sample-id column + a ``time_col`` and an
    optional ``group_col`` to restrict to one stratum (e.g. one tissue). The figure is
    a line plot of mean normalised expression vs time for the top trending genes.
    """
    import numpy as np

    from skills._plotly import jsonable

    counts = _read_counts(data_path)
    design = _load_design(params)
    if design is None:
        raise ValueError(
            "time-course DE needs a design sheet (sample id + a time column) — column-name "
            "inference can't recover timepoints. Upload a design file."
        )
    time_col = params.get("time_col") or "time"
    if time_col not in design.columns:
        raise ValueError(f"time_col '{time_col}' not in design columns {list(design.columns)}")

    # Optionally restrict to a single stratum so the trend isn't confounded (e.g. one tissue).
    group_col = params.get("group_col")
    group_val = str(params.get("group_val") or "").strip()
    samples = [c for c in counts.columns if str(c) in design.index]
    if group_col and group_val:
        if group_col not in design.columns:
            raise ValueError(f"group_col '{group_col}' not in design columns {list(design.columns)}")
        samples = [s for s in samples if str(design[group_col].get(str(s))) == group_val]
    if len(samples) < 4:
        raise ValueError(
            f"time-course needs >=4 samples spanning the timepoints; matched {len(samples)} "
            f"(check the design join / group filter)"
        )

    sub = counts[samples].copy()
    sub = sub[sub.sum(axis=1) >= int(params.get("min_count", 10))]
    times = np.array([_numeric_time(design[time_col].get(str(s))) for s in samples], dtype=float)
    if len(set(times.tolist())) < 3:
        raise ValueError(f"time-course needs >=3 distinct timepoints, found {sorted(set(times.tolist()))}")

    # Optional covariate to adjust for a known confounder (e.g. genotype): the trend is
    # then tested net of it (design ~covariate + time), keeping the test honest.
    covariate_col = params.get("covariate_col")
    covariate = None
    if covariate_col:
        if covariate_col not in design.columns:
            raise ValueError(f"covariate_col '{covariate_col}' not in design columns {list(design.columns)}")
        covariate = [str(design[covariate_col].get(str(s))) for s in samples]

    top_n = int(params["top_n"])
    ranked, subtitle = _timecourse_rank(sub, samples, times, top_n, covariate)

    # Mean normalised (log2 CPM) expression per distinct timepoint, one line per gene.
    cpm = np.log2(sub.div(sub.sum(axis=0), axis=1) * 1e6 + 1.0)
    uniq = sorted(set(times.tolist()))
    cols_by_t = {t: [samples[i] for i in range(len(samples)) if times[i] == t] for t in uniq}
    data = []
    for gene in ranked:
        y = [float(cpm.loc[gene, cols_by_t[t]].mean()) for t in uniq]
        data.append({"type": "scatter", "mode": "lines+markers", "x": uniq, "y": y, "name": str(gene)})

    spec = {
        "data": data,
        "layout": {
            "title": {"text": f"Time-course DE — top {len(ranked)} trending genes<br><sub>{subtitle}</sub>"},
            "xaxis": {"title": {"text": f"{time_col} (numeric)"}},
            "yaxis": {"title": {"text": "mean log2 CPM"}},
        },
    }
    return jsonable(spec)


def _timecourse_rank(sub, samples, times, top_n, covariate=None):
    """Rank genes by the significance of a linear time trend.

    pyDESeq2 with a continuous time factor + Wald on the time coefficient when present
    (adjusting for ``covariate`` if given via design ~covariate + time); else a Pearson
    correlation of log2-CPM vs time (deterministic light fallback). Returns (top gene
    index, engine/subtitle label).
    """
    import numpy as np
    import pandas as pd

    try:
        from pydeseq2.dds import DeseqDataSet
        from pydeseq2.ds import DeseqStats

        meta = {"time": times}
        design = "~time"
        if covariate is not None and len(set(covariate)) >= 2:
            meta["covariate"] = covariate
            design = "~covariate + time"
        metadata = pd.DataFrame(meta, index=sub.columns)
        # time is continuous (auto-detected from the float column). DeseqStats needs a
        # contrast over the design columns, so test the time coefficient directly with a
        # unit contrast vector (the [factor, level, ref] form is categorical-only).
        dds = DeseqDataSet(counts=sub.T, metadata=metadata, design=design, quiet=True)
        dds.deseq2()
        dm_cols = list(dds.obsm["design_matrix"].columns)
        contrast = np.zeros(len(dm_cols))
        contrast[dm_cols.index("time")] = 1.0
        stat = DeseqStats(dds, contrast=contrast, quiet=True)
        stat.summary()
        res = stat.results_df.dropna(subset=["padj"])
        res = res.sort_values("padj")
        n_sig = int((res["padj"] < 0.05).sum())
        ranked = [str(g) for g in res.head(top_n).index]
        adj = " (adj. covariate)" if design != "~time" else ""
        return ranked, f"pyDESeq2 continuous-time Wald{adj} · {len(samples)} samples · {n_sig} genes FDR<0.05"
    except ModuleNotFoundError:
        cpm = np.log2(sub.div(sub.sum(axis=0), axis=1) * 1e6 + 1.0)
        t = times - times.mean()
        denom = np.sqrt((t**2).sum())
        x = cpm.sub(cpm.mean(axis=1), axis=0)
        corr = (x.mul(t, axis=1).sum(axis=1)) / (np.sqrt((x**2).sum(axis=1)) * denom + 1e-12)
        ranked = [str(g) for g in corr.abs().sort_values(ascending=False).head(top_n).index]
        return ranked, f"Pearson time-trend (pyDESeq2 absent) · {len(samples)} samples"
