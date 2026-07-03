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
from engine.vocab import DE_LOGFC_SYNONYMS, DE_PVAL_SYNONYMS, METABOLOMICS_TOKENS


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

# The DE / metabolomics column vocabulary is the single named engine primitive in ``engine.vocab``
# (imported here for classify + by columns/compat/frame_schema/qc; a drift-guard test fails if a
# second copy forks). These module-private aliases keep the historical import path
# ``engine.databundle._LOGFC`` / ``_PVAL`` / ``_METAB_TOKENS`` resolving to the SAME tuple objects,
# so identity-based lookups elsewhere (columns._ROLE_BY_SYNONYMS_ID, frame_schema._NUMERIC_SYNONYM_SETS)
# stay valid. A fold-change column + a p-value column => DE results (DESeq2/edgeR/Seurat).
_LOGFC = DE_LOGFC_SYNONYMS
_PVAL = DE_PVAL_SYNONYMS
_METAB_TOKENS = METABOLOMICS_TOKENS


def classify(payload: Any, *, hint: str | None = None, source: SourceRef | None = None,
             override: dict | None = None) -> str:
    """Best-effort modality for a loaded payload. ``hint`` (a caller-supplied ``Kind``) wins;
    otherwise dispatch by payload type, then by table signature. Returns a member of
    ``engine.models.ALL_KINDS`` — ``UNKNOWN`` when nothing matches (never raises).

    ``override`` is the optional user column-override (``{role: column}``, roles logFC/pval/gene —
    see :mod:`engine.columns`): a mapped, *existing* column counts as that role for DE detection, so a
    table whose fold-change/significance columns the synonym sets miss can still classify as
    ``de_results``. Override-only — a mapping to an absent column is ignored (never fabricated)."""
    if hint:
        return hint
    if _is_anndata(payload):
        return SC_COUNTS
    if _is_dataframe(payload):
        return _classify_frame(payload, override)
    return UNKNOWN


def _is_anndata(obj: Any) -> bool:
    """True if ``obj`` is an AnnData — matched by MRO name to avoid a hard anndata import."""
    return any(t.__name__ == "AnnData" for t in type(obj).__mro__)


def _is_dataframe(obj: Any) -> bool:
    return any(t.__name__ == "DataFrame" for t in type(obj).__mro__)


def _override_has(df: Any, override: dict | None, role: str) -> bool:
    """True when ``override`` maps ``role`` to a column the frame actually carries (override-only —
    a mapping to an absent column never fabricates the role). Inline here to keep
    :mod:`engine.databundle` free of an :mod:`engine.columns` import (columns imports databundle)."""
    if not override or not isinstance(override, dict):
        return False
    col = override.get(role)
    return bool(col) and col in set(str(c) for c in df.columns)


def _classify_frame(df: Any, override: dict | None = None) -> str:
    cols = [str(c).strip().lower() for c in df.columns]
    has_fc = _override_has(df, override, "logFC") or _has_any(cols, _LOGFC)
    has_pval = _override_has(df, override, "pval") or _has_any(cols, _PVAL)
    if has_fc and has_pval:
        return DE_RESULTS

    num = df.select_dtypes(include="number")
    if num.shape[1] == 0:
        return GENERIC_TABLE
    if _looks_metabolomic(df):
        return METABOLOMICS

    miss = _missing_fraction(num)
    integral = _is_integral(num)
    # WS2.8 — a real counts matrix with a dropped/failed sample arrives with one entirely-empty
    # column, pushing whole-frame missingness to ~1/n_samples (16.7% for 6 samples): enough to fail
    # the <2% counts gate and demote to generic_table, losing both counts routing AND QC's
    # ``all_nan_columns`` empty-sample warn (which only runs in the counts branch). Score the counts
    # gate over the columns that actually carry data — a fully-empty column is an *absent sample*, not
    # a scattered gap. Tight by design: only WHOLE-empty columns are excused, so scattered missingness
    # still reads as not-counts and a genuinely generic table is never misread as counts. QC then
    # surfaces the empty column (:func:`engine.qc._all_nan_column_flag`).
    populated = num.loc[:, ~_all_nan_columns_mask(num)]
    counts_miss = _missing_fraction(populated) if populated.shape[1] else 1.0
    if integral and populated.shape[1] and counts_miss < 0.02:
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


def _all_nan_columns_mask(num: Any) -> Any:
    """Boolean per-column mask (aligned with ``num.columns``) marking columns that are entirely NaN —
    a dropped/empty sample, as opposed to a scattered gap. Used by the counts gate (WS2.8) to score
    missingness over the populated columns only, and mirrors the column QC uses to warn on the same."""
    return num.isna().all(axis=0).to_numpy()


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
