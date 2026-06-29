"""P1 ingest engine hooks — the column-override (map_columns) end-to-end + provenance.

Covers the engine side the AI flip compiles to (the AI-action side is in test_ai_s3.py):

* engine.columns           — the role→column resolver (override wins; override-only never fabricate).
* engine.databundle.classify — DE detection honours an override.
* engine.compat.fit        — a non-standard-named DE column is missing_columns-gated WITHOUT the
                             override, and FITS with it (the gate that would otherwise block the run).
* engine.frame_schema      — D2 usability-checks the OVERRIDDEN column (what the runner reads).
* skills.volcano.run_real  — the figure is drawn from the overridden columns; a re-run from the
                             recorded override reproduces it (AI compiles away).
* skills.contract.resolved_params — _column_override IS recorded (reproducible); _design_path is not.
* POST /run                — the override threads end-to-end; a missing-column override is a clean 400.

Fast gate (no scanpy): the runner test calls volcano/run_real directly (pandas+numpy); the endpoint
tests run under the stub engine — the D1/D2 gates + the 400 guard fire in _execute_skill_run before
the runner, so they're exercised regardless of engine mode.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# engine.columns — the resolver
# ---------------------------------------------------------------------------

def test_resolver_override_wins_over_synonym():
    from engine.columns import override_column

    cols = ["GeneName", "log2FoldChange", "FoldChange_custom", "padj"]
    # Override points at an existing column → it wins (even though a synonym column also exists).
    assert override_column({"logFC": "FoldChange_custom"}, "logFC", cols) == "FoldChange_custom"


def test_resolver_missing_override_column_returns_none():
    """Override-only, never fabricate: a mapping to an absent column resolves to None."""
    from engine.columns import override_column

    assert override_column({"logFC": "nope"}, "logFC", ["gene", "padj"]) is None
    assert override_column(None, "logFC", ["gene"]) is None
    assert override_column({"pval": "padj"}, "logFC", ["padj"]) is None  # role not in the map


def test_resolver_overridable_roles_disjoint_from_set_design():
    from engine.columns import OVERRIDABLE_ROLES

    assert OVERRIDABLE_ROLES == frozenset({"logFC", "pval", "gene"})
    assert "condition" not in OVERRIDABLE_ROLES and "batch" not in OVERRIDABLE_ROLES


# ---------------------------------------------------------------------------
# engine.databundle.classify — DE detection honours an override
# ---------------------------------------------------------------------------

def test_classify_honours_override_for_de_detection():
    import pandas as pd
    from engine import databundle
    from engine.models import DE_RESULTS

    df = pd.DataFrame({"GeneName": ["A", "B"], "FC_custom": [1.0, 2.0], "padj": [0.01, 0.02]})
    # Without the override the fold-change column isn't a synonym → not a DE table.
    assert databundle.classify(df) != DE_RESULTS
    # With the override (pval 'padj' is a synonym) → DE_RESULTS.
    assert databundle.classify(df, override={"logFC": "FC_custom"}) == DE_RESULTS
    # Override pointing at an absent column never fabricates the role.
    assert databundle.classify(df, override={"logFC": "ghost"}) != DE_RESULTS


# ---------------------------------------------------------------------------
# engine.compat.fit — the D1 gate honours the override
# ---------------------------------------------------------------------------

def _fa(columns):
    from engine.compat import FileAssessment
    from engine.models import GENERIC_TABLE

    return FileAssessment(path="x.csv", filename="x.csv", loadable=True, kind=GENERIC_TABLE,
                          quality=100, qc_ok=True, columns=columns, n_numeric_cols=2)


def test_compat_fit_gates_mismatched_fc_without_override():
    from engine.compat import fit

    fa = _fa(["GeneName", "FoldChange_custom", "padj"])  # FC col is not a synonym
    df = fit("volcano", fa)
    assert df.gated is True
    assert df.verdict == "missing_columns"


def test_compat_fit_passes_with_column_override():
    from engine.compat import fit

    fa = _fa(["GeneName", "FoldChange_custom", "padj"])
    df = fit("volcano", fa, column_override={"logFC": "FoldChange_custom"})
    assert df.gated is False
    assert df.compatible is True


def test_compat_fit_other_callers_unchanged():
    """Default column_override=None keeps every existing caller's behaviour (a real DE table fits)."""
    from engine.compat import fit

    fa = _fa(["gene", "log2FoldChange", "padj"])
    assert fit("volcano", fa).compatible is True


