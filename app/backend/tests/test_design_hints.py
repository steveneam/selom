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


def test_inspect_design_absent_for_de_results():
    r = client.post(
        "/data/inspect",
        files={"matrix": ("de.csv", b"gene,log2FoldChange,padj\nRHO,1.2,0.01\nRPGR,-0.7,0.04\n", "text/csv")},
    )
    assert r.status_code == 200
    design = r.json()["design"]
    assert design["needs_design"] is False
    assert design["group_candidates"] == []
