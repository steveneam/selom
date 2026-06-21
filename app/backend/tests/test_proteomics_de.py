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


def test_emits_de_table_with_machine_readable_counts():
    """§8 step 5: proteomics_de now attaches the canonical de_table so its DE counts are
    machine-readable at source (the prior gap). The shared L1 reader resolves
    de_up/de_down/de_total from the direction column — de_total = up + down, NOT the
    tested-protein row count (the trap the schema doc warns about)."""
    from extract.readers import L1, SRC_TABLE, read_metric
    from skills.contract import run_skill_with_table

    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        _synthetic_csv(path)
        figure, table = run_skill_with_table(
            "proteomics_de", path,
            {"group_a": "A", "group_b": "B", "log_input": True, "top_n": 40},
        )
    finally:
        os.unlink(path)

    assert table is not None and "table" not in figure  # table popped from the figure (D7)
    assert table["columns"] == ["gene", "log2FC", "padj", "direction"]

    up = read_metric("proteomics_de", "de_up", figure, table)
    down = read_metric("proteomics_de", "de_down", figure, table)
    total = read_metric("proteomics_de", "de_total", figure, table)
    assert (up.value, down.value, total.value) == (len(UP), len(DOWN), len(UP) + len(DOWN))
    assert up.layer == L1 and up.source == SRC_TABLE  # shared volcano de_table reader, not L2


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


def test_impute_mean_default_matches_prior_row_mean():
    """The default ``mean`` mode must reproduce the prior per-protein-row mean impute exactly,
    so verified outputs stay byte-identical."""
    from skills.proteomics_de.run_real import _impute

    M = np.array([[1.0, np.nan, 3.0], [np.nan, 2.0, 4.0]])
    got = _impute(M, "mean", np)
    exp = M.copy()
    rowmean = np.nanmean(M, axis=1)
    exp[0, 1] = rowmean[0]
    exp[1, 0] = rowmean[1]
    assert np.allclose(got, exp)
    assert np.isfinite(got).all()


def test_impute_mindet_fills_from_low_detection_tail():
    """``mindet`` is left-censored per sample: a high protein dropping out in one sample is
    filled from that sample's low tail — NOT the protein's high row mean (the MNAR fix)."""
    from skills.proteomics_de.run_real import _impute

    # protein 0 is high (8) but missing in sample col 2, whose other proteins are low (2,3)
    M = np.array([[8.0, 8.0, np.nan], [1.0, 2.0, 3.0], [0.5, 1.0, 2.0]])
    mindet = _impute(M, "mindet", np)
    mean = _impute(M, "mean", np)
    assert mean[0, 2] == 8.0, "mean impute fills the dropout with the protein's high row mean"
    assert mindet[0, 2] < 3.0, "mindet fills from the sample's low detection tail, not the high mean"
    assert mindet[0, 2] < mean[0, 2], "left-censored fill must be below the mean fill (preserves MNAR FC)"


def test_impute_minprob_is_deterministic_and_downshifted():
    """``minprob`` draws from a downshifted normal but is seeded -> reproducible across runs,
    and lands below the sample's observed mean."""
    from skills.proteomics_de.run_real import _impute

    M = np.array([[5.0, 6.0, np.nan], [1.0, 2.0, 3.0], [2.0, 3.0, 4.0]])
    a = _impute(M, "minprob", np)
    b = _impute(M, "minprob", np)
    assert np.allclose(a, b), "seeded minprob must be reproducible"
    assert np.isfinite(a).all()
    col2_obs_mean = np.nanmean(np.array([3.0, 4.0]))  # observed entries of sample col 2
    assert a[0, 2] < col2_obs_mean, "downshifted draw should sit below the observed mean"


def test_mindet_mode_runs_via_skill():
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        _synthetic_csv(path)
        fig = run_skill(
            "proteomics_de", path,
            {"group_a": "A", "group_b": "B", "log_input": True, "missing": "mindet", "top_n": 40},
        )
    finally:
        os.unlink(path)

    labels = set()
    for tr in fig["data"]:
        if tr.get("mode") == "text":
            labels |= {str(t) for t in tr["text"]}
    assert set(UP) | set(DOWN) <= labels, "mindet mode should still recover the planted DE"
