"""D1 — POST /skills/{id}/run declared data-contract pre-run gate
(docs/architecture-consistency-gate/skill-input-contract.md).

A skill with a declared input contract (``engine.compat`` — column groups / modality) that is fed a
CERTAIN mismatch is blocked with a clear **422 data_contract_failed** BEFORE the runner is entered,
so the user gets an actionable message, not a runtime stack trace. The gate is honest (only a
positively-determined mismatch blocks) and overridable (``override=true`` bypasses, the same escape
hatch as the QC gate).

The engine classifier runs for real even under the stub *runner* (it is engine-level, not the skill),
so a stubbed skill still gets a true fit verdict — exactly the pre-run check the gate needs.
"""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

# A raw counts table (gene + sample columns) — the wrong input for volcano, which reads a DE-results
# table. No fold-change / p-value columns → a determined miss.
_COUNTS = ("counts.csv",
           b"gene,WT_1,WT_2,KO_1,KO_2\nACTB,10,12,40,44\nGAPDH,30,28,5,6\nB2M,5,6,8,9\n",
           "text/csv")
# A DE-results table — what volcano actually needs (logFC + padj).
_DE = ("de.csv", b"gene,log2FoldChange,padj\nACTB,2.1,0.001\nGAPDH,-1.4,0.02\nB2M,0.1,0.9\n",
       "text/csv")


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    # Stub the RUNNER (fast, dep-free); the engine classifier the gate relies on still runs for real.
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def test_volcano_on_counts_is_blocked_pre_run():
    """The acceptance: a DE-viz skill dropped on a counts table gets a clear pre-run message naming
    the missing columns — a 422, not a 500 stack trace from inside the runner."""
    r = client.post("/skills/volcano/run", files={"matrix": _COUNTS})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "data_contract_failed"
    assert detail["skill_id"] == "volcano"
    assert "fold-change" in detail["message"]                 # names what's missing
    assert detail["data_fit"]["verdict"] == "missing_columns"  # the structured verdict rides along


def test_volcano_on_de_table_runs_no_false_block():
    """The right data is NOT blocked — the gate only fires on a determined mismatch (no false block)."""
    r = client.post("/skills/volcano/run", files={"matrix": _DE})
    assert r.status_code == 200
    assert r.json()["figure"]["data"]


def test_override_bypasses_the_contract_gate():
    """override=true is the escape hatch (a rare classifier / synonym miss) — the run proceeds."""
    r = client.post("/skills/volcano/run?override=true", files={"matrix": _COUNTS})
    assert r.status_code == 200


def test_uncontracted_skill_is_not_gated_runner_validates_instead():
    """A skill with no compat contract (pca) is never gated here — its own runner validates the input
    (the existing ValueError→400 path). The two layers are complementary, not duplicated."""
    r = client.post("/skills/pca/run", files={"matrix": _COUNTS})
    assert r.status_code == 200  # pca has no modality/column contract → optimistic, runs
