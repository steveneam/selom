"""Statistics-table contract (Pillar 1 — Decision D7).

A skill that computes a tabular result returns it as `table` alongside the figure
(`run_skill_with_table`); the figure itself stays a pure {data, layout} spec, so the
existing golden figures (taken via `run_skill`) are unchanged. Purely-visual skills
return no table (the FE omits the Statistics node, D3).
"""

import re

import pytest

from skills.contract import run_skill, run_skill_with_table

# The skills that attach TWO tables on a run with default params, and the reason each is allowed to.
# Everywhere else a second table is something the user asked for (`pairs=`), so it can surprise no
# consumer that did not opt in; these two are different in kind and the difference is declared
# rather than discovered (spec D4 ranks 3–4, decided question 1):
#
#   confusion — n, overall agreement and Cohen's κ (or the named refusal) are computed on EVERY run.
#   qq        — λ, its verdict and the test count likewise.
#
# Neither is gated by a knob, and both were already published on a default run — inside a title
# string, where nothing could read them. Gating the split on a param would invent a switch to
# protect a shape rather than a user.
UNCONDITIONAL_MULTI_TABLE = {"confusion", "qq"}


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


def test_g3_only_declared_skills_emit_a_list_on_DEFAULT_params():
    """Emitting two tables from a DEFAULT run is a decision, so it has to be written down.

    The original form of this guard asserted the list was empty, on the premise that a second table
    is always something the user ASKED for (`lollipop`/`boxplot` emit two once `pairs=` is set, and
    nothing changes for anyone who did not ask). Slice 5 breaks that premise on purpose and it is
    worth being precise about why: `confusion`'s κ and `qq`'s λ are computed on EVERY run — there is
    no knob gating them — so gating the table on a param would be inventing a switch to protect a
    shape rather than a user. The scalars were already published on a default run; the change is
    which home they are published from, not whether.

    So the assertion becomes exact in BOTH directions, the `API_ONLY_KNOBS` shape: a skill cannot
    start emitting a list unprompted without landing here, and one that stops has to leave the list.
    """
    from skills.registry import list_skill_ids

    listed = []
    for skill_id in list_skill_ids():
        try:
            _figure, table = run_skill_with_table(skill_id, "unused", {})
        except Exception:  # noqa: BLE001 — a stub that needs real data is not this test's subject
            continue
        if isinstance(table, list):
            listed.append(skill_id)
    assert sorted(listed) == sorted(UNCONDITIONAL_MULTI_TABLE), (
        f"default-run multi-table set drifted: new={sorted(set(listed) - UNCONDITIONAL_MULTI_TABLE)} "
        f"gone={sorted(UNCONDITIONAL_MULTI_TABLE - set(listed))}"
    )


@pytest.mark.parametrize("skill_id", sorted(UNCONDITIONAL_MULTI_TABLE))
def test_g3_a_declared_multi_table_skill_leads_with_its_DETAIL_table(skill_id):
    """⚑ The scalar table must never be first, and the reason is a live mis-read, not neatness.

    `extract.readers._read_generic` walks the tables in array order, and `_read_count` answers ANY
    count-shaped metric (`n_*`, `*_total`) from the FIRST table that has rows — falling back to
    `len(rows)` when the title carries no true total. A one-row scalar table in position 0 therefore
    answers "how many?" with **1**, at confidence 0.5, and that number can reach a reproducibility
    score. Reversing the array is enough to break this, which is what makes it a guard rather than
    a comment.
    """
    from extract.readers import read_metric

    _figure, tables = run_skill_with_table(skill_id, "unused", {})
    assert isinstance(tables, list) and len(tables) >= 2
    assert len(tables[-1]["rows"]) == 1, "the declared scalar table is the trailing one"
    reading = read_metric(skill_id, "n_total", None, tables)
    assert reading is not None and reading.value != 1, (
        f"{skill_id}: a count metric resolved to the scalar table's single row — the detail table "
        f"must lead (got {reading.value if reading else None})"
    )
    # ...and the same read against the REVERSED array is the wrong answer, so the order is doing
    # the work rather than the reader happening to be robust.
    flipped = read_metric(skill_id, "n_total", None, list(reversed(tables)))
    assert flipped is not None and flipped.value == 1


def test_qq_publishes_lambda_from_the_table_not_the_title():
    """λ is the reason the skill exists, so it has to be a value, not prose (spec D4 rank 4).

    Both halves again: present as a cell, and GONE from the points title. The verdict travels with
    it — "inflated" is the reading of the number, and separating the two is how a figure ends up
    captioned "calibrated" beside a λ of 2.1.
    """
    _figure, tables = run_skill_with_table("qq", "unused", {})
    points, inflation = tables
    assert inflation["columns"] == ["λ (genomic inflation)", "verdict", "tests"]
    assert inflation["rows"] == [[1.18, "inflated", 40]]
    assert "λ" not in points["title"], "the points table must not re-publish λ in its title"
    # The caveat is genuine prose and stays a title — it qualifies the number, it is not one.
    assert "assumes most features are null" in inflation["title"]


def test_qq_points_title_carries_the_true_test_total():
    """`top N of M` is the phrasing `extract.readers._title_total` parses, and using it is
    deliberate rather than incidental: before this split a count metric on a Q-Q resolved to the
    number of rows SHOWN (the top 15), which is a display cap being reported as a result."""
    from extract.readers import read_metric

    _figure, tables = run_skill_with_table("qq", "unused", {"top_n": 5})
    assert "top 5 of 40 tested" in tables[0]["title"]
    reading = read_metric("qq", "n_total", None, tables)
    assert reading is not None and reading.value == 40
