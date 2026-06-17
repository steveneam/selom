"""Reproduction Engine R3 — the gated R oracle: gating, result parsing, and the blame
verdicts it produces.

No R runs in this suite (the live subprocess is the dev CLI / a slow manual integration,
spec Testing Strategy): **running** is gated + isolated, **parsing + verdict** are pure.
The blame cases are the two real dogfoods' MEASURED oracle numbers — Fig 5 edgeR
FDR<0.05 → 19 vs golden 181 (paper-irreproducible); Fig 6E fgsea on Selom's own Cepo
rankings → 95 vs golden 119, gseapy 36 (engine-delta), shared core fgsea 0 vs 52
(upstream-delta).
"""

import json

import pytest

import oracle as O
import reproduction as R


# --- gating (validation-only, ADR 0002; OFF by default) -----------------------


def test_oracle_disabled_by_default():
    with pytest.raises(O.OracleUnavailable):
        O.resolve_rscript()


def test_runners_are_gated():
    with pytest.raises(O.OracleUnavailable):
        O.run_edger_signature("c.tsv", "u.txt", "Control1", "MSVUS", workdir="x")


# --- result parsing (captured result.json; no R) ------------------------------


def test_read_result(tmp_path):
    (tmp_path / "result.json").write_text(
        json.dumps({"tool": "edgeR", "version": "4.6.0",
                    "metrics": {"signature.adj": 19, "signature.raw": 125, "universe": 1133}}),
        encoding="utf-8",
    )
    res = O.read_result(tmp_path)
    assert res["tool"] == "edgeR"
    assert res["metrics"]["signature.adj"] == 19
    assert res["metrics"]["universe"] == 1133


# --- the blame verdicts the oracle produces (the dogfoods) --------------------


def test_fig5_signature_is_paper_irreproducible():
    # edgeR (authors' actual tool) on the deposited raw data: golden 181, edgeR FDR<0.05 = 19.
    res = O.build_oracle_result(
        "edgeR", R.DEPOSITED_RAW, oracle_value=19, golden=181, computed=19, version="4.6.0",
    )
    assert res.agrees_with_paper is False  # edgeR misses the golden too -> the paper's problem
    assert R.assign_blame(R.FAIL, oracle=res, substituted=True) == R.PAPER_IRREPRODUCIBLE


def test_fig6e_term_count_is_engine_delta():
    # fgsea on Selom's OWN Cepo ranking ~ paper (95 vs 119); gseapy (Selom) far fewer (36).
    # Enriched-term count is engine-sensitive (RISKS #10) -> wide close band on the golden.
    res = O.build_oracle_result(
        "fgsea", R.SELOM_INTERMEDIATE, oracle_value=95, golden=119, computed=36, close_tol=0.5,
    )
    assert res.agrees_with_paper is True
    assert res.agrees_with_selom is False
    assert R.assign_blame(R.FAIL, oracle=res) == R.ENGINE_DELTA


def test_fig6e_shared_core_is_upstream_delta():
    # The 52-term shared core: even fgsea on Selom's rod subtypes gives 0 -> upstream of GSEA.
    res = O.build_oracle_result(
        "fgsea", R.SELOM_INTERMEDIATE, oracle_value=0, golden=52, computed=0, close_tol=0.5,
    )
    assert res.agrees_with_paper is False
    assert R.assign_blame(R.FAIL, oracle=res) == R.UPSTREAM_DELTA


def test_engine_delta_vs_selom_bug_on_raw():
    # If edgeR reproduces the paper on raw and Selom still differs: substitution -> engine-delta,
    # same method -> a genuine selom-engine bug.
    res = O.build_oracle_result("edgeR", R.DEPOSITED_RAW, oracle_value=181, golden=181, computed=19)
    assert res.agrees_with_paper is True
    assert R.assign_blame(R.FAIL, oracle=res, substituted=True) == R.ENGINE_DELTA
    assert R.assign_blame(R.FAIL, oracle=res, substituted=False) == R.SELOM_ENGINE