# ---------------------------------------------------------------------------
# engine.frame_schema — D2 checks the OVERRIDDEN column's usability
# ---------------------------------------------------------------------------

def test_frame_schema_checks_overridden_column():
    import pandas as pd
    from engine import frame_schema

    # An all-text fold-change column the user mapped → D2 flags it non-numeric (what the runner reads).
    df = pd.DataFrame({"FoldChange_custom": ["a", "b"], "padj": [0.01, 0.02]})
    errs = frame_schema.check_skill_input("volcano", df, override={"logFC": "FoldChange_custom"})
    assert any(e.code == "non_numeric_column" and e.column == "FoldChange_custom" for e in errs)
    # Without the override the non-synonym column isn't inspected (a missing group is D1's job).
    assert frame_schema.check_skill_input("volcano", df) == []


# ---------------------------------------------------------------------------
# skills.volcano.run_real — the figure reads the override + reproduces from the record
# ---------------------------------------------------------------------------

_CSV = "GeneName,FoldChange_custom,Significance_custom\nA,2.5,0.001\nB,-3.0,0.0001\nC,0.1,0.5\n"


def test_volcano_runner_reads_override(tmp_path):
    from skills.volcano import run_real

    path = tmp_path / "de.csv"
    path.write_text(_CSV)

    # Without an override the non-standard columns aren't found → the runner's honest ValueError.
    with pytest.raises(ValueError):
        run_real.run(str(path), {})

    override = {"logFC": "FoldChange_custom", "pval": "Significance_custom", "gene": "GeneName"}
    spec = run_real.run(str(path), {"_column_override": override})
    assert spec["data"], "the figure should be drawn from the overridden columns"
    # The figure was built from the mapped fold-change values (A=+2.5 up, B=-3.0 down).
    assert spec["table"] is not None


def test_volcano_no_gene_column_uses_index_without_crashing(tmp_path):
    """Mapping only logFC+pval (no gene) → labels come from the frame index. Regression for the
    'Index has no .iloc' 500 the live verify caught: genes must be a Series, not a bare Index."""
    from skills.volcano import run_real

    # No gene column at all; significant points exist (so the top-N label path runs .iloc).
    path = tmp_path / "nogene.csv"
    path.write_text("FoldChange_custom,Significance_custom\n2.8,0.0001\n-3.1,0.00005\n0.1,0.9\n")
    spec = run_real.run(str(path), {"_column_override": {"logFC": "FoldChange_custom",
                                                         "pval": "Significance_custom"}})
    assert spec["data"], "the figure should render with index-derived labels"


def test_volcano_override_reproduces_with_no_ai(tmp_path):
    """Re-running from the recorded params (which carry _column_override) reproduces the figure."""
    from skills.contract import load_skill, resolved_params
    from skills.volcano import run_real

    path = tmp_path / "de.csv"
    path.write_text(_CSV)
    override = {"logFC": "FoldChange_custom", "pval": "Significance_custom", "gene": "GeneName"}

    first = run_real.run(str(path), {"_column_override": override})
    # The recorded params a downstream re-run would replay (no AI in the loop).
    recorded = resolved_params(load_skill("volcano"), {"_column_override": override})
    assert recorded["_column_override"] == override
    second = run_real.run(str(path), recorded)
    assert first["data"] == second["data"]


# ---------------------------------------------------------------------------
# skills.contract.resolved_params — _column_override recorded, _design_path stripped
# ---------------------------------------------------------------------------

