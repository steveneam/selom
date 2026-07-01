"""engine.suggest_design_hints + the /data/inspect `design` field — the intake questionnaire's
deterministic DESIGN prefill (Layer A ingest, AI-off). Asserts the four detections the engine did
NOT do before: candidate group columns, distinct levels, replicate-per-level counts, control guess.
See docs/intake-questionnaire/build-spec.md §2."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from engine import suggest_design_hints
from engine.databundle import DataBundle
from engine.models import BULK_COUNTS, DE_RESULTS, GENERIC_TABLE, SC_COUNTS
from main import app

client = TestClient(app)


# --- bulk: condition labels inferred from the sample column names -----------------------------------

def test_bulk_infers_conditions_from_column_names():
    # genes x samples; the gene-id is a string first column (drops out as non-numeric), the sample
    # columns carry a trailing replicate suffix the deg runner strips (ctrl_1 -> ctrl).
    df = pd.DataFrame({
        "gene": [f"g{i}" for i in range(5)],
        "ctrl_1": range(5), "ctrl_2": range(5), "ctrl_3": range(5),
        "treat_1": range(5), "treat_2": range(5),
    })
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    assert hints.needs_design is True
    assert hints.source == "column_names"
    assert hints.best_group == "__column_names__"
    cand = hints.group_candidates[0]
    assert cand.n_levels == 2
    levels = {lv.name: lv.n_replicates for lv in cand.levels}
    assert levels == {"ctrl": 3, "treat": 2}          # replicate count per inferred condition
    assert [lv.name for lv in cand.levels] == ["ctrl", "treat"]   # first-seen (deterministic) order
    assert cand.reference_guess == "ctrl"             # control keyword guess
    assert all(lv.replicate_unit == "samples" for lv in cand.levels)


def test_bulk_control_keyword_guess_matches_dogfood_naming():
    # The EYG28-style naming: PDE6B vs Control. The reference guess should land on Control.
    df = pd.DataFrame({
        "gene": [f"g{i}" for i in range(4)],
        "PDE6B_1": range(4), "PDE6B_2": range(4), "PDE6B_3": range(4),
        "Control_1": range(4), "Control_2": range(4), "Control_3": range(4),
    })
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    assert hints.needs_design is True
    cand = hints.group_candidates[0]
    assert cand.n_levels == 2
    assert {lv.name for lv in cand.levels} == {"PDE6B", "Control"}
    assert cand.reference_guess == "Control"


def test_bulk_numeric_gene_id_not_counted_as_a_sample():
    # GEO-style: an all-integer gene id (Entrez) as the first column. The deg runner drops column 0
    # POSITIONALLY (_read_counts reads index_col=0), so detection must too — the gene-id column must NOT
    # become a phantom condition level. Regression: dtype-filtering counted a numeric gene-id as a
    # sample, manufacturing a spurious level and a treatment the runner would 400 on (detection != run).
    df = pd.DataFrame({
        "Geneid": [100 + i for i in range(5)],            # all-integer gene ids (numeric first column)
        "WT_1": range(5), "WT_2": range(5), "WT_3": range(5),
        "KO_1": range(5), "KO_2": range(5), "KO_3": range(5),
    })
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    assert hints.needs_design is True
    cand = hints.group_candidates[0]
    assert cand.n_levels == 2
    assert {lv.name for lv in cand.levels} == {"WT", "KO"}   # NOT {"Geneid", "WT", "KO"}
    assert {lv.name: lv.n_replicates for lv in cand.levels} == {"WT": 3, "KO": 3}
    assert cand.reference_guess == "WT"


def test_reuses_the_deg_runner_label_constants():
    # The design detector must consume the SAME label logic the deg run consumes (detection == run).
    # These symbols are the contract; a rename/move in skills.deg.run_real must fail LOUDLY here, not
    # silently degrade the questionnaire to a stale copy (the shadow-copy fallback was removed).
    from engine.questionnaire import _obs_aliases, _rep_regex
    from skills.deg.run_real import (
        DEFAULT_REP_REGEX,
        _CONDITION_FALLBACKS,
        _SAMPLE_FALLBACKS,
    )

    assert _rep_regex() == DEFAULT_REP_REGEX
    cond, sample = _obs_aliases()
    assert cond == _CONDITION_FALLBACKS
    assert sample == _SAMPLE_FALLBACKS


def test_bulk_single_condition_needs_no_design():
    # All sample columns collapse to one label -> there is no contrast to capture.
    df = pd.DataFrame({
        "gene": [f"g{i}" for i in range(5)],
        "wt_1": range(5), "wt_2": range(5), "wt_3": range(5),
    })
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    assert hints.needs_design is False
    assert hints.source == "none"


def test_bulk_too_few_samples_needs_no_design():
    df = pd.DataFrame({"gene": [f"g{i}" for i in range(5)], "only": range(5)})
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    assert hints.needs_design is False


# --- de_results / generic: nothing to capture -------------------------------------------------------

def test_de_results_needs_no_design():
    # An already-computed DE table has no raw design to confirm — only the two structure chips show.
    df = pd.DataFrame({"gene": ["RHO", "RPGR"], "log2FoldChange": [1.2, -0.7], "padj": [0.01, 0.04]})
    hints = suggest_design_hints(DataBundle(payload=df, kind=DE_RESULTS))
    assert hints.needs_design is False
    assert hints.source == "none"
    assert hints.group_candidates == []


def test_generic_table_needs_no_design():
    df = pd.DataFrame({"a": ["x", "y"], "b": ["p", "q"]})
    hints = suggest_design_hints(DataBundle(payload=df, kind=GENERIC_TABLE))
    assert hints.needs_design is False


def test_fail_soft_on_bad_payload():
    # A bulk_counts kind whose payload is not a frame must NOT raise — fail-soft to no-design.
    hints = suggest_design_hints(DataBundle(payload=object(), kind=BULK_COUNTS))
    assert hints.needs_design is False
    assert hints.modality == BULK_COUNTS


# --- bulk time-course (2c) --------------------------------------------------------------------------

def test_bulk_timecourse_detected_and_time_sorted():
    # Columns encode an ordered timepoint axis (t0/t24/t120), 2 reps each. Detection must tag the
    # candidate time_course, sort the levels by NUMERIC time (120 > 24, even though "120" < "24"
    # alphabetically — proving it's numeric, not lexical), and emit one design row per sample column.
    df = pd.DataFrame({
        "gene": [f"g{i}" for i in range(5)],
        "t0_1": range(5), "t0_2": range(5),
        "t24_1": range(5), "t24_2": range(5),
        "t120_1": range(5), "t120_2": range(5),
    })
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    assert hints.needs_design is True
    assert hints.source == "column_names"
    cand = hints.group_candidates[0]
    assert cand.kind == "time_course"
    assert [lv.name for lv in cand.levels] == ["t0", "t24", "t120"]      # numeric order, not alphabetical
    assert cand.reference_guess == "t0"                                  # baseline = earliest timepoint
    rows = {r.sample: r.time for r in cand.time_rows}
    assert rows == {
        "t0_1": 0.0, "t0_2": 0.0, "t24_1": 24.0, "t24_2": 24.0, "t120_1": 120.0, "t120_2": 120.0,
    }


def test_bulk_timecourse_times_equal_the_deg_runner_parser():
    # DETECTED == CONSUMED: the emitted times must equal the deg runner's own _numeric_time on the
    # stripped label — the design detector reuses that parser directly (no shadow copy).
    from skills.deg.run_real import _numeric_time

    df = pd.DataFrame({
        "gene": [f"g{i}" for i in range(4)],
        "day0_1": range(4), "day0_2": range(4), "day3_1": range(4), "day7_1": range(4),
    })
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    cand = hints.group_candidates[0]
    assert cand.kind == "time_course"
    for r in cand.time_rows:
        label = r.sample.rsplit("_", 1)[0]                 # drop the _rep suffix the runner strips
        assert r.time == _numeric_time(label)


def test_bulk_two_timepoints_stays_categorical():
    # <3 distinct timepoints → not enough for a trend → the categorical contrast fallback (no worse
    # than today): a 2-level design with no time_rows.
    df = pd.DataFrame({
        "gene": [f"g{i}" for i in range(4)],
        "0h_1": range(4), "0h_2": range(4), "24h_1": range(4), "24h_2": range(4),
    })
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    cand = hints.group_candidates[0]
    assert cand.kind == "categorical"
    assert cand.time_rows == []
    assert cand.n_levels == 2


def test_bulk_timecourse_needs_four_samples():
    # 3 timepoints but only 3 samples (1 rep each) < the deg runner's 4-sample floor → categorical,
    # so we never present a time-course the runner would reject at run time (DETECTED == CONSUMED).
    df = pd.DataFrame({
        "gene": [f"g{i}" for i in range(4)],
        "0h": range(4), "24h": range(4), "48h": range(4),
    })
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    cand = hints.group_candidates[0]
    assert cand.kind == "categorical"


def test_bulk_bare_numeric_labels_not_timecourse():
    # A bare number with no time affix (1/2/3) is as likely a replicate index as a timepoint — it must
    # NOT be called a time-course (E4: fall back to categorical rather than fabricate a time axis).
    df = pd.DataFrame({
        "gene": [f"g{i}" for i in range(4)],
        "1_1": range(4), "1_2": range(4), "2_1": range(4), "3_1": range(4),
    })
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    cand = hints.group_candidates[0]
    assert cand.kind == "categorical"


def test_bulk_non_time_labels_stay_categorical():
    # Plain condition labels (WT/KO/HET) are not timepoints — a normal categorical contrast, no time_rows.
    df = pd.DataFrame({
        "gene": [f"g{i}" for i in range(4)],
        "WT_1": range(4), "WT_2": range(4), "KO_1": range(4), "HET_1": range(4),
    })
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    cand = hints.group_candidates[0]
    assert cand.kind == "categorical"
    assert cand.time_rows == []


def test_inspect_carries_timecourse_design():
    csv = (
        b"gene,t0_1,t0_2,t24_1,t24_2,t48_1,t48_2\n"
        + b"".join(f"g{i},{i},{i + 1},{i + 2},{i + 3},{i + 4},{i + 5}\n".encode() for i in range(20))
    )
    r = client.post("/data/inspect", files={"matrix": ("counts.csv", csv, "text/csv")})
    assert r.status_code == 200
    cand = r.json()["design"]["group_candidates"][0]
    assert cand["kind"] == "time_course"
    assert [lv["name"] for lv in cand["levels"]] == ["t0", "t24", "t48"]
    assert len(cand["time_rows"]) == 6
    assert {row["sample"]: row["time"] for row in cand["time_rows"]}["t48_2"] == 48.0


# --- scRNA: candidate condition columns from obs ----------------------------------------------------

def test_scrna_obs_condition_column_with_sample_replicates():
    ad = pytest.importorskip("anndata")
    import numpy as np

    # 4 biological samples (2 per condition), 3 cells each -> 12 cells. Replicates must count as
    # DISTINCT SAMPLES per condition, not cells.
    samples = ["ctrl_a", "ctrl_b", "mut_a", "mut_b"]
    cond_of = {"ctrl_a": "Control", "ctrl_b": "Control", "mut_a": "Mutant", "mut_b": "Mutant"}
    rows = [(s, cond_of[s]) for s in samples for _ in range(3)]
    obs = pd.DataFrame(
        {"sample": [s for s, _ in rows], "condition": [c for _, c in rows]},
        index=[f"cell{i}" for i in range(len(rows))],
    )
    adata = ad.AnnData(X=np.ones((len(rows), 4), dtype="float32"), obs=obs)

    hints = suggest_design_hints(DataBundle(payload=adata, kind=SC_COUNTS))
    assert hints.needs_design is True
    assert hints.source == "obs"
    assert hints.sample_col == "sample"               # the detected biological-replicate column
    assert hints.best_group == "condition"            # the alias hit wins as the best candidate
    cand = next(c for c in hints.group_candidates if c.key == "condition")
    levels = {lv.name: lv.n_replicates for lv in cand.levels}
    assert levels == {"Control": 2, "Mutant": 2}      # distinct samples per condition (not 6 cells)
    assert all(lv.replicate_unit == "samples" for lv in cand.levels)
    assert cand.reference_guess == "Control"


def test_scrna_sample_col_candidates_offered_for_the_picker():
    # followups #6: the FE sample-col picker needs candidate obs id columns. The detected sample alias
    # leads; other bounded categoricals are offered so the user can override when detection missed.
    ad = pytest.importorskip("anndata")
    import numpy as np

    samples = ["ctrl_a", "ctrl_b", "mut_a", "mut_b"]
    cond_of = {"ctrl_a": "Control", "ctrl_b": "Control", "mut_a": "Mutant", "mut_b": "Mutant"}
    rows = [(s, cond_of[s]) for s in samples for _ in range(3)]
    obs = pd.DataFrame(
        {"donor": [s for s, _ in rows], "condition": [c for _, c in rows]},
        index=[f"cell{i}" for i in range(len(rows))],
    )
    adata = ad.AnnData(X=np.ones((len(rows), 4), dtype="float32"), obs=obs)

    hints = suggest_design_hints(DataBundle(payload=adata, kind=SC_COUNTS))
    assert hints.sample_col == "donor"                     # the detected replicate column (alias)
    assert hints.sample_col_candidates[0] == "donor"       # alias priority leads the picker
    assert "condition" in hints.sample_col_candidates      # other bounded categoricals are offered too


def test_bulk_has_no_sample_col_candidates():
    # No obs on a bulk table → the sample-col picker is scRNA-only; the field stays empty.
    df = pd.DataFrame({
        "gene": [f"g{i}" for i in range(4)],
        "PDE6B_1": range(4), "PDE6B_2": range(4), "Control_1": range(4), "Control_2": range(4),
    })
    hints = suggest_design_hints(DataBundle(payload=df, kind=BULK_COUNTS))
    assert hints.sample_col_candidates == []


def test_scrna_without_sample_column_counts_cells_with_unit_note():
    ad = pytest.importorskip("anndata")
    import numpy as np

    obs = pd.DataFrame(
        {"genotype": ["WT"] * 4 + ["Rd10"] * 4},
        index=[f"cell{i}" for i in range(8)],
    )
    adata = ad.AnnData(X=np.ones((8, 3), dtype="float32"), obs=obs)

    hints = suggest_design_hints(DataBundle(payload=adata, kind=SC_COUNTS))
    assert hints.needs_design is True
    cand = next(c for c in hints.group_candidates if c.key == "genotype")
    assert {lv.name: lv.n_replicates for lv in cand.levels} == {"WT": 4, "Rd10": 4}   # cells
    assert all(lv.replicate_unit == "cells" for lv in cand.levels)
    assert cand.reference_guess == "WT"


# --- /data/inspect integration ---------------------------------------------------------------------

def test_inspect_carries_design_for_bulk_counts():
    csv = (
        b"gene,Control_1,Control_2,Control_3,Mut_1,Mut_2,Mut_3\n"
        + b"".join(f"g{i},{i},{i+1},{i+2},{i+3},{i+4},{i+5}\n".encode() for i in range(20))
    )
    r = client.post("/data/inspect", files={"matrix": ("counts.csv", csv, "text/csv")})
    assert r.status_code == 200
    design = r.json()["design"]
    assert design["needs_design"] is True
    assert design["source"] == "column_names"
    cand = design["group_candidates"][0]
    assert cand["n_levels"] == 2
    assert {lv["name"] for lv in cand["levels"]} == {"Control", "Mut"}
    assert cand["reference_guess"] == "Control"


def test_inspect_uses_attached_design_sheet_as_source_of_truth():
    # followups #5: an attached sample sheet is the reproducible mis-grouping fix — /data/inspect now
    # threads it into suggest_design_hints so the confirm-card reflects the sheet, not just column names.
    csv = (
        b"gene,s1,s2,s3,s4\n"
        + b"".join(f"g{i},{i},{i + 1},{i + 2},{i + 3}\n".encode() for i in range(20))
    )
    sheet = b"sample,genotype\ns1,WT\ns2,WT\ns3,KO\ns4,KO\n"
    r = client.post(
        "/data/inspect",
        files={
            "matrix": ("counts.csv", csv, "text/csv"),
            "design": ("design.csv", sheet, "text/csv"),
        },
    )
    assert r.status_code == 200
    design = r.json()["design"]
    assert design["source"] == "design_sheet"
    assert design["needs_design"] is True
    cand = design["group_candidates"][0]
    assert {lv["name"] for lv in cand["levels"]} == {"WT", "KO"}


def test_inspect_design_absent_for_de_results():
    r = client.post(
        "/data/inspect",
        files={"matrix": ("de.csv", b"gene,log2FoldChange,padj\nRHO,1.2,0.01\nRPGR,-0.7,0.04\n", "text/csv")},
    )
    assert r.status_code == 200
    design = r.json()["design"]
    assert design["needs_design"] is False
    assert design["group_candidates"] == []
