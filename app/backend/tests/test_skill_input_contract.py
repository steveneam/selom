"""D1 — declared skill INPUT-contract guard
(docs/architecture-consistency-gate/skill-input-contract.md).

The pre-run data-contract gate (POST /run, ``test_data_contract.py``) blocks a certain mismatch
before the skill runs, using the per-skill input contract declared in ``engine.compat``:

* ``_REQS``   — the payload **modality class** a skill needs (matrix vs table), and
* ``_SCHEMA`` — the named **column groups** a table-consuming skill needs (fold-change / p-value / …).

This guard keeps those declarations honest — every contracted skill must be a real shipped skill
(no drift), and a column contract must actually declare something — mirroring the OUTPUT
``skill-table-contract`` guard's "declared + mechanically guarded" philosophy. A skill renamed or
removed without updating the contract fails here, not silently at a user's run.
"""

from __future__ import annotations

from engine.compat import _REQS, _SCHEMA
from skills.registry import list_skill_ids


def test_input_contract_skills_all_ship():
    """Every skill named in the input contract is a real, currently-shipped skill — so a rename /
    removal can't leave a dangling (and therefore never-enforced) contract entry."""
    shipped = set(list_skill_ids())
    declared = set(_REQS) | set(_SCHEMA)
    stale = declared - shipped
    assert not stale, (
        f"engine.compat input contract references skill(s) that no longer ship: {sorted(stale)} — "
        f"update _REQS / _SCHEMA when a skill is renamed or removed."
    )


def test_schema_contracts_declare_something_checkable():
    """A column contract must declare a non-empty, checkable requirement (≥1 named group with
    synonyms, or a numeric-score requirement) — an empty contract would gate nothing yet read as
    'covered', the silent-gap the guard exists to prevent."""
    for skill_id, (groups, needs_numeric) in _SCHEMA.items():
        assert groups or needs_numeric, f"{skill_id} declares an empty column contract"
        for label, synonyms in groups:
            assert label, f"{skill_id} has a column group with no human label"
            assert synonyms, f"{skill_id} group {label!r} has no synonym substrings to match"


def test_schema_skills_are_table_consumers_not_matrix_only():
    """A column contract only makes sense for a table-consuming skill: if the skill also has a
    modality requirement, that requirement must admit a table class (not be matrix-only) — else the
    L2 class gate would block every input before the column check could ever run."""
    from engine.compat import _MATRIX_KINDS

    for skill_id in _SCHEMA:
        req = _REQS.get(skill_id)
        if req is None:
            continue  # no modality constraint → any loadable table reaches the column check
        assert any(k not in _MATRIX_KINDS for k in req), (
            f"{skill_id} has a column contract but a matrix-only modality requirement — the column "
            f"check is unreachable; relax _REQS[{skill_id!r}] to admit a table kind."
        )
