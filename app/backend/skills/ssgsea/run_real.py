"""Real ssGSEA engine — per-sample pathway enrichment via gseapy.ssgsea (BSD-3).

Within each sample, genes are rank-normalized and a single-sample enrichment score (a
weighted KS-like statistic over the ranked list) is computed for every gene set,
yielding a normalized enrichment score (NES) per sample x gene set. With no explicit
``gene_set`` the skill scores the chosen ``gene_sets`` source (default GO;
``gene_sets/library.py``) — never MSigDB (DECISIONS #9, corrected: gseapy itself is
BSD-3; only MSigDB's *data* was the constraint). The top ``top_n`` gene sets by
across-sample variance are drawn as a heatmap (row z-scored by default so the diverging
scale is meaningful); the full per-sample NES rides the Statistics table. Shares the
heatmap spec with the stub via ``run.ssgsea_spec``.
"""

import re

from skills.ssgsea.run import ssgsea_spec

_SOURCE_ALIASES = {"": "go", "go": "go", "wikipathways": "wikipathways", "wiki": "wikipathways",
                   "curated": "curated", "reference": "reference", "all": "all"}


def run(data_path: str, params: dict) -> dict:
    import gseapy as gp

    expr = _read_matrix(data_path)
    sets, _lib_mode = _resolve_sets(params, expr)
    ss = gp.ssgsea(
        data=expr,
        gene_sets={k: list(v) for k, v in sets.items()},
        min_size=max(1, int(params.get("min_size", 10))),
        max_size=max(2, int(params.get("max_size", 500))),
        weight=float(params.get("weight", 0.25)),
        permutation_num=None,   # deterministic NES, no permutation p-values
        no_plot=True, outdir=None, threads=4, seed=0, verbose=False,
    )
    return _assemble(ss.res2d, list(expr.columns), params)


# ---- inputs ------------------------------------------------------------------
def _read_matrix(data_path):
    """An expression matrix as genes (UPPER, deduped) x samples — numeric, NaN filled 0."""
    import pandas as pd

    df = pd.read_csv(data_path, index_col=0)
    df = df.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
    if df.shape[1] < 1:
        raise ValueError("ssgsea needs an expression matrix (genes x samples) with numeric sample columns")
    df.index = df.index.astype(str).str.upper()
    df = df[~df.index.duplicated(keep="first")].dropna(how="all")
    if df.empty:
        raise ValueError("ssgsea: no usable gene rows in the expression matrix")
    return df.fillna(0.0)


def _resolve_sets(params, expr):
    """The gene sets to score + whether this is library mode. An explicit ``gene_set``
    (pasted members) → single-set mode; otherwise the ``gene_sets`` source → library mode."""
    explicit = _parse_panel(params.get("gene_set", ""))
    if explicit:
        return {"gene set": sorted(explicit)}, False
    from gene_sets.library import load_collection

    token = _SOURCE_ALIASES.get(str(params.get("gene_sets", "go")).strip().lower(), "go")
    sets = load_collection(token)
    if not sets:
        raise ValueError(f"ssgsea: gene-set library '{token}' is empty or unavailable")
    return sets, True


# ---- figure assembly (pure; testable with a synthetic res2d) ------------------
def _assemble(res, sample_order, params):
    import numpy as np
    import pandas as pd

    from skills._plotly import jsonable
    from skills._table import table

    res = res.copy()
    res["NES"] = pd.to_numeric(res["NES"], errors="coerce")
    n_total = int(res["Term"].nunique())
    mat = res.pivot(index="Term", columns="Name", values="NES")
    cols = [c for c in sample_order if c in mat.columns] or list(mat.columns)
    mat = mat.reindex(columns=cols).dropna(how="all")
    if mat.empty:
        raise ValueError("ssgsea: no gene set produced a score (check gene symbols / set-size bounds)")
    mat = mat.fillna(0.0)

    top_n = max(1, int(params.get("top_n", 25)))
    order = mat.var(axis=1, ddof=0).sort_values(ascending=False).index  # most variable first
    mat = mat.loc[order[:top_n]]

    pathways = [str(t) for t in mat.index]
    samples = [str(c) for c in mat.columns]
    raw = mat.to_numpy(dtype=float)

    if _truthy(params.get("zscore", True)):
        z = _row_zscore(raw, np)
        score_label = "enrichment (z)"
    else:
        z = np.round(raw, 4)
        score_label = "NES"

    title = (
        f"ssGSEA — {n_total} gene set{'s' if n_total != 1 else ''} x {len(samples)} "
        f"samples (top {len(pathways)} by variance)"
    )
    stats = table(
        ["gene set", *samples],
        [[pathways[i], *[round(float(raw[i][j]), 3) for j in range(len(samples))]]
         for i in range(len(pathways))],
        f"ssGSEA NES — {len(pathways)} gene sets x {len(samples)} samples",
    )
    z_list = [[round(float(v), 4) for v in row] for row in np.asarray(z)]
    return jsonable(ssgsea_spec(z_list, samples, pathways, title, score_label, stats))


def _row_zscore(values, np):
    """Per-row (per-pathway) z-score across samples; zero-variance rows stay at 0."""
    values = np.asarray(values, dtype=float)
    mean = values.mean(axis=1, keepdims=True)
    std = values.std(axis=1, keepdims=True)
    std[std == 0] = 1.0
    return np.round((values - mean) / std, 4)


def _truthy(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _parse_panel(raw) -> set:
    return {tok.upper() for tok in re.split(r"[,\s]+", str(raw or "").strip()) if tok}
