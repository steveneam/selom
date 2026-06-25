"""Real differential-expression engines — scRNA (scanpy) and bulk (pyDESeq2).

Mode is chosen from the ``mode`` param (``auto`` -> scRNA for ``.h5ad``, bulk for a
counts table). The scRNA + 2-group bulk paths emit a horizontal bar of the top-N
genes by signed score (up = cyan, down = rose); the time-course path emits
mean-expression trajectories across timepoints for the top trending genes.

``mode="pseudobulk"`` is the statistically correct way to compare CONDITIONS on
single-cell data: per-cell tests treat each cell as a biological replicate, which is
pseudoreplication and inflates false positives (Lun & Marioni 2017; Squair 2021). So we
sum each sample's raw counts (optionally within one cell-type) into one profile per
biological replicate, then run the same bulk DESeq2 engine on those pseudo-bulk samples.

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
    if mode in ("pseudobulk", "pseudo-bulk", "pseudo_bulk"):
        return _pseudobulk(data_path, params)
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
    """Read the optional design sheet → DataFrame indexed by sample id, or None if not supplied.
    Delegates to the shared loader (``skills._design``) so the id-column heuristic is identical
    wherever a sample sheet is consumed (deg contrast, heatmap annotation tracks)."""
    from skills._design import load_design

    return load_design(params)


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


# Common obs columns that carry the biological-replicate / condition labels, tried in
# order when the requested column is absent (real h5ads disagree on the name).
_SAMPLE_FALLBACKS = ("sample", "Sample", "sample_id", "donor", "orig.ident", "library", "batch")
_CONDITION_FALLBACKS = ("condition", "Condition", "genotype", "group", "treatment", "disease", "status")


def _resolve_obs_col(obs, requested, fallbacks, label: str) -> str:
    """The requested obs column if present, else the first known alias; raise otherwise."""
    requested = str(requested or "").strip()
    if requested:
        if requested in obs.columns:
            return requested
        raise ValueError(f"{label} '{requested}' not in obs columns {list(obs.columns)}")
    for c in fallbacks:
        if c in obs.columns:
            return c
    raise ValueError(f"{label} not given and no known alias found in obs columns {list(obs.columns)}")


def _looks_like_counts(matrix) -> bool:
    """True if the matrix looks like raw integer counts (non-negative, ~integer-valued).

    Sampled (first 10k stored values) so it stays cheap on big sparse matrices. DESeq2
    models raw counts, so a normalized/log matrix must be rejected before aggregation.
    """
    import numpy as np
    import scipy.sparse as sp

    # scipy-sparse `.data` is the stored nonzero values; a dense ndarray's `.data` is a raw
    # buffer (not values), so only trust `.data` for sparse and flatten dense explicitly.
    vals = np.asarray(matrix.data if sp.issparse(matrix) else np.asarray(matrix).ravel())
    if vals.size == 0:
        return False
    sample = np.asarray(vals[:10000], dtype=float)
    return bool(np.all(sample >= 0) and np.allclose(sample, np.round(sample), atol=1e-6))


def _raw_counts(adata):
    """Return (counts matrix [cells x genes], var_names, provenance note) of RAW counts.

    Prefer a ``counts`` layer, then ``.X``, then ``.raw`` (only when its genes match) —
    taking the FIRST source that looks like integer counts. Raise a clear error if only
    normalized values are available, since pseudo-bulk + DESeq2 need raw counts.
    """
    candidates = []
    layers = getattr(adata, "layers", None)
    if layers is not None and "counts" in layers:
        candidates.append(("layers['counts']", layers["counts"], list(adata.var_names)))
    candidates.append(("X", adata.X, list(adata.var_names)))
    raw = getattr(adata, "raw", None)
    if raw is not None and raw.shape[0] == adata.n_obs and list(raw.var_names) == list(adata.var_names):
        candidates.append((".raw", raw.X, list(adata.var_names)))

    for note, matrix, var_names in candidates:
        if _looks_like_counts(matrix):
            return matrix, var_names, note
    raise ValueError(
        "pseudobulk DE needs RAW integer counts, but the AnnData only has normalized/log "
        "values (checked layers['counts'], .X, .raw). Provide raw counts — e.g. store them "
        "in a 'counts' layer before running."
    )


def _pseudobulk(data_path: str, params: dict) -> dict:
    """Pseudo-bulk DE between conditions: sum raw counts per biological replicate (within
    one cell-type if ``label_col``/``label`` are given) into one profile per sample, then
    run the bulk DESeq2 engine on those pseudo-bulk samples. Aggregating to the replicate
    level is what makes a multi-sample comparison statistically valid (samples, not cells,
    are the unit of replication).
    """
    import numpy as np
    import pandas as pd

    from skills._genes import read_anndata
    from skills._plotly import jsonable

    adata = read_anndata(data_path)
    obs = adata.obs

    sample_col = _resolve_obs_col(obs, params.get("sample_col"), _SAMPLE_FALLBACKS, "sample_col")
    condition_col = _resolve_obs_col(obs, params.get("condition_col"), _CONDITION_FALLBACKS, "condition_col")

    # Optional: restrict the contrast to a single cell-type / cluster.
    label_col = str(params.get("label_col") or "").strip()
    label_val = str(params.get("label") or params.get("label_val") or "").strip()
    label_note = ""
    if label_col:
        if label_col not in obs.columns:
            raise ValueError(f"label_col '{label_col}' not in obs columns {list(obs.columns)}")
        if not label_val:
            raise ValueError(
                f"label_col '{label_col}' given without `label` — set `label` to one "
                f"{label_col} value to restrict the pseudobulk contrast to a single cell type"
            )
        mask = obs[label_col].astype(str).to_numpy() == label_val
        if not mask.any():
            raise ValueError(f"no cells with {label_col} == '{label_val}'")
        adata = adata[mask].copy()
        obs = adata.obs
        label_note = f" · {label_col}={label_val}"

    counts, var_names, _src = _raw_counts(adata)
    samples = obs[sample_col].astype(str).to_numpy()
    conds = obs[condition_col].astype(str).to_numpy()
    order = list(dict.fromkeys(samples.tolist()))  # stable unique sample order

    # Sum raw counts per sample -> one pseudo-bulk profile; track cell count + condition.
    pb, n_cells, cond_of = {}, {}, {}
    for s in order:
        idx = np.where(samples == s)[0]
        n_cells[s] = int(idx.size)
        block = counts[idx]
        pb[s] = np.asarray(block.sum(axis=0)).ravel()
        here = set(conds[idx].tolist())
        if len(here) != 1:
            raise ValueError(
                f"sample '{s}' spans multiple {condition_col} values {sorted(here)} — "
                "each biological replicate must map to exactly one condition"
            )
        cond_of[s] = here.pop()

    min_cells = int(params.get("min_cells", 10))
    kept = [s for s in order if n_cells[s] >= min_cells]
    dropped = [s for s in order if n_cells[s] < min_cells]
    if len(kept) < 2:
        raise ValueError(
            f"pseudobulk needs >=2 samples with >={min_cells} cells "
            f"(kept {len(kept)} of {len(order)}{label_note})"
        )

    reference = str(params.get("reference") or "").strip()
    treatment = str(params.get("treatment") or "").strip()
    groups = sorted({cond_of[s] for s in kept})
    if not reference and not treatment:
        if len(groups) == 2:
            reference, treatment = groups[0], groups[1]
        else:
            raise ValueError(
                f"pseudobulk DE needs a 2-group contrast but {len(groups)} {condition_col} "
                f"groups were found ({groups}); set `reference` and `treatment` to two of them "
                "(logFC = treatment vs reference)."
            )
    for role, g in (("reference", reference), ("treatment", treatment)):
        if g not in groups:
            raise ValueError(f"{role} group '{g}' not among {condition_col} groups {groups}")
    if reference == treatment:
        raise ValueError("reference and treatment must be different groups")

    keep_cols = [s for s in kept if cond_of[s] in (reference, treatment)]
    cond = [cond_of[s] for s in keep_cols]
    n_ref, n_treat = cond.count(reference), cond.count(treatment)
    if min(n_ref, n_treat) < 2:
        raise ValueError(
            f"each condition needs >=2 sample-replicates for pseudobulk DE "
            f"(got {reference}={n_ref}, {treatment}={n_treat})"
        )

    mat = np.vstack([pb[s] for s in keep_cols]).T  # genes x samples
    sub = pd.DataFrame(mat, index=[str(g) for g in var_names], columns=keep_cols)
    sub = sub[sub.sum(axis=1) >= int(params.get("min_count", 10))]  # drop near-zero genes

    top_n = int(params["top_n"])
    normalization = str(params.get("normalization") or "deseq2").strip().lower()
    names, scores, engine = _bulk_deseq(sub, cond, reference, treatment, top_n, normalization)
    drop_note = f" · dropped {len(dropped)} sample(s) <{min_cells} cells" if dropped else ""
    subtitle = (
        f"pseudobulk · {engine} · {treatment} (n={n_treat}) vs {reference} (n={n_ref})"
        f"{label_note} · {sub.shape[0]} genes{drop_note}"
    )
    return _bar(names, scores, f"Pseudobulk DE — {treatment} vs {reference}", jsonable, subtitle)


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
    normalization = str(params.get("normalization") or "deseq2").strip().lower()
    names, scores, engine = _bulk_deseq(sub, cond, reference, treatment, top_n, normalization)
    subtitle = f"{engine} · {treatment} (n={n_treat}) vs {reference} (n={n_ref}) · {sub.shape[0]} genes tested"
    return _bar(names, scores, f"Top DE genes — {treatment} vs {reference}", jsonable, subtitle)


def deseq_results(sub, cond, reference, treatment, normalization="deseq2"):
    """pyDESeq2 Wald (treatment vs reference) on a raw-count frame (rows = features,
    columns = samples). Returns ``(results_df, engine label)`` — the FULL results frame
    (log2FoldChange, padj, ...). Raises ``ImportError`` when pyDESeq2 is unavailable so
    callers can choose their own light fallback.

    ``normalization``: ``deseq2`` (median-of-ratios) or ``tmm`` — edgeR-identical TMM size
    factors (via rnanorm, Apache-2.0) injected into the otherwise-standard pyDESeq2 fit, to
    match an edgeR/limma-voom reference pipeline. The *test* stays DESeq2's Wald; only the
    normalization changes. Shared by the bulk/pseudobulk DE path and differential abundance.
    """
    import pandas as pd
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.ds import DeseqStats

    metadata = pd.DataFrame({"condition": cond}, index=sub.columns)
    dds = DeseqDataSet(
        counts=sub.T, metadata=metadata, design="~condition", ref_level=["condition", reference], quiet=True
    )
    engine = "pyDESeq2 (Wald)"
    if normalization == "tmm":
        try:
            _fit_deseq_with_tmm(dds, sub)
            engine = "pyDESeq2 (Wald, TMM norm)"
        except Exception:
            dds.deseq2()  # rnanorm absent / API drift → fall back to median-of-ratios
            engine = "pyDESeq2 (Wald, TMM unavailable)"
    else:
        dds.deseq2()
    stat = DeseqStats(dds, contrast=["condition", treatment, reference], quiet=True)
    stat.summary()
    return stat.results_df, engine


def _bulk_deseq(sub, cond, reference, treatment, top_n, normalization="deseq2"):
    """Top-N DE genes by |log2FC| via :func:`deseq_results`; CPM-log2FC fallback if pyDESeq2
    is absent. Returns (gene names, signed log2FC scores, engine label)."""
    import numpy as np

    try:
        res, engine = deseq_results(sub, cond, reference, treatment, normalization)
        res = res.dropna(subset=["log2FoldChange", "padj"])
        res = res.reindex(res["log2FoldChange"].abs().sort_values(ascending=False).index).head(top_n)
        return [str(g) for g in res.index], [float(v) for v in res["log2FoldChange"]], engine
    except ImportError:
        # Light fallback when pyDESeq2 isn't installed: log2FC of mean CPM per group.
        cpm = sub.div(sub.sum(axis=0), axis=1) * 1e6
        a = cpm.loc[:, [c == reference for c in cond]].mean(axis=1)
        b = cpm.loc[:, [c == treatment for c in cond]].mean(axis=1)
        lfc = np.log2((b + 1.0) / (a + 1.0))
        lfc = lfc.reindex(lfc.abs().sort_values(ascending=False).index).head(top_n)
        return [str(g) for g in lfc.index], [float(v) for v in lfc], "CPM log2FC (pyDESeq2 absent)"


def tmm_size_factors(counts_genes_x_samples):
    """edgeR-identical TMM size factors (geomean 1) for a genes x samples count frame.

    rnanorm (Apache-2.0) computes the per-sample TMM normalization factor; the DESeq2 size
    factor is the *effective* library size (lib_size x norm_factor) rescaled to geometric
    mean 1 — so swapping these into pyDESeq2 reproduces edgeR/limma-voom's TMM normalization.
    """
    import numpy as np
    from rnanorm import TMM

    x = counts_genes_x_samples.T.to_numpy(dtype=float)  # rnanorm wants samples x genes
    nf = np.asarray(TMM().fit(x).get_norm_factors(x), dtype=float)
    eff = x.sum(axis=1) * nf                              # effective library size per sample
    return eff / np.exp(np.mean(np.log(eff)))            # rescale to geometric mean 1


def _fit_deseq_with_tmm(dds, sub):
    """Run the standard pyDESeq2 pipeline but with TMM size factors swapped in.

    Lets pyDESeq2 populate its internal state via ``fit_size_factors()``, overwrites the size
    factors + normalized counts with the TMM values, then runs the remaining deseq2() steps
    (dispersions -> LFC -> Cooks). Only the normalization differs from a vanilla ``deseq2()``.
    """
    import numpy as np

    sf = tmm_size_factors(sub)
    dds.fit_size_factors()  # populate logmeans / filtered_genes / internal state first
    dds.obs["size_factors"] = sf
    counts = dds.X.toarray() if not isinstance(dds.X, np.ndarray) else dds.X
    dds.layers["normed_counts"] = counts / sf[:, None]
    dds.var["_normed_means"] = dds.layers["normed_counts"].mean(axis=0)
    dds.fit_genewise_dispersions()
    dds.fit_dispersion_trend()
    dds.fit_dispersion_prior()
    dds.fit_MAP_dispersions()
    dds.fit_LFC()
    dds.calculate_cooks()
    if dds.refit_cooks:
        dds.refit()
    dds.cooks_outlier()


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
