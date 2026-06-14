"""proteomics_de differential abundance — recovers planted DE on a synthetic matrix.

CI-safe validation (G): the real engine (Welch t-test over log2 median-normalized
intensities + Benjamini-Hochberg FDR) runs on a synthetic proteins × samples matrix with
known up/down proteins, asserting the volcano recovers them with the correct direction and
leaves the null proteins unlabelled. Uses ``log_input`` so the planted log2 effects are
exact. Skipped when the scientific stack (numpy/pandas/scipy) is unavailable.
"""

import os
import tempfile

import pytest

from skills.contract import run_skill

np = pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("scipy")

UP = [f"U{i}" for i in range(15)]
DOWN = [f"D{i}" for i in range(15)]
NULL = [f"N{i}" for i in range(170)]


def _synthetic_csv(path: str) -> None:
    import pandas as pd

    rng = np.random.RandomState(0)
    a_cols = [f"A{i}" for i in range(4)]
    b_cols = [f"B{i}" for i in range(4)]
    base = 20.0  # already log2-scale; run with log_input=True so the engine keeps it
    rows = []
    for name in UP + DOWN + NULL:
        a_mu = base + (2.0 if name in UP else -2.0 if name in DOWN else 0.0)
        b_mu = base
        row = {"protein": name}
        for c in a_cols:
            row[c] = a_mu + rng.normal(0, 0.3)
        for c in b_cols:
            row[c] = b_mu + rng.normal(0, 0.3)
        rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False)


@pytest.fixture(autouse=True)
def _real(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "real")


def test_proteomics_de_recovers_planted_de():
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        _synthetic_csv(path)
        fig = run_skill(
            "proteomics_de", path,
            {"group_a": "A", "group_b": "B", "log_input": True, "top_n": 40},
        )
    finally:
        os.unlink(path)

    # Labels are the significant genes (top_n=40 covers all 30 planted DE, no nulls).
    labels = {}
    for tr in fig["data"]:
        if tr.get("mode") == "text":
            for x, name in zip(tr["x"], tr["text"]):
                labels[str(name)] = float(x)

    assert set(labels) == set(UP) | set(DOWN), "labelled set should be exactly the planted DE"
    assert all(labels[u] > 0 for u in UP), "up proteins (higher in A) must have positive log2FC"
    assert all(labels[d] < 0 for d in DOWN), "down proteins (lower in A) must have negative log2FC"
    assert not (set(labels) & set(NULL)), "no null protein should be called significant"
