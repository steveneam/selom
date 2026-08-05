"""D2 — frame-schema validation at the stage seams (engine.frame_schema).

Unit coverage for the declarative, dependency-free frame schema: the skill-input seam check (a
*present, required* column that is empty / all-text / duplicated is a positively-determined defect)
and the result-table seam schema (a rectangular StatsTable). The endpoint behaviour — a malformed
clean→skill handoff → a clear 400, not a stack trace — lives in ``test_frame_validation.py``.
"""

from __future__ import annotations

import pandas as pd
import pytest

from engine.frame_schema import (
    STAGE_RESULT,
    STAGE_SKILL_INPUT,
    _is_numeric_group,
    check_skill_input,
    frame_validation_message,
    validate_result_table,
)
from engine.databundle import _LOGFC, _PVAL

# A well-formed DE table — what volcano/enrichment read (fold-change + significance, both numeric).
_GOOD_DE = pd.DataFrame(
    {"gene": ["ACTB", "GAPDH", "B2M"],
     "log2FoldChange": [2.1, -1.4, 0.1],
     "padj": [0.001, 0.02, 0.9]}
)


def _codes(skill_id: str, df) -> list[str]:
    return [v.code for v in check_skill_input(skill_id, df)]


def test_good_de_table_has_no_violations():
    """The right, usable data is never flagged — D2 false-blocks nothing on a clean frame."""
    assert check_skill_input("volcano", _GOOD_DE) == []
    assert check_skill_input("enrichment", _GOOD_DE) == []


def test_empty_required_column_is_flagged():
    """A present-but-empty fold-change column (passes D1's presence check) is a determined defect —
    the silently-degenerate-figure case D2 exists to catch."""
    df = _GOOD_DE.assign(log2FoldChange=[None, None, None])
    viols = check_skill_input("volcano", df)
    assert len(viols) == 1
    assert viols[0].code == "empty_column"
    assert viols[0].column == "log2FoldChange"        # names the offending column
    assert viols[0].stage == STAGE_SKILL_INPUT
    assert "fold-change" in viols[0].message


def test_non_numeric_required_column_is_flagged():
    """A required numeric column whose values can't parse as numbers (all text) is flagged — but a
    column with at least one parseable number is not (the runner coerces it)."""
    bad = _GOOD_DE.assign(log2FoldChange=["NA", "n/a", "missing"])
    assert _codes("volcano", bad) == ["non_numeric_column"]
    # numbers stored as strings still parse → not flagged (honest, no false block).
    ok = _GOOD_DE.assign(log2FoldChange=["2.1", "-1.4", "0.1"])
    assert check_skill_input("volcano", ok) == []


def test_lazy_collects_every_defect_strict_stops_at_first():
    """``lazy`` (the default) lists every violation so one 400 names them all; ``lazy=False`` stops
    at the first."""
    both_bad = _GOOD_DE.assign(log2FoldChange=[None, None, None], padj=["x", "y", "z"])
    lazy = check_skill_input("volcano", both_bad, lazy=True)
    assert {v.code for v in lazy} == {"empty_column", "non_numeric_column"}
    assert len(check_skill_input("volcano", both_bad, lazy=False)) == 1


def test_duplicate_required_column_is_flagged():
    """A duplicated required column selects a 2-D frame, not a Series — the runner's single-column
    read then mis-shapes. Flagged so the user renames the duplicates."""
    df = pd.DataFrame([[1.0, 2.0, 0.01], [1.1, 2.2, 0.02]],
                      columns=["log2FoldChange", "log2FoldChange", "padj"])
    assert _codes("volcano", df) == ["duplicate_column"]


def test_uncontracted_skill_and_non_frame_are_not_checked():
    """A skill with no column contract (pca) and a non-DataFrame payload are out of scope — D2 only
    deepens D1's declared table contracts."""
    assert check_skill_input("pca", _GOOD_DE) == []
    assert check_skill_input("volcano", {"not": "a frame"}) == []
    assert check_skill_input("volcano", None) == []


def test_missing_column_is_left_to_d1_not_double_reported():
    """A *missing* required group is D1's 422 — D2 never re-flags an absent column (no false block,
    no duplication)."""
    no_fc = _GOOD_DE.drop(columns=["log2FoldChange"])
    assert check_skill_input("volcano", no_fc) == []