def test_step_param_coupling_guard():
    """Drift guard for the STEP_PARAM convention: every (step_id, param) must be (a) emitted by a
    cleaning plan as a CleaningStep(id=step_id, param=param), and (b) declared by >=1 installed skill.
    Fails if a step id is renamed, the param is dropped from the skills, or a STEP_PARAM key is added
    with no plan step / no skill behind it (gauntlet spine-consistency finding 2026-06-30)."""
    import anndata as ad
    import numpy as np
    import pandas as pd
    from engine.cleaning import STEP_PARAM, plan_cleaning
    from engine.databundle import DataBundle
    from engine.models import BULK_COUNTS, PROTEOMICS, SC_COUNTS, SourceRef
    from skills.contract import load_skill
    from skills.registry import list_skill_ids

    adata = ad.AnnData(np.array([[1.0, 0.0, 2.0], [0.0, 3.0, 1.0]]))
    bulk = pd.DataFrame({"s1": [5, 0, 7], "s2": [6, 1, 0]})
    prot = pd.DataFrame({"s1": [1.0, None, 7.0], "s2": [6.0, 1.0, None]})
    plans = [
        plan_cleaning(DataBundle(payload=adata, kind=SC_COUNTS, source=SourceRef(filename="c.h5ad"))),
        plan_cleaning(DataBundle(payload=bulk, kind=BULK_COUNTS, source=SourceRef(filename="b.csv"))),
        plan_cleaning(DataBundle(payload=prot, kind=PROTEOMICS, source=SourceRef(filename="p.csv"))),
    ]
    emitted = {(s.id, s.param) for p in plans for s in p.steps if s.param}

    declared: set[str] = set()
    for sid in list_skill_ids():
        try:
            declared |= set(load_skill(sid).param_spec)
        except Exception:  # noqa: BLE001 — a skill that won't load can't be a controller; skip it
            pass

    for step_id, param in STEP_PARAM.items():
        assert (step_id, param) in emitted, (
            f"STEP_PARAM[{step_id!r}]={param!r}: no cleaning plan emits a step with that id+param "
            f"(emitted: {sorted(emitted)})")
        assert param in declared, f"STEP_PARAM param {param!r} is not declared by any installed skill"


def test_resolved_params_records_override_strips_design_path():
    from skills.contract import load_skill, resolved_params

    out = resolved_params(load_skill("volcano"),
                          {"fc_threshold": 1.5, "_column_override": {"logFC": "X"},
                           "_design_path": "/tmp/x"})
    assert out["_column_override"] == {"logFC": "X"}
    assert "_design_path" not in out
    assert out["fc_threshold"] == 1.5


# ---------------------------------------------------------------------------
# POST /run — the override threads end-to-end (stub engine; gates fire pre-runner)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


_FILES = {"matrix": ("de.csv", _CSV.encode(), "text/csv")}


def test_run_gates_mismatched_columns_without_override(client):
    """A non-standard-named DE table is D1-gated (data_contract_failed) without the override."""
    r = client.post("/skills/volcano/run", files=_FILES)
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "data_contract_failed"


def test_run_passes_and_records_override(client):
    """With the override the run proceeds AND _column_override lands in provenance.params."""
    import json

    ov = {"logFC": "FoldChange_custom", "pval": "Significance_custom", "gene": "GeneName"}
    r = client.post(f"/skills/volcano/run?_column_override={json.dumps(ov)}", files=_FILES)
    assert r.status_code == 200, r.text
    assert r.json()["provenance"]["params"]["_column_override"] == ov


def test_run_missing_override_column_is_clean_400(client):
    """An override pointing at a column the data doesn't carry → a clear 400, not a crash."""
    import json

    r = client.post(f"/skills/volcano/run?_column_override={json.dumps({'logFC': 'ghost'})}",
                    files=_FILES)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "column_override_missing"
    assert "ghost" in r.json()["detail"]["missing"]["logFC"]


def test_run_override_flag_bypasses_guard_and_prunes_poison_override(client):
    """override=true is the same escape hatch as the QC/D1/D2 gates — BUT an unresolvable override
    must not be recorded as a poison value the runner silently ignores: provenance must reflect only
    what fed the figure (gauntlet repro-integrity fix). All entries unresolvable → key dropped."""
    import json

    r = client.post(f"/skills/volcano/run?override=true&_column_override={json.dumps({'logFC': 'ghost'})}",
                    files=_FILES)
    assert r.status_code == 200, r.text
    # The ghost mapping never fed the figure (the runner fell back to synonyms) → not recorded.
    assert "_column_override" not in r.json()["provenance"]["params"]


def test_run_override_flag_records_only_effective_entries(client):
    """A partly-resolvable override under override=true records ONLY the entries that resolve to a
    real column — so a faithful re-run reproduces and provenance doesn't misrepresent the inputs."""
    import json

    ov = {"logFC": "FoldChange_custom", "pval": "ghost"}  # logFC exists in _CSV; pval does not
    r = client.post(f"/skills/volcano/run?override=true&_column_override={json.dumps(ov)}", files=_FILES)
    assert r.status_code == 200, r.text
    assert r.json()["provenance"]["params"]["_column_override"] == {"logFC": "FoldChange_custom"}
