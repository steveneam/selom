"""Engine spine — "is-my-data-clean?" QC (P1, E3, step 3).

:func:`run_qc` inspects a :class:`~engine.databundle.DataBundle` and returns a
:class:`~engine.models.QCReport`: modality-aware, **honest** problem flags + stats. This is the
layer that earns the "for non-bioinformaticians" claim — a verdict the user *reads and can
override*, never a silent filter (E3; generalizes the reproduction "no silent caps" rule).

Severity (D-e5): ``block`` = misleading-analysis risk → warn + require an explicit override;
``warn`` = proceed with a caveat; ``info`` = annotate. No fabricated flags — we emit only what we
can determine from the payload, and skip honestly otherwise. See ``docs/engine-spine/spec.md`` Sec 5.
"""

from __future__ import annotations

from typing import Any

from engine.databundle import _PVAL, _is_anndata, _is_dataframe
from engine.models import (
    BULK_COUNTS,
    DE_RESULTS,
    GENERIC_TABLE,
    PROTEOMICS,
    QC_BLOCK,
    QC_INFO,
    QC_WARN,
    SC_COUNTS,
    UNKNOWN,
    QCFlag,
    QCReport,
)


def _flag(severity: str, code: str, message: str, fix: str = "") -> QCFlag:
    return QCFlag(severity=severity, code=code, message=message, fix=fix)


def _orientation_flag(n_rows: int, n_numeric_cols: int, feature_noun: str) -> QCFlag | None:
    """A count/intensity matrix is ``features × samples`` (tall): many feature rows, a handful of
    sample columns. Far more numeric columns than rows is a strong, low-false-positive sign the table
    was dropped transposed — a genes×samples matrix never has more sample columns than gene rows. A
    ``warn`` (not a hard block): running DE on a transposed matrix produces garbage, but the user can
    override if their wide shape is intentional."""
    if n_numeric_cols > n_rows and n_numeric_cols >= 12:
        return _flag(QC_WARN, "maybe_transposed",
                     f"{n_numeric_cols} numeric columns but only {n_rows} rows — the table may be "
                     f"transposed (samples as rows, {feature_noun} as columns).",
                     f"Analyses expect {feature_noun} as rows and samples as columns; "
                     f"transpose it if that's the case.")
    return None


def run_qc(bundle: Any) -> QCReport:
    """Inspect a ``DataBundle`` → a ``QCReport``. Pure: returns the report; the caller assigns
    ``bundle.qc = run_qc(bundle)``. ``ok`` is True only when no ``warn``/``block`` flag fired."""
    payload = bundle.payload
    if _is_anndata(payload):
        stats, flags = _qc_anndata(payload, bundle.kind)
    elif _is_dataframe(payload):
        stats, flags = _qc_frame(payload, bundle.kind)
    else:
        stats, flags = {}, [
            _flag(QC_BLOCK, "unloadable", "No tabular/matrix payload to check.",
                  "Provide a matrix or table (.h5ad / .csv / .xlsx).")
        ]
    ok = not any(f.severity in (QC_WARN, QC_BLOCK) for f in flags)
    return QCReport(ran=True, ok=ok, flags=flags, stats=stats)


# --- table payloads ---------------------------------------------------------------------

