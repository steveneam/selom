"""B4 publish-confidence — statistical / data-quality guardrail tests.

Method/param guardrails and the pure data-guardrail logic are tested directly (no
heavy deps); the stub engine is forced like the other suites. The h5ad profiling that
feeds ``_data_guardrails`` needs anndata and is exercised by the real-engine smoke.
"""

import pytest
from fastapi.testclient import TestClient

import guardrails
from main import app
from skills.contract import load_skill

client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_stub(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "stub")


def _codes(items):
    return {g["code"] for g in items}


def _levels(items):
    assert all(g["level"] in ("info", "warn") for g in items)
    assert all({"level", "code", "title", "detail"} <= set(g) for g in items)


# --- method / param guardrails (always available, no data read) -----------------

def test_fdr_skills_report_multiple_testing():
    for skill in ("deg", "volcano", "enrichment"):
        g = guardrails.build(load_skill(skill), "x.csv", {})
        _levels(g)
        assert "multiple-testing" in _codes(g)


def test_non_fdr_skill_has_no_multiple_testing():
    g = guardrails.build(load_skill("umap_scrna"), "x.csv", {})
    assert "multiple-testing" not in _codes(g)


def test_lax_fdr_threshold_warns():
    # Query-style string param is coerced before the check (0.3 > 0.1).
    g = guardrails.build(load_skill("volcano"), "x.csv", {"fdr_threshold": "0.3"})
    fdr = [x for x in g if x["code"] == "fdr-threshold"]
    assert fdr and fdr[0]["level"] == "warn" and "Lax" in fdr[0]["title"]


def test_no_fdr_filtering_warns():
    g = guardrails.build(load_skill("volcano"), "x.csv", {"fdr_threshold": "1.0"})
    fdr = [x for x in g if x["code"] == "fdr-threshold"]
    assert fdr and "No FDR filtering" in fdr[0]["title"]


def test_conventional_fdr_threshold_no_warn():
    g = guardrails.build(load_skill("volcano"), "x.csv", {"fdr_threshold": "0.05"})
    assert "fdr-threshold" not in _codes(g)


# --- data guardrails (pure logic over a crafted profile) ------------------------

def test_low_cell_count_warns():
    g = guardrails._data_guardrails(load_skill("cluster"), {"n_obs": 80, "batch_columns": {}})
    warn = [x for x in g if x["code"] == "low-cell-count"]
    assert warn and warn[0]["level"] == "warn"


def test_ample_cells_no_low_cell_warning():
    g = guardrails._data_guardrails(load_skill("cluster"), {"n_obs": 3000, "batch_columns": {}})
    assert "low-cell-count" not in _codes(g)


def test_pre_normalized_input_warns_for_normalizing_skills():
    profile = {"n_obs": 3000, "x_max": 9.1, "x_is_integer": False, "batch_columns": {}}
    assert "pre-normalized-input" in _codes(guardrails._data_guardrails(load_skill("cluster"), profile))


def test_raw_counts_no_normalization_warning():
    raw = {"n_obs": 3000, "x_max": 4123.0, "x_is_integer": True, "batch_columns": {}}
    assert "pre-normalized-input" not in _codes(guardrails._data_guardrails(load_skill("cluster"), raw))


def test_normalization_check_only_for_normalizing_skills():
    # deg does not normalize internally, so a pre-normalized input is not flagged for it.
    profile = {"n_obs": 3000, "x_max": 9.1, "x_is_integer": False, "batch_columns": {}}
    assert "pre-normalized-input" not in _codes(guardrails._data_guardrails(load_skill("deg"), profile))


def test_batch_column_warns():
    g = guardrails._data_guardrails(load_skill("umap_scrna"), {"n_obs": 3000, "batch_columns": {"sample": 4}})
    batch = [x for x in g if x["code"] == "uncorrected-batch"]
    assert batch and "sample" in batch[0]["detail"]


# --- the /run bundle carries guardrails -----------------------------------------

def test_run_endpoint_includes_guardrails():
    res = client.post(
        "/skills/volcano/run?fdr_threshold=0.5",
        files={"matrix": ("de.csv", b"gene,log2fc,pval\nA,2,0.01\n", "text/csv")},
    )
    assert res.status_code == 200
    body = res.json()
    assert "guardrails" in body
    codes = {g["code"] for g in body["guardrails"]}
    assert "fdr-threshold" in codes and "multiple-testing" in codes
