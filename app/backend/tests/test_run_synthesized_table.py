"""L3 table synthesis on the own-data run path (docs/records/table-synthesis/spec.md §4 / §8 step 4).

A tableless skill that HAS a deterministic synthesizer gets a canonical Statistics table re-shaped
from its OWN figure on ``POST /skills/{id}/run`` — tagged ``synthesized: True`` — so the FE
Statistics node renders for purely-visual skills. A native-table skill is left untouched (never
re-tagged), and a skill with no synthesizer stays tableless (-> L4 Pro-AI, never fabricated). This
is the cross-lane backend half of the L3 FE Statistics-node wiring; symmetric with the reproduction
reader, which attaches the same synthesis when a native table is absent. Stub engine.
"""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

# Clean integer counts (>=2 samples, no all-zero rows) -> classifies + passes QC, so the run is not
# blocked and we exercise the real bundle path through engine.ingest.
_CLEAN = b"gene,s0,s1,s2,s3\n" + b"".join(
    f"g{i},{i + 1},{i + 2},{i + 3},{i + 4}\n".encode() for i in range(10)
)


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def test_tableless_skill_gets_a_synthesized_table():
    # pca attaches no native table; its synthesizer reshapes the PC axis titles -> [component, %].
    r = client.post("/skills/pca/run", files={"matrix": ("counts.csv", _CLEAN, "text/csv")})
    assert r.status_code == 200
    tbl = r.json()["table"]
    assert tbl is not None
    assert tbl["synthesized"] is True
    assert tbl["columns"][0] == "component"          # [component, variance %]
    assert tbl["rows"]                                # PC1/PC2 rows read from the axis titles


def test_native_table_skill_is_not_overwritten():
    # deg attaches its own native table -> the synthesis branch never runs, so it stays untagged.
    r = client.post("/skills/deg/run", files={"matrix": ("counts.csv", _CLEAN, "text/csv")})
    assert r.status_code == 200
    tbl = r.json()["table"]
    assert tbl is not None
    assert not tbl.get("synthesized")


def test_skill_with_no_synthesizer_stays_tableless():
    # go_graph is L4-only (node-link) — no native table, no synthesizer -> table is honestly None.
    r = client.post("/skills/go_graph/run", files={"matrix": ("counts.csv", _CLEAN, "text/csv")})
    assert r.status_code == 200
    assert r.json()["table"] is None


# --- ALSO_SYNTHESIZE: a native table AND its L3 summary on the SAME run (stats-tables D3) --------
#
# ⚑ This branch shipped in slice 4 with NO gated consumer. Deleting `or skill_id in
# ALSO_SYNTHESIZE` from `routers/_run.py` left 1672 tests green — the registry was declared "where
# it is EXECUTED rather than merely documented", and the execution was the one thing untested. The
# route is the only place the two tables are composed, so it is the only place the claim can be
# proven; `tests/test_skill_table_contract.py` proves the entries DESERVE the opt-in, which is a
# different question from whether the runtime honours it.


def _run_boxplot(**params) -> dict:
    r = client.post("/skills/boxplot/run", params=params,
                    files={"matrix": ("counts.csv", _CLEAN, "text/csv")})
    assert r.status_code == 200, r.text
    return r.json()


def test_also_synthesize_skill_returns_its_native_table_AND_the_synthesized_one():
    """`boxplot` with `pairs=` computes p-values that exist nowhere in the figure except as stars,
    and the figure still encodes a distribution the synthesizer can re-shape. Both ship, in that
    order — the runner's own table leads (D4/D5)."""
    # `A~B`, and the groups must be ones the stub actually has (Cepo / Limma / HVG). Both halves
    # cost this test a red run, and both are worth pinning: a pair with the wrong SEPARATOR and a
    # pair naming absent LEVELS are indistinguishable from `pairs=` never being set — the run
    # silently falls through to plain L3 synthesis and returns one table. So `pairs=` being SET is
    # not the same condition as `pairs=` being TESTABLE, and only the second composes two tables.
    tables = _run_boxplot(pairs="Cepo~HVG")
    assert isinstance(tables["table"], list), "the two-table composition did not happen"
    native, synth = tables["table"]
    assert not native.get("synthesized"), "the runner's own table must not be tagged synthesized"
    assert synth.get("synthesized") is True, (
        "the appended table is the ONLY thing telling a reader it was re-shaped from the figure"
    )
    # They must carry DIFFERENT numbers, or appending prints the same result twice under two names.
    assert native["columns"] != synth["columns"]
    # G4 at the site that composes the list: a stacked panel is told apart from its neighbour by its
    # title, and this route is where the list is built.
    assert all(str(t.get("title") or "").strip() for t in tables["table"])


def test_a_native_skill_outside_the_registry_stays_a_bare_object():
    """The negative half, so the branch cannot widen silently: `deg` is native and NOT in
    `ALSO_SYNTHESIZE`, so it must still come back as one bare StatsTable."""
    r = client.post("/skills/deg/run", files={"matrix": ("counts.csv", _CLEAN, "text/csv")})
    assert isinstance(r.json()["table"], dict)
