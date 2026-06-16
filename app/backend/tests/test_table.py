"""Statistics-table contract (Pillar 1 — Decision D7).

A skill that computes a tabular result returns it as `table` alongside the figure
(`run_skill_with_table`); the figure itself stays a pure {data, layout} spec, so the
existing golden figures (taken via `run_skill`) are unchanged. Purely-visual skills
return no table (the FE omits the Statistics node, D3).
"""

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
