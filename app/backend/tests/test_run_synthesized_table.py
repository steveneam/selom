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
