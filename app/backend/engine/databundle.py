"""Engine spine — the canonical ``DataBundle`` + the layered modality classifier (P1, E1).

One in-memory representation for any tabular/omics input. It **wraps** the native loaded
object (AnnData stays AnnData, tables stay DataFrames — D-e1 wrap-don't-coerce) and carries
its modality (``kind``), provenance, design, and QC verdict.

:func:`classify` is the layered detector ([[layered-deterministic-extraction]]): L1 structured
(payload type + exact column signatures) -> L2 recovery (sniff column names / dtypes / missingness)
-> L3 ``GENERIC_TABLE`` (still usable) -> ``UNKNOWN``. ``kind`` therefore degrades gracefully and
never blocks ingest (E2). See ``docs/engine-spine/spec.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.models import (
    BULK_COUNTS,
    DE_RESULTS,
    GENERIC_TABLE,
    METABOLOMICS,
    PROTEOMICS,
    SC_COUNTS,
    UNKNOWN,
    Design,
    QCReport,
    SourceRef,
)


@dataclass
class DataBundle:
    """The product-agnostic data object. ``payload`` is the *loaded* object (never a path):
    ``AnnData`` | ``pandas.DataFrame`` | ``dict`` of frames. Both products call the spine over
    this; reproduction adds only the grade step."""

    payload: Any
    kind: str = UNKNOWN
    source: SourceRef = field(default_factory=SourceRef)
    design: Design | None = None
    qc: QCReport = field(default_factory=QCReport)
    meta: dict = field(default_factory=dict)
    # Runtime handle to the source file (set by :func:`engine.ingest.ingest`): the re-openable
    # path a still-path-based skill runs from — the ANALYZE entry (``run_bundle``) executes from
    # it. Distinct from ``source`` (the *serialized* provenance — filename/sha, not a path); this
    # field is not serialized (the wrapper is a dataclass, not pydantic). ``None`` when the bundle
    # was built in-memory rather than ingested from a file (E4). See ``docs/engine-spine/spec.md`` §9.
    path: str | None = None


# --- modality classification ------------------------------------------------------------

# A fold-change column + a p-value column => differential-expression results (DESeq2/edgeR/Seurat).
_LOGFC = ("log2foldchange", "logfoldchange", "logfc", "log2fc", "avg_log2fc", "log fold change")
_PVAL = ("padj", "pvalue", "p_val", "p.value", "pval", "adj.p.val", "fdr", "qvalue")
# Metabolomics feature labels (m/z or database tokens) — a conservative, honest signal.
_METAB_TOKENS = ("m/z", "hmdb", "metabolite", "kegg c")


def classify(payload: Any, *, hint: str | None = None, source: SourceRef | None = None) -> str:
    """Best-effort modality for a loaded payload. ``hint`` (a caller-supplied ``Kind``) wins;
    otherwise dispatch by payload type, then by table signature. Returns a member of
    ``engine.models.ALL_KINDS`` — ``UNKNOWN`` when nothing matches (never raises)."""
    if hint:
        return hint
    if _is_anndata(payload):
        return SC_COUNTS
    if _is_dataframe(payload):
        return _classify_frame(payload)
    return UNKNOWN


def _is_anndata(obj: Any) -> bool:
    """True if ``obj`` is an AnnData — matched by MRO name to avoid a hard anndata import."""
    return any(t.__name__ == "AnnData" for t in type(obj).__mro__)


def _is_dataframe(obj: Any) -> bool:
    return any(t.__name__ == "DataFrame" for t in type(obj).__mro__)


def _classify_frame(df: Any) -> str:
    cols = [str(c).strip().lower() for c in df.columns]
    if _has_any(cols, _LOGFC) and _has_any(cols, _PVAL):
        return DE_RESULTS

    num = df.select_dtypes(include="number")
    if num.shape[1] == 0:
        return GENERIC_TABLE
    if _looks_metabolomic(df):
        return METABOLOMICS

    miss = _missing_fraction(num)
    integral = _is_integral(num)
    if integral and miss < 0.02:
        return BULK_COUNTS
    if miss >= 0.05 and not integral:
        return PROTEOMICS
    return GENERIC_TABLE


def _has_any(cols: list[str], needles: tuple[str, ...]) -> bool:
    return any(any(n in c for n in needles) for c in cols)


def _missing_fraction(num: Any) -> float:
    if num.size == 0:
        return 0.0
    return float(num.isna().to_numpy().mean())


def _is_integral(num: Any) -> bool:
    """True if every finite value equals its rounded value (counts), ignoring NaN."""
    import numpy as np

    arr = num.to_numpy(dtype="float64", na_value=np.nan)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return False
    return bool(np.all(finite == np.round(finite)))


def _looks_metabolomic(df: Any) -> bool:
    """Conservative: feature labels (index or first column) that look like m/z values or
    carry metabolomics tokens. Honest about being weak — falls through to GENERIC otherwise."""
    import re

    labels = [str(x).lower() for x in list(df.index[:50])]
    # Include the first column as labels only when it is non-numeric (a name column) — a
    # numeric data column (e.g. proteomics intensities like 18.3456) must not read as m/z.
    if df.shape[1] and df.iloc[:, 0].dtype.kind not in "iufcb":
        labels += [str(x).lower() for x in df.iloc[:50, 0].tolist()]
    if any(any(tok in lab for tok in _METAB_TOKENS) for lab in labels):
        return True
    mz = re.compile(r"^\d{2,4}\.\d{3,}$")
    return sum(1 for lab in labels if mz.match(lab)) >= 5