def _qc_frame(df: Any, kind: str) -> tuple[dict, list[QCFlag]]:
    import numpy as np

    flags: list[QCFlag] = []
    n_rows, n_cols = df.shape
    num = df.select_dtypes(include="number")
    stats = {"n_rows": int(n_rows), "n_cols": int(n_cols), "n_numeric_cols": int(num.shape[1])}

    if n_rows == 0 or num.shape[1] == 0:
        flags.append(_flag(QC_BLOCK, "empty", "No numeric data to analyze.",
                           "Check the file parsed correctly (delimiter / header / sheet)."))
        return stats, flags

    arr = num.to_numpy(dtype="float64", na_value=np.nan)
    miss = float(np.isnan(arr).mean())
    finite = arr[np.isfinite(arr)]
    stats["missing_fraction"] = round(miss, 4)

    if kind == BULK_COUNTS:
        if finite.size and (finite < 0).any():
            flags.append(_flag(QC_BLOCK, "negative_counts",
                               "Negative values where raw counts are expected.",
                               "This looks log/normalized, not raw counts — deg/pseudobulk need raw integers."))
        elif finite.size and not np.all(finite == np.round(finite)):
            flags.append(_flag(QC_BLOCK, "non_integer_counts",
                               "Non-integer values where raw counts are expected.",
                               "Provide the raw integer count matrix (this looks already normalized)."))
        n_zero = int((np.nansum(arr, axis=1) == 0).sum())
        if n_zero:
            flags.append(_flag(QC_INFO, "all_zero_features",
                               f"{n_zero} feature(s) are all-zero.", "They will be dropped before analysis."))
        if num.shape[1] < 2:
            flags.append(_flag(QC_WARN, "too_few_samples",
                               "Only one sample column — most analyses need ≥2 per group.",
                               "Add the other samples / a design with replicates."))
        orient = _orientation_flag(n_rows, num.shape[1], "genes")
        if orient is not None:
            flags.append(orient)

    elif kind == PROTEOMICS:
        orient = _orientation_flag(n_rows, num.shape[1], "proteins")
        if orient is not None:
            flags.append(orient)
        n_all_missing = int(np.isnan(arr).all(axis=1).sum())
        if n_all_missing:
            flags.append(_flag(QC_WARN, "all_missing_rows",
                               f"{n_all_missing} protein(s) never detected (all-missing).",
                               "Drop them or impute (proteomics_de missing=minprob/mindet)."))
        if miss >= 0.5:
            flags.append(_flag(QC_WARN, "high_missingness",
                               f"{miss:.0%} of values are missing.",
                               "Use MNAR-aware imputation (proteomics_de missing=minprob/mindet)."))
        elif miss > 0:
            flags.append(_flag(QC_INFO, "missingness", f"{miss:.0%} of values are missing.", ""))

    elif kind == DE_RESULTS:
        flags += _qc_de_columns(df, np)

    elif kind in (GENERIC_TABLE, UNKNOWN):
        flags.append(_flag(QC_INFO, "unclassified",
                           "Modality not recognized — the table is still usable.",
                           "Routing will propose the analyses that fit its shape."))

    return stats, flags


def _qc_de_columns(df: Any, np: Any) -> list[QCFlag]:
    flags: list[QCFlag] = []
    lower = {str(c).strip().lower(): c for c in df.columns}
    pcol = next((orig for low, orig in lower.items() if low in _PVAL), None)
    if pcol is not None:
        p = df[pcol].to_numpy(dtype="float64", na_value=np.nan)
        finite = p[np.isfinite(p)]
        if finite.size and (finite.min() < 0 or finite.max() > 1):
            flags.append(_flag(QC_WARN, "pvalue_out_of_range",
                               f"'{pcol}' has values outside [0, 1].",
                               "Check this is a p-value column, not a score."))
        n_nan = int(np.isnan(p).sum())
        if n_nan:
            flags.append(_flag(QC_INFO, "nan_pvalues",
                               f"{n_nan} gene(s) have NaN in '{pcol}'.",
                               "Usually independent-filtered by the DE test — expected."))
    return flags


# --- AnnData payloads -------------------------------------------------------------------

def _qc_anndata(adata: Any, kind: str) -> tuple[dict, list[QCFlag]]:
    import numpy as np
    from scipy.sparse import issparse

    flags: list[QCFlag] = []
    stats = {"n_cells": int(adata.n_obs), "n_genes": int(adata.n_vars)}
    X = adata.X
    if issparse(X):
        vals = X.data
        libsize = np.asarray(X.sum(axis=1)).ravel()
    else:
        dense = np.asarray(X, dtype="float64")
        vals = dense.ravel()
        libsize = dense.sum(axis=1)

    finite = vals[np.isfinite(vals)] if vals.size else vals
    if kind == SC_COUNTS and finite.size:
        if (finite < 0).any():
            flags.append(_flag(QC_BLOCK, "negative_counts",
                               "Negative values in X where raw counts are expected.",
                               "Provide raw counts (a normalized matrix can't feed count-based skills)."))
        elif not np.all(finite == np.round(finite)):
            flags.append(_flag(QC_WARN, "not_raw_counts",
                               "X is not raw integer counts (looks normalized).",
                               "Keep raw counts in .layers['counts'] / .raw for count-based skills."))

    n_empty = int((libsize == 0).sum())
    if n_empty:
        flags.append(_flag(QC_WARN, "empty_cells",
                           f"{n_empty} cell(s) have zero total counts.",
                           "Filter empty droplets (normalization_qc filter=true)."))

    mito_mask = np.array([str(n).upper().startswith("MT-") for n in adata.var_names])
    if mito_mask.any() and float(libsize.sum()) > 0:
        if issparse(X):
            mito = np.asarray(X[:, mito_mask].sum(axis=1)).ravel()
        else:
            mito = dense[:, mito_mask].sum(axis=1)
        pct = 100.0 * mito / np.clip(libsize, 1, None)
        med = float(np.median(pct))
        stats["median_pct_mito"] = round(med, 2)
        if med > 20.0:
            flags.append(_flag(QC_WARN, "high_mito",
                               f"Median mitochondrial fraction is {med:.1f}% (>20%).",
                               "Filter low-quality / dying cells (normalization_qc)."))

    return stats, flags
