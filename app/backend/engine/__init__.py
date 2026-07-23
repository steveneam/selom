"""Engine spine — the product-agnostic core both Selom products call.

INGEST -> JOIN/MATCH -> ROUTE/GUIDE -> ANALYZE -> READ-BACK -> [GRADE] -> OUTPUT.
Own-data analysis = the spine minus grading; paper reproduction = the spine plus grading.
See ``docs/engine-spine/spec.md`` and ``docs/pillars/plan.md`` (P1-P4 = this spine).

P1 ships the entry: the canonical :class:`DataBundle` + the layered :func:`classify`.
Ingest registry (``engine.ingest``) and QC (``engine.qc``) follow.
"""

from __future__ import annotations

from engine.assemble import assemble_scrna
from engine.databundle import DataBundle, classify
from engine.cleaning import CleaningPlan, DataProfile, plan_cleaning, profile_data
from engine.ingest import clear_input_cache, ingest, ingest_cached, ingest_many
from engine.qc import run_qc
from engine.questionnaire import DesignHints, suggest_design_hints
from engine.recommend import ParamRec, ParamRecs, RecommendContext, recommend_params
from engine.route import route_data, route_profile
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
    "ingest_cached",
    "ingest_many",
    "assemble_scrna",
    "clear_input_cache",
    "run_qc",
    "route_data",
    "route_profile",
    "suggest_design_hints",
    "DesignHints",
    "recommend_params",
    "RecommendContext",
    "ParamRecs",
    "ParamRec",
    "plan_cleaning",
    "profile_data",
    "CleaningPlan",
    "DataProfile",
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
