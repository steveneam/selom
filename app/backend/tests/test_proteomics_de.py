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


def test_moderated_recovers_more_de_at_small_n():
    """Empirical-Bayes moderation beats an un-moderated t-test at small N: more true DE at the
    same FDR threshold, without inflating false positives. This is the point of the mode."""
    from scipy import stats as sstats

    from skills.proteomics_de.run_real import _bh, _moderated_stats

    rng = np.random.RandomState(0)
    n = 3  # only three replicates per group — where moderation pays off
    n_de, n_null = 40, 160
    effect, sd = 1.2, 0.7
    g = n_de + n_null
    A = np.empty((g, n))
    B = np.empty((g, n))
    truth = np.zeros(g, dtype=bool)
    truth[:n_de] = True
    for i in range(g):
        mu = effect if truth[i] else 0.0
        A[i] = mu + rng.normal(0, sd, n)
        B[i] = rng.normal(0, sd, n)

    _, p_mod = _moderated_stats(A, B)
    padj_mod = _bh(p_mod, np)
    with np.errstate(all="ignore"):
        _, p_welch = sstats.ttest_ind(A, B, axis=1, equal_var=False)
    p_welch = np.where(np.isfinite(p_welch), p_welch, 1.0)
    padj_welch = _bh(p_welch, np)

    tp_mod = int(((padj_mod <= 0.05) & truth).sum())
    fp_mod = int(((padj_mod <= 0.05) & ~truth).sum())
    tp_welch = int(((padj_welch <= 0.05) & truth).sum())

    assert tp_mod > tp_welch, f"moderated should recover more true DE (mod={tp_mod}, welch={tp_welch})"
    assert fp_mod <= 2, f"moderated must not inflate false positives (fp={fp_mod})"


def test_moderated_mode_runs_via_skill():
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        _synthetic_csv(path)
        fig = run_skill(
            "proteomics_de", path,
            {"group_a": "A", "group_b": "B", "log_input": True, "stats": "moderated", "top_n": 40},
        )
    finally:
        os.unlink(path)

    labels = set()
    for tr in fig["data"]:
        if tr.get("mode") == "text":
            labels |= {str(t) for t in tr["text"]}
    assert set(UP) | set(DOWN) <= labels, "moderated mode should still recover the planted DE"