def test_numeric_group_derivation_is_single_sourced():
    """The fold-change / significance groups are numeric (their column must parse as a number); a
    gene/label group is not — derived from the classifier synonym sets, not re-declared."""
    assert _is_numeric_group(_LOGFC)
    assert _is_numeric_group(_PVAL)
    assert not _is_numeric_group(("gene", "symbol"))


def test_validate_result_table_accepts_rectangular_rejects_ragged():
    """The result-seam schema: a non-empty columns list + rows each as wide as the columns. ``None``
    (a purely-visual skill) is valid; a ragged / column-less / non-dict table is not."""
    good = {"columns": ["gene", "log2FC"], "rows": [["ACTB", 2.1], ["B2M", -1.0]]}
    assert validate_result_table(good) == []
    assert validate_result_table(None) == []
    ragged = validate_result_table({"columns": ["a", "b"], "rows": [["only-one"]]})
    assert [v.code for v in ragged] == ["ragged_row"]
    assert ragged[0].stage == STAGE_RESULT
    assert [v.code for v in validate_result_table({"columns": []})] == ["no_columns"]
    assert [v.code for v in validate_result_table("not a dict")] == ["not_a_table"]


def test_validate_result_table_validates_every_element_of_a_list():
    """G1 (docs/stats-tables/spec.md §6) — a runner may attach a LIST of tables, and a ragged table
    in position 2 must fail exactly as loudly as one in position 1. Without this the second table is
    the unguarded one, which is the whole failure mode a result-seam schema exists to stop."""
    good = {"columns": ["gene", "log2FC"], "rows": [["ACTB", 2.1]]}
    ragged = {"columns": ["a", "b"], "rows": [["only-one"]]}
    assert validate_result_table([]) == []
    assert validate_result_table([good, good]) == []

    second_bad = validate_result_table([good, ragged], skill_id="lollipop")
    assert [v.code for v in second_bad] == ["ragged_row"]
    assert second_bad[0].stage == STAGE_RESULT
    # ...and it says WHICH table, or a two-table failure reads as a one-table failure.
    assert "table 2" in second_bad[0].message

    # The same defect first or second — same code, only the position differs.
    first_bad = validate_result_table([ragged, good], skill_id="lollipop")
    assert [v.code for v in first_bad] == ["ragged_row"]
    assert "table 1" in first_bad[0].message
    # A non-dict element is caught too, not silently skipped.
    assert [v.code for v in validate_result_table([good, "not a dict"])] == ["not_a_table"]


def test_single_table_messages_carry_no_position_prefix():
    """G3's half of the result seam: one table is byte-identical to before — no `table 1:` prefix
    leaking into a message a user or a test reads."""
    bare = validate_result_table({"columns": ["a", "b"], "rows": [["only-one"]]})
    assert bare[0].message == "row 0 has 1 cells, expected 2 (one per column)."
    # A one-element LIST reads the same — the prefix is a disambiguator, not decoration.
    one_element = validate_result_table([{"columns": ["a", "b"], "rows": [["only-one"]]}])
    assert one_element[0].message == bare[0].message


def test_frame_validation_message_is_actionable():
    """The 400 message names the skill and folds in every defect's actionable reason."""
    df = _GOOD_DE.assign(log2FoldChange=[None, None, None])
    msg = frame_validation_message(check_skill_input("volcano", df), "volcano")
    assert "volcano" in msg and "fold-change" in msg


# --- the result-seam ratchet: every native-table skill emits a rectangular table ----------------

@pytest.fixture()
def _stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


# The stub-visible native-table skills (mirrors test_skill_table_contract.STUB_NATIVE) — those that
# attach a Statistics table from their stub with default params.
_STUB_NATIVE = ["volcano", "deg", "proteomics_de", "enrichment", "cepo",
                "erg_traces", "erg_bwave_bar", "erg_intensity_response", "erg_flicker"]


@pytest.mark.parametrize("skill_id", _STUB_NATIVE)
def test_native_result_tables_are_rectangular(skill_id, _stub):
    """Every native StatsTable validates against the result-seam schema — a runner can't ship a
    ragged/column-less table the FE Statistics node would choke on (the output-seam ratchet)."""
    from skills.contract import run_skill_with_table

    _figure, table = run_skill_with_table(skill_id, "unused", {})
    assert validate_result_table(table, skill_id=skill_id) == []
