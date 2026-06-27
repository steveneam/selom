"""Engine spine — frame-schema validation at the stage seams (D2).

The run path is a pipeline of stages — **ingest → clean → skill** — each handing a frame to the
next. D1 (:mod:`engine.compat`) gates the *semantic* contract at the skill seam: does the dropped
data carry the right **modality / named columns** for this skill (presence → a 422 before the
runner). D2 adds the layer below it: once the required columns are *present*, are they actually
**usable** — non-empty, and numeric where a number is needed? A column that is present by name but
all-empty (or all-text) passes D1's presence check and slips into the runner, where it becomes a
silently-degenerate figure (an all-NaN volcano) or a downstream crash. D2 catches that malformed
handoff **at the seam** with a clear 400, mirroring the runner's own ``ValueError → 400`` path.

The three layers are distinct, one source of truth each:

* **QC** (:mod:`engine.qc`) — *is the data clean?* (coarse, whole-frame: empty / negative counts / …).
* **D1** (:mod:`engine.compat`) — *are the named columns/modality this skill needs present?* (→ 422).
* **D2** (this module) — *do those present, required columns carry usable data?* (→ 400).

Honest by the same load-bearing rule as D1/the matcher: D2 only flags a **positively-determined**
structural defect (a required column that is *certainly* unusable). It never inspects columns D1
hasn't already confirmed present (a missing group is D1's 422, not a D2 false-block), and it is
overridable (``override=true``). Dependency-free — a lightweight, ``lazy``-style collector (every
violation reported at once), not a new venv dependency on the EDR-fragile hand-sewn venv (the C1
"no diskcache" precedent + [[selom-uv-sync-footgun]]).

The per-skill column rules are **derived from D1's** ``compat._SCHEMA`` (and the classifier synonym
sets in :mod:`engine.databundle`) so the column vocabulary stays single-sourced: D1 reads a group's
*presence*, D2 reads the *usability* of the same resolved column. See
``docs/architecture-consistency-gate/frame-validation.md``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from engine.compat import _SCHEMA
from engine.databundle import _LOGFC, _PVAL, _is_dataframe

# Named stages a frame crosses (the seams). The skill-input seam is enforced now; the result seam
# is a declared schema guarded by a test (a future endpoint can enforce it too).
STAGE_SKILL_INPUT = "skill_input"
STAGE_RESULT = "result"

# Which D1 column groups carry *numbers* (their resolved column must parse as numeric): the
# fold-change and significance groups. Derived from the classifier synonym sets so the vocabulary is
# single-sourced — a gene/label group (e.g. ``compat._GENE_G``) is exempt from the numeric check.
_NUMERIC_SYNONYM_SETS = (_LOGFC, _PVAL)


class FrameViolation(BaseModel):
    """One positively-determined structural defect at a stage seam — the wire shape the 400 carries.

    ``stage`` = which seam (``skill_input`` / ``result``); ``column`` = the offending column (empty
    for a whole-frame defect); ``code`` = the machine reason; ``message`` = the human, actionable why.
    """

    stage: str = STAGE_SKILL_INPUT
    column: str = ""
    code: str = ""           # empty_column | non_numeric_column | duplicate_column | ragged_row | …
    message: str = ""


def _is_numeric_group(synonyms: tuple[str, ...]) -> bool:
    return synonyms in _NUMERIC_SYNONYM_SETS


def _resolve(df: Any, synonyms: tuple[str, ...]) -> list[str]:
    """Every column name whose lower-cased form contains any synonym (the same match D1 uses)."""
    return [c for c in df.columns if any(s in str(c).strip().lower() for s in synonyms)]


def _is_all_empty(series: Any) -> bool:
    """True when the column carries no usable value: every cell null, or (a text column) every
    non-null cell blank/whitespace. A column with at least one real value is never 'empty'."""
    try:
        if bool(series.isna().all()):
            return True
        if getattr(getattr(series, "dtype", None), "kind", "") == "O":  # text/object column
            nonnull = series.dropna().astype(str).str.strip()
            return bool(len(nonnull)) and bool((nonnull == "").all())
    except Exception:  # noqa: BLE001 — a check we can't run is not a positive defect (stay honest)
        return False
    return False


def _has_finite_numeric(series: Any) -> bool:
    """True when at least one cell parses to a finite number — so a column the runner can coerce
    (e.g. numbers stored as strings) is *not* flagged; only an all-unparseable column is."""
    import numpy as np
    import pandas as pd

    try:
        arr = pd.to_numeric(series, errors="coerce").to_numpy(dtype="float64")
        return bool(np.isfinite(arr).any())
    except Exception:  # noqa: BLE001 — uncheckable → not a positive defect
        return True


def check_skill_input(skill_id: str, payload: Any, *, lazy: bool = True) -> list[FrameViolation]:
    """Validate the frame ``skill_id`` is about to consume, at the ingest/clean→skill seam.

    Returns the structural defects among the columns this skill's D1 contract *requires* — each
    required column must be present-and-usable (non-empty; numeric where a number is needed). Returns
    ``[]`` for a skill with no column contract, a non-table payload (an AnnData matrix is checked by
    QC + the modality gate, not here), or a well-formed frame. ``lazy`` collects every violation (the
    default — one 400 lists them all); ``lazy=False`` stops at the first.

    Only columns D1 has already confirmed present are inspected — a *missing* group is D1's 422, so
    D2 never double-reports it (and never false-blocks on absence). The check is best-effort: any
    column it cannot evaluate is left alone (honest — never a guessed block).
    """
    contract = _SCHEMA.get(skill_id)
    if contract is None or not _is_dataframe(payload):
        return []
    groups, _needs_numeric = contract
    violations: list[FrameViolation] = []
    for label, synonyms in groups:
        matched = _resolve(payload, synonyms)
        if not matched:
            continue  # absent → D1's job (422), not D2's
        col = matched[0]
        selected = payload[col]
        # A duplicate column name selects a DataFrame, not a Series — the runner's single-column
        # read then mis-shapes downstream. Flag it; the per-cell checks can't run on a 2-D select.
        if getattr(selected, "ndim", 1) > 1:
            violations.append(FrameViolation(
                stage=STAGE_SKILL_INPUT, column=str(col), code="duplicate_column",
                message=f"{label} ('{col}') appears more than once — rename the duplicates so a "
                        f"single {label} can be read."))
        elif _is_all_empty(selected):
            violations.append(FrameViolation(
                stage=STAGE_SKILL_INPUT, column=str(col), code="empty_column",
                message=f"{label} ('{col}') is empty — every value is missing. Check the file parsed "
                        f"correctly (delimiter / header), or swap in a complete table."))
        elif _is_numeric_group(synonyms) and not _has_finite_numeric(selected):
            violations.append(FrameViolation(
                stage=STAGE_SKILL_INPUT, column=str(col), code="non_numeric_column",
                message=f"{label} ('{col}') has no numeric values — {skill_id} needs numbers there. "
                        f"Check this is the right column, not a label or note."))
        if violations and not lazy:
            break
    return violations


def validate_result_table(table: Any, *, skill_id: str = "") -> list[FrameViolation]:
    """Validate a skill's Statistics-table output (the result seam): a well-formed ``StatsTable`` has
    a non-empty ``columns`` list and rectangular ``rows`` (each row as wide as ``columns``). Returns
    the defects (``[]`` for ``None`` — a purely-visual skill attaches no table, which is valid).

    A named schema for the output seam, guarded by a test over the native-table skills — the ratchet
    that keeps a runner from shipping a ragged table the FE Statistics node would choke on.
    """
    if table is None:
        return []
    if not isinstance(table, dict):
        return [FrameViolation(stage=STAGE_RESULT, code="not_a_table",
                               message=f"{skill_id or 'skill'} returned a non-dict table.")]
    cols = table.get("columns")
    if not isinstance(cols, list) or not cols:
        return [FrameViolation(stage=STAGE_RESULT, code="no_columns",
                               message=f"{skill_id or 'skill'} table has no columns.")]
    width = len(cols)
    violations: list[FrameViolation] = []
    for i, row in enumerate(table.get("rows", []) or []):
        if not isinstance(row, (list, tuple)) or len(row) != width:
            got = len(row) if isinstance(row, (list, tuple)) else "non-list"
            violations.append(FrameViolation(
                stage=STAGE_RESULT, code="ragged_row",
                message=f"row {i} has {got} cells, expected {width} (one per column)."))
    return violations


def frame_validation_message(violations: list[FrameViolation], skill_id: str = "") -> str:
    """A clear, actionable 400 message for a seam block — frames the collected defects with a next
    step, in the same voice as D1's :func:`engine.compat.contract_message`."""
    reasons = "; ".join(v.message for v in violations) or "the data handed to it is malformed"
    head = f"This data can't be analyzed by {skill_id}: " if skill_id else "This data is malformed: "
    return head + reasons
