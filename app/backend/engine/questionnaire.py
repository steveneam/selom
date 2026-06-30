"""Engine spine — deterministic DESIGN-hint detection for the intake questionnaire (Layer A ingest).

The intake questionnaire (`docs/intake-questionnaire/build-spec.md`) is a dynamic, layered confirm-card
the engine pre-fills with NO AI. ``/data/inspect`` already returns the *structure* layer (modality +
orientation via :mod:`engine.cleaning`, the routed analysis via :mod:`engine.route`, columns + numeric-col
count via :mod:`engine.compat`). This module adds the *design* layer it did not detect:

  * candidate group / condition columns,
  * the distinct condition levels per candidate,
  * the replicate count per level,
  * a control / reference keyword guess.

The detection **reuses the ``deg`` runner's own label logic** (the replicate-suffix regex + the
condition/sample obs aliases) so that what the questionnaire *detects* is exactly what the run will
*consume* — the confirmed answers map directly onto the ``deg`` params (``reference``/``treatment``/
``condition_col``/``sample_col``), which the runner already records in provenance ("AI compiles away" with
no AI). See ``docs/intake-questionnaire/build-spec.md`` §2.

Fail-soft (E4): any error returns an empty ``needs_design=False`` hint — never breaks ``/data/inspect``.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from engine.models import BULK_COUNTS, SC_COUNTS, UNKNOWN

# Control / reference keyword guess — the level a 2-group contrast should reference against. Word-ish
# so a short token (``WT``) matches without false-positiving inside a longer word; a trailing replicate
# index is stripped before matching (``ctrl1`` -> ``ctrl``) so the un-suffixed forms still hit.
_CONTROL_RE = re.compile(
    r"(?i)(?:\b(?:wt|ctrl|control|wild[\s_-]?type|vehicle|dmso|untreated|naive|baseline|mock|sham|"
    r"uninjected|scramble|scr|non[\s_-]?target|nontarget|parental)\b)"
    r"|(?:\b(?:0h|day[\s_-]?0|d0|t0|p0)\b)"
)

# Low-cardinality bounds for an scRNA obs column to count as a candidate condition (a contrast needs
# >=2 levels; >12 is a per-cell annotation / id, not a design factor).
_MIN_LEVELS = 2
_MAX_LEVELS = 12


class LevelHint(BaseModel):
    """One condition level + how many replicates carry it."""

    name: str
    n_replicates: int = 0       # bulk: sample columns at this level · scRNA: distinct sample ids (else cells)
    replicate_unit: str = "samples"   # "samples" (biological replicates) | "cells" (no sample col found)


class GroupCandidate(BaseModel):
    """A candidate design factor: a column (or the bulk header-inferred pseudo-column) + its levels."""

    key: str                    # an obs / design-sheet column name, OR the sentinel "__column_names__"
    label: str                  # human label ("genotype" / "sample columns")
    levels: list[LevelHint] = Field(default_factory=list)
    n_levels: int = 0
    reference_guess: str | None = None   # a control/reference level among `levels` (None if no match)


class DesignHints(BaseModel):
    """The deterministic design prefill for the intake questionnaire (Layer A ingest).

    ``needs_design`` is False for any input that carries no design to capture — an already-computed DE
    table (``de_results``), an unsupervised matrix, or a modality v1 doesn't cover — and the confirm-card
    then shows only the two structure chips. Serializable: rides ``/data/inspect`` as ``design``.
    """

    needs_design: bool = False
    source: str = "none"        # "column_names" | "obs" | "design_sheet" | "none"
    modality: str = UNKNOWN     # echoes bundle.kind for the FE
    group_candidates: list[GroupCandidate] = Field(default_factory=list)
    best_group: str | None = None       # key of the best candidate (pre-selects the group dropdown)
    sample_col: str | None = None       # scRNA: the detected biological-replicate column (deg sample_col)
    note: str = ""


_COLUMN_NAMES_KEY = "__column_names__"   # the sentinel "group" for bulk labels inferred from headers


def suggest_design_hints(bundle: Any, *, design_path: str | None = None) -> DesignHints:
    """Deterministically detect the experimental design of a classified ``DataBundle`` for the intake
    questionnaire. Fail-soft: any error yields an empty (``needs_design=False``) hint."""
    try:
        return _suggest(bundle, design_path)
    except Exception:  # noqa: BLE001 — a prefill helper must never break /data/inspect (E4)
        return DesignHints(needs_design=False, source="none",
                           modality=getattr(bundle, "kind", UNKNOWN))


def _suggest(bundle: Any, design_path: str | None) -> DesignHints:
    kind = getattr(bundle, "kind", UNKNOWN)
    # A design sheet, when one is already attached, is the source of truth (auto-join, never hand-match).
    if design_path:
        sheet = _design_sheet_candidate(design_path)
        if sheet is not None:
            return DesignHints(
                needs_design=sheet.n_levels >= _MIN_LEVELS, source="design_sheet", modality=kind,
                group_candidates=[sheet], best_group=sheet.key,
                note=f"read the design sheet → {sheet.n_levels} condition(s) on '{sheet.key}'")
    if kind == BULK_COUNTS:
        return _bulk_hints(bundle, kind)
    if kind == SC_COUNTS:
        return _scrna_hints(bundle, kind)
    # de_results (already computed), proteomics/metabolomics (v1 defers), generic/unknown → no design.
    return DesignHints(needs_design=False, source="none", modality=kind,
                       note="no experimental design to capture for this data type")


# --- bulk: condition labels inferred from the sample column names ------------------------------------

def _bulk_hints(bundle: Any, kind: str) -> DesignHints:
    df = getattr(bundle, "payload", None)
    if df is None or not _is_dataframe(df):
        return DesignHints(needs_design=False, source="none", modality=kind)
    # The numeric columns ARE the sample columns: a genes x samples count matrix is read with the
    # gene-id as a string first column (engine.ingest._load_csv, no index_col), so it drops out here.
    sample_cols = [str(c) for c in df.columns if _is_numeric_series(df[c])]
    if len(sample_cols) < _MIN_LEVELS:
        return DesignHints(needs_design=False, source="none", modality=kind,
                           note="not enough sample columns to form a contrast")
    rep_regex = _rep_regex()
    labels: dict[str, str] = {c: re.sub(rep_regex, "", c) for c in sample_cols}
    levels = _levels_from_labels(labels)
    if len(levels) < _MIN_LEVELS:
        return DesignHints(needs_design=False, source="none", modality=kind,
                           note="all sample columns map to one condition — no contrast")
    cand = GroupCandidate(
        key=_COLUMN_NAMES_KEY, label="sample columns",
        levels=[LevelHint(name=name, n_replicates=n, replicate_unit="samples") for name, n in levels],
        n_levels=len(levels), reference_guess=_guess_reference([name for name, _ in levels]))
    return DesignHints(
        needs_design=True, source="column_names", modality=kind,
        group_candidates=[cand], best_group=_COLUMN_NAMES_KEY,
        note=f"inferred {len(levels)} condition(s) from the sample column names")


# --- scRNA: candidate condition columns from obs ----------------------------------------------------

def _scrna_hints(bundle: Any, kind: str) -> DesignHints:
    adata = getattr(bundle, "payload", None)
    obs = getattr(adata, "obs", None)
    if obs is None or not _is_dataframe(obs) or obs.shape[1] == 0:
        return DesignHints(needs_design=False, source="none", modality=kind)
    cond_aliases, sample_aliases = _obs_aliases()
    obs_cols = [str(c) for c in obs.columns]
    sample_col = next((c for c in sample_aliases if c in obs_cols), None)
    # Candidate condition columns: the known aliases first (preserve their priority order), then any
    # other low-cardinality non-numeric obs column — deduped, never the sample column itself.
    ordered: list[str] = [c for c in cond_aliases if c in obs_cols]
    for c in obs_cols:
        if c == sample_col or c in ordered:
            continue
        if _is_categorical_series(obs[c]) and _MIN_LEVELS <= _nunique(obs[c]) <= _MAX_LEVELS:
            ordered.append(c)
    candidates = [_obs_candidate(obs, c, sample_col) for c in ordered]
    candidates = [c for c in candidates if c is not None and c.n_levels >= _MIN_LEVELS]
    if not candidates:
        return DesignHints(needs_design=False, source="none", modality=kind,
                           note="no low-cardinality condition column found in obs")
    # Best = the first alias hit if present, else the lowest-cardinality candidate (the tightest factor).
    alias_hit = next((c for c in candidates if c.key in cond_aliases), None)
    best = alias_hit or min(candidates, key=lambda c: c.n_levels)
    unit = "distinct samples" if sample_col else "cells (no sample column found)"
    return DesignHints(
        needs_design=True, source="obs", modality=kind,
        group_candidates=candidates, best_group=best.key, sample_col=sample_col,
        note=f"replicates counted as {unit}")


def _obs_candidate(obs: Any, col: str, sample_col: str | None) -> GroupCandidate | None:
    series = obs[col].astype(str)
    if sample_col is not None:
        # Biological replicates = distinct sample ids per condition level (cells are not replicates).
        grouped = obs.assign(_lvl=series)[[sample_col, "_lvl"]].astype(str)
        counts = grouped.groupby("_lvl")[sample_col].nunique()
        unit = "samples"
    else:
        counts = series.value_counts()
        unit = "cells"
    levels = [LevelHint(name=str(name), n_replicates=int(n), replicate_unit=unit)
              for name, n in counts.items()]
    levels.sort(key=lambda lv: lv.name)
    return GroupCandidate(
        key=col, label=col, levels=levels, n_levels=len(levels),
        reference_guess=_guess_reference([lv.name for lv in levels]))


# --- design sheet -----------------------------------------------------------------------------------

def _design_sheet_candidate(design_path: str) -> GroupCandidate | None:
    """Read an attached design sheet and pick its best group column (the lowest-cardinality non-id
    factor with 2..12 levels). Reuses the shared sheet loader so the id-column heuristic is identical."""
    from skills._design import load_design

    design = load_design({"_design_path": design_path})
    if design is None or design.shape[1] == 0:
        return None
    best: GroupCandidate | None = None
    for col in (str(c) for c in design.columns):
        series = design[col].astype(str)
        if not (_MIN_LEVELS <= series.nunique() <= _MAX_LEVELS):
            continue
        counts = series.value_counts()
        levels = sorted((LevelHint(name=str(name), n_replicates=int(n), replicate_unit="samples")
                         for name, n in counts.items()), key=lambda lv: lv.name)
        cand = GroupCandidate(key=col, label=col, levels=levels, n_levels=len(levels),
                              reference_guess=_guess_reference([lv.name for lv in levels]))
        if best is None or cand.n_levels < best.n_levels:
            best = cand
    return best


# --- helpers ----------------------------------------------------------------------------------------

def _levels_from_labels(labels: dict[str, str]) -> list[tuple[str, int]]:
    """Distinct condition labels in first-seen (deterministic) order + their sample count."""
    order: list[str] = []
    counts: dict[str, int] = {}
    for label in labels.values():
        if label not in counts:
            order.append(label)
        counts[label] = counts.get(label, 0) + 1
    return [(name, counts[name]) for name in order]


def _guess_reference(levels: list[str]) -> str | None:
    """The first level that reads like a control/reference (keyword or time-zero), else None."""
    for lvl in levels:
        probe = re.sub(r"[\s_\-]*\d+$", "", str(lvl)).strip()
        if _CONTROL_RE.search(str(lvl)) or (probe and _CONTROL_RE.search(probe)):
            return lvl
    return None


def _rep_regex() -> str:
    """The deg runner's trailing-replicate-suffix regex (reused so detection == the run's labelling)."""
    try:
        from skills.deg.run_real import DEFAULT_REP_REGEX

        return DEFAULT_REP_REGEX
    except Exception:  # noqa: BLE001 — keep working even if the skill module shifts
        return r"_\d+$"


def _obs_aliases() -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The deg runner's condition + sample obs aliases (reused so detection == the run's resolution)."""
    try:
        from skills.deg.run_real import _CONDITION_FALLBACKS, _SAMPLE_FALLBACKS

        return _CONDITION_FALLBACKS, _SAMPLE_FALLBACKS
    except Exception:  # noqa: BLE001
        return (
            ("condition", "Condition", "genotype", "group", "treatment", "disease", "status"),
            ("sample", "Sample", "sample_id", "donor", "orig.ident", "library", "batch"),
        )


def _is_dataframe(obj: Any) -> bool:
    return any(t.__name__ == "DataFrame" for t in type(obj).__mro__)


def _is_numeric_series(series: Any) -> bool:
    return getattr(getattr(series, "dtype", None), "kind", "") in "iuf"


def _is_categorical_series(series: Any) -> bool:
    """A low-cardinality factor column: not a continuous numeric (int/uint/float). Object, category,
    bool, and string dtypes all qualify as candidate design factors."""
    return getattr(getattr(series, "dtype", None), "kind", "") not in "iuf"


def _nunique(series: Any) -> int:
    try:
        return int(series.astype(str).nunique())
    except Exception:  # noqa: BLE001
        return 0
