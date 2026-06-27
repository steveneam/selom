"""D2 — POST /skills/{id}/run frame-validation at the skill seam
(docs/architecture-consistency-gate/frame-validation.md).

D1 blocks a *wrong-kind* of data (missing columns / wrong modality → 422). D2 sits one layer below:
the required columns are PRESENT (D1 passes) but one carries no usable data — a present-but-empty
fold-change column. That frame passes QC (the p-value column gives it numeric data) and D1 (both
column names exist), then becomes a silently-degenerate volcano inside the runner. D2 catches the
malformed handoff at the seam with a clear **400 frame_validation_failed**, not a 500 stack trace.

As with D1, the engine classifier + QC run for real under the stub *runner*, so a stubbed skill
still gets the true pre-run frame check.
"""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

# A DE-results table whose fold-change column is PRESENT but entirely empty (every cell blank), with
# a valid p-value column. Classifies as de_results (both names present), passes QC (padj is numeric,
# in range) and D1 (both groups present) — so it reaches D2, which flags the empty fold-change.
_DE_EMPTY_FC = ("de_empty_fc.csv",
                b"gene,log2FoldChange,padj\nACTB,,0.001\nGAPDH,,0.02\nB2M,,0.9\n",
                "text/csv")
# A well-formed DE table — the right, usable input for volcano.
_DE = ("de.csv", b"gene,log2FoldChange,padj\nACTB,2.1,0.001\nGAPDH,-1.4,0.02\nB2M,0.1,0.9\n",
       "text/csv")
# A raw counts table — no fold-change/p-value at all (D1's 422 territory, not D2's).
_COUNTS = ("counts.csv",
           b"gene,WT_1,WT_2,KO_1,KO_2\nACTB,10,12,40,44\nGAPDH,30,28,5,6\nB2M,5,6,8,9\n",
           "text/csv")


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    # Stub the RUNNER (fast, dep-free); the engine classifier + QC the seam check relies on still run.
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def test_empty_required_column_blocked_at_the_seam():
    """The acceptance: a malformed clean→skill handoff (an empty required column) fails at the seam
    with a clear 400 naming the column — not a runtime stack trace / silently-degenerate figure."""
    r = client.post("/skills/volcano/run", files={"matrix": _DE_EMPTY_FC})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "frame_validation_failed"
    assert detail["skill_id"] == "volcano"
    assert detail["stage"] == "skill_input"
    assert "fold-change" in detail["message"]                      # names what's wrong
    assert detail["violations"][0]["code"] == "empty_column"       # structured, rides along
    assert detail["violations"][0]["column"] == "log2FoldChange"


def test_well_formed_de_table_runs_no_false_block():
    """A usable DE table is not blocked — D2 fires only on a determined structural defect."""
    r = client.post("/skills/volcano/run", files={"matrix": _DE})
    assert r.status_code == 200
    assert r.json()["figure"]["data"]


def test_override_bypasses_the_seam_check():
    """override=true is the escape hatch (the same as the QC + D1 gates) — the run proceeds."""
    r = client.post("/skills/volcano/run?override=true", files={"matrix": _DE_EMPTY_FC})
    assert r.status_code == 200


def test_missing_columns_is_d1_not_d2():
    """A counts table (no fold-change column at all) is D1's 422 — D2 doesn't double-report a column
    that isn't there. Confirms the layers are complementary, not overlapping."""
    r = client.post("/skills/volcano/run", files={"matrix": _COUNTS})
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "data_contract_failed"


def test_uncontracted_skill_is_not_seam_checked():
    """A skill with no column contract (pca) is never frame-checked here — its own runner validates
    its input. The empty-fc table still has a numeric p-value column for pca to read."""
    r = client.post("/skills/pca/run", files={"matrix": _DE_EMPTY_FC})
    assert r.status_code == 200
