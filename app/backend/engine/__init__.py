"""Engine spine — the product-agnostic core both Selom products call.

INGEST -> JOIN/MATCH -> ROUTE/GUIDE -> ANALYZE -> READ-BACK -> [GRADE] -> OUTPUT.
Own-data analysis = the spine minus grading; paper reproduction = the spine plus grading.
See ``docs/engine-spine/spec.md`` and ``docs/pillars/plan.md`` (P1-P4 = this spine).

P1 ships the entry: the canonical :class:`DataBundle` + the layered :func:`classify`.
Ingest registry (``engine.ingest``) and QC (``engine.qc``) follow.
"""

from __future__ import annotations

from engine.databundle import DataBundle, classify
from engine.ingest import ingest
from engine.qc import run_qc
from engine.models import (
    ALL_KINDS,
    BULK_COUNTS,
    DE_RESULTS,
    GENERIC_TABLE,
    METABOLOMICS,
    SC_COUNTS,
    UNKNOWN,
    Design,
    QCFlag,
    QCReport,
    SourceRef,
)

__all__ = [
    "DataBundle",
    "classify",
    "ingest",
    "run_qc",
    "ALL_KINDS",
    "SC_COUNTS",
    "BULK_COUNTS",
    "DE_RESULTS",
    "GENERIC_TABLE",
    "METABOLOMICS",
    "UNKNOWN",
    "Design",
    "QCFlag",
    "QCReport",
    "SourceRef",
]
