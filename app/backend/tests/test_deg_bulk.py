"""deg bulk + time-course: design inference, contrast selection, and guard contracts.

Fast, dep-free unit tests for the new bulk raw-count + time-course logic — the parts
most prone to regression: group inference (name-strip + design sheet), contrast
selection and its error contracts, timepoint parsing, and the deterministic light
fallbacks (forced by hiding pyDESeq2). Real pyDESeq2 numerics are validated by
dogfooding on real datasets (docs/real-datasets.md), not here — unit tests stay
deterministic and heavy-dep-free, matching test_skills_golden.
"""

import sys

import numpy as np
import pandas as pd
import pytest

from skills.deg.run_real import _bulk, _labels_from_design_or_names, _numeric_time, _timecourse


@pytest.fixture
def no_pydeseq2(monkeypatch):
    """Hide pyDESeq2 so the runners take their deterministic light fallback path."""
    monkeypatch.setitem(sys.modules, "pydeseq2", None)


def _write_counts(path, columns, planted=None, seed=0, n_genes=20):
    """A deterministic genes x samples integer count CSV; `planted` maps gene index ->
    a per-sample additive vector (to inject a known up/trend signal)."""
    rng = np.random.default_rng(seed)
    mat = rng.integers(20, 80, size=(n_genes, len(columns))).astype(int)
    for gene_idx, add in (planted or {}).items():
        mat[gene_idx] = np.maximum(mat[gene_idx] + np.asarray(add, dtype=int), 0)
    df = pd.DataFrame(mat, index=[f"g{i}" for i in range(n_genes)], columns=columns)
    df.to_csv(path)
    return str(path)


# --- group inference ------------------------------------------------------------


def test_label_inference_strips_replicate_suffix():
    cols = ["B7_CE11_1_ASO_AK1_1", "B7_CE11_1_ASO_AK1_2", "B7_CE11_1_ASO_SCR_1", "ctrl_1", "ctrl_2"]
    labels = _labels_from_design_or_names(cols, {})
    assert labels["B7_CE11_1_ASO_AK1_1"] == "B7_CE11_1_ASO_AK1"
    assert labels["ctrl_2"] == "ctrl"
    assert sorted(set(labels.values())) == ["B7_CE11_1_ASO_AK1", "B7_CE11_1_ASO_SCR", "ctrl"]


def test_label_inference_from_design_sheet_drops_unmatched(tmp_path):
    design = tmp_path / "design.csv"
    design.write_text("SampleID,grp\nS1,A\nS2,A\nS3,B\nS4,B\n")
    cols = ["S1", "S2", "S3", "S4", "S99"]  # S99 has no design row -> excluded, not an error
    labels = _labels_from_design_or_names(cols, {"_design_path": str(design), "group_col": "grp"})
    assert labels == {"S1": "A", "S2": "A", "S3": "B", "S4": "B"}


@pytest.mark.parametrize("value,expected", [("P14", 14), ("day7", 7), ("6h", 6), ("30", 30), ("-5", -5)])
def test_numeric_time(value, expected):
    assert _numeric_time(value) == expected


def test_numeric_time_no_number():
    with pytest.raises(ValueError):
        _numeric_time("baseline")


# --- bulk contrast-selection error contracts (raise before any DE engine) -------


def test_bulk_ambiguous_contrast_lists_groups(tmp_path):
    path = _write_counts(tmp_path / "c.csv", ["a_1", "a_2", "b_1", "b_2", "c_1", "c_2"])
    with pytest.raises(ValueError, match="2-group contrast"):
        _bulk(path, {"mode": "bulk", "top_n": 5})


def test_bulk_unknown_group_rejected(tmp_path):
    path = _write_counts(tmp_path / "c.csv", ["ctrl_1", "ctrl_2", "treat_1", "treat_2"])
    with pytest.raises(ValueError, match="not among detected groups"):
        _bulk(path, {"mode": "bulk", "top_n": 5, "reference": "nope", "treatment": "treat"})


def test_bulk_too_few_replicates(tmp_path):
    path = _write_counts(tmp_path / "c.csv", ["ctrl_1", "ctrl_2", "treat_1"])
    with pytest.raises(ValueError, match="replicates"):
        _bulk(path, {"mode": "bulk", "top_n": 5})


def test_bulk_fallback_recovers_planted_signal(tmp_path, no_pydeseq2):
    # g0 strongly up in treatment -> CPM-log2FC fallback should rank it near the top.
    cols = ["ctrl_1", "ctrl_2", "ctrl_3", "treat_1", "treat_2", "treat_3"]
    path = _write_counts(tmp_path / "c.csv", cols, planted={0: [0, 0, 0, 4000, 4000, 4000]})
    fig = _bulk(path, {"mode": "bulk", "top_n": 5})
    assert "treat vs ctrl" in fig["layout"]["title"]["text"]
    assert "g0" in fig["data"][0]["y"]                       # planted up gene surfaced
    assert len(fig["data"][0]["x"]) == 5                     # top_n bars
    import json
    assert json.loads(json.dumps(fig)) == fig               # plain JSON, no numpy leakage


# --- time-course error contracts + fallback -------------------------------------


def test_timecourse_requires_design(tmp_path):
    path = _write_counts(tmp_path / "c.csv", ["s1", "s2", "s3", "s4"])
    with pytest.raises(ValueError, match="design sheet"):
        _timecourse(path, {"mode": "timecourse", "top_n": 5})


def test_timecourse_needs_three_timepoints(tmp_path):
    cols = ["s1", "s2", "s3", "s4"]
    path = _write_counts(tmp_path / "c.csv", cols)
    design = tmp_path / "d.csv"
    design.write_text("SampleID,time\ns1,P14\ns2,P14\ns3,P30\ns4,P30\n")  # only 2 timepoints
    with pytest.raises(ValueError, match="distinct timepoints"):
        _timecourse(path, {"mode": "timecourse", "top_n": 5, "_design_path": str(design), "time_col": "time"})


def test_timecourse_fallback_recovers_trend(tmp_path, no_pydeseq2):
    cols = [f"s{i}" for i in range(9)]
    times = [7, 7, 7, 14, 14, 14, 21, 21, 21]
    # g0 rises monotonically with time -> Pearson trend fallback should surface it.
    trend = [int((t - 14) * 300) for t in times]
    path = _write_counts(tmp_path / "c.csv", cols, planted={0: trend}, n_genes=15)
    design = tmp_path / "d.csv"
    design.write_text("SampleID,time\n" + "".join(f"{c},{t}\n" for c, t in zip(cols, times)))
    fig = _timecourse(path, {"mode": "timecourse", "top_n": 6, "_design_path": str(design), "time_col": "time"})
    names = [tr["name"] for tr in fig["data"]]
    assert "g0" in names
    assert fig["data"][0]["x"] == [7.0, 14.0, 21.0]          # distinct timepoints, sorted
    assert fig["data"][0]["mode"] == "lines+markers"
