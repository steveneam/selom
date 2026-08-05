"""Statistics-table contract (Pillar 1 — Decision D7).

A skill that computes a tabular result returns it as `table` alongside the figure
(`run_skill_with_table`); the figure itself stays a pure {data, layout} spec, so the
existing golden figures (taken via `run_skill`) are unchanged. Purely-visual skills
return no table (the FE omits the Statistics node, D3).
"""

import re

import pytest

from skills.contract import run_skill, run_skill_with_table


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    # Pin the deterministic stub engine (like the golden tests), so the table contract
    # is exercised without a data fixture, regardless of which heavy deps are installed.
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def _valid(tbl):
    assert isinstance(tbl, dict), "expected a StatsTable dict"
    assert isinstance(tbl["columns"], list) and tbl["columns"]
    assert isinstance(tbl["rows"], list) and tbl["rows"]
    width = len(tbl["columns"])
    assert all(len(r) == width for r in tbl["rows"]), "every row matches the column count"


def test_volcano_emits_de_table():
    figure, table = run_skill_with_table("volcano", "unused", {})
    _valid(table)
    assert table["columns"][:3] == ["gene", "log2FC", "padj"]
    assert "table" not in figure  # popped — the Plotly spec the editor renders stays pure


def test_enrichment_emits_table():
    _, table = run_skill_with_table("enrichment", "unused", {})
    _valid(table)
    assert table["columns"][0] == "pathway"


def test_deg_emits_table():
    _, table = run_skill_with_table("deg", "unused", {})
    _valid(table)
    assert table["columns"][0] == "gene"


def test_visual_skill_has_no_table():
    _, table = run_skill_with_table("pca", "unused", {})
    assert table is None


def test_run_skill_drops_the_table():
    # The figure path (golden tests, the editor) never sees the table key.
    figure = run_skill("volcano", "unused", {})
    assert "table" not in figure


# --- the multi-table union (docs/stats-tables/spec.md D1) ----------------------


def test_as_tables_maps_the_three_wire_cases():
    """The ONE narrowing site on this side. `[]` for None is load-bearing far from here — the L3
    synthesis gate in `extract.readers.read_metric` decides a reproducibility score on it."""
    from skills._table import as_tables

    t1 = {"columns": ["a"], "rows": [[1]]}
    t2 = {"columns": ["b"], "rows": [[2]]}
    assert as_tables(None) == []
    assert as_tables(t1) == [t1]
    assert as_tables([t1, t2]) == [t1, t2]
    assert as_tables([]) == []
    assert as_tables([t1, t2]) is not None


def test_as_tables_is_the_only_backend_narrowing_site():
    """G2 backend twin — the union must not sprout `isinstance(table, list)` at every call site.

    D1's known failure mode arrives one call site at a time, not all at once, so the guard is
    structural rather than a convention. Scoped to the whole backend package; `skills/_table.py` is
    the declared home and tests may exercise the union directly."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    home = root / "skills" / "_table.py"
    skip_dirs = {".venv", "__pycache__", "alembic", "tests", ".pytest_cache"}
    # `isinstance(<something table-ish>, list)` — the inline three-case narrow, however spelled.
    pattern = re.compile(r"isinstance\(\s*[\w.\[\]\"']*\b(?:table|tables|tbl|table_stats)\b[\w.\[\]\"']*\s*,\s*list\s*\)",
                         re.I)
    offenders = []
    for py in root.rglob("*.py"):
        if any(part in skip_dirs for part in py.relative_to(root).parts):
            continue
        if py == home:
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{py.relative_to(root)}:{i}")
    assert offenders == [], f"narrow the StatsTable union in skills/_table.as_tables, not inline: {offenders}"


def test_as_tables_is_declared_exactly_once():
    """The other half: a SECOND normalizer spelling the three cases slightly differently is the same
    defect wearing the right name."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    decls = [str(p.relative_to(root)) for p in root.rglob("*.py")
             if ".venv" not in p.parts and "__pycache__" not in p.parts
             and re.search(r"^def as_tables\(", p.read_text(encoding="utf-8"), re.M)]
    assert decls == ["skills/_table.py"]


@pytest.mark.parametrize("skill_id", ["volcano", "enrichment", "deg"])
def test_g3_a_single_table_stays_a_bare_object_on_the_wire(skill_id):
    """G3 — the no-op claim, made executable. A one-table run must NOT become a one-element list:
    every persisted `table_stats` row and every existing consumer reads a bare object, and
    'uniformity' bought by wrapping would break all of them for nothing."""
    _figure, table = run_skill_with_table(skill_id, "unused", {})
    assert isinstance(table, dict), f"{skill_id} must still emit a bare StatsTable, not a list"


def test_g3_no_native_skill_has_started_emitting_a_list():
    """Slice 1 changes the contract, not a single runner. When slice 3 unsqueezes `lollipop` this
    test is the one that must be updated on purpose — which is the point: the migration is a no-op
    until someone deliberately makes it not one."""
    from skills.registry import list_skill_ids

    listed = []
    for skill_id in list_skill_ids():
        try:
            _figure, table = run_skill_with_table(skill_id, "unused", {})
        except Exception:  # noqa: BLE001 — a stub that needs real data is not this test's subject
            continue
        if isinstance(table, list):
            listed.append(skill_id)
    assert listed == []
