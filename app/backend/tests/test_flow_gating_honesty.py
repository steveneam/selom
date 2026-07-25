"""FACS gating honesty — the gate SPACE is recorded (A15) and no defined gate vanishes (A16).

Deliberately NOT ``@slow`` (unlike ``test_flow_smoke.py``, which needs flowio/flowutils and is
excluded from ``pytest -m "not slow"``, i.e. from ``scripts/verify.sh``): both invariants here are
about what the code CLAIMS, and a claim guard that never runs in the gate of record is not a
ratchet. The engine-touching half is covered by a tiny synthetic FCS behind ``importorskip``; the
rest is pure functions.

**Real-data limitation, recorded not hidden:** ``SELOM_DATASETS_DIR`` carries no ``.fcs`` file
(verified 2026-07-25 — the corpus has scRNA, bulk DE, ERG and paper assets, no flow cytometry), so
these run against an FCS written by FlowIO's own writer. That is the strongest evidence available
in-tree; a real acquisition is still owed. See ``LANE-WRAP.md``.
"""

from __future__ import annotations

import pytest

from skills import _flow


# --- A16: a gate the operator DEFINED never vanishes -------------------------------------------
# Three silent drops lived on the population-stats path: parse_gates dropped a gate with no
# geometry / <3 vertices / a non-finite split, _gating_rows `continue`d for a channel absent from
# the FCS and again for an unrecognized type, and an unresolved PARENT fell back to the root mask
# so a child's %-parent was silently computed against ALL events. For a table whose counts ARE the
# result, a missing row is a wrong result presented as a complete one.

def test_parse_gates_reports_every_drop_with_a_reason():
    raw = {"gates": [
        {"id": "GOOD", "type": "rect", "x_min": 0.1, "x_max": 0.9},
        {"id": "NOGEOM", "type": "rect"},                                   # no bounds at all
        {"id": "THINPOLY", "type": "polygon", "vertices": [[0, 0], [1, 1]]},  # < 3 vertices
        {"id": "BADQUAD", "type": "quadrant", "x_split": "nope", "y_split": 1},
        {"id": "WEIRD", "type": "ellipse", "x_min": 0.1},                   # unknown type
        "not-an-object",
    ]}
    gates, dropped = _flow.parse_gates(raw, "FITC-A", "PE-A")

    assert [g["id"] for g in gates] == ["GOOD"]
    assert {d["id"]: d["reason"] for d in dropped} == {
        "NOGEOM": _flow.DROP_NO_GEOMETRY,
        "THINPOLY": _flow.DROP_TOO_FEW_VERTICES,
        "BADQUAD": _flow.DROP_NON_FINITE_SPLIT,
        "WEIRD": _flow.DROP_UNKNOWN_TYPE,
        "P6": _flow.DROP_NOT_AN_OBJECT,
    }
    assert all(d["fix"] for d in dropped), "every drop must carry an actionable fix"


def test_parse_gates_still_never_raises():
    """Tolerance is kept — it just stops being silent."""
    assert _flow.parse_gates("{not json") == ([], [])
    assert _flow.parse_gates(None) == ([], [])
    assert _flow.parse_gates("") == ([], [])


def test_population_table_carries_the_status_column():
    rows = [
        {"population": "All events", "parent": None, "count": 10, "pct_parent": 100.0,
         "pct_total": 100.0, "mfi_x": 1.0, "mfi_y": 2.0},
        {"population": "P1", "parent": "All events", "count": None, "pct_parent": None,
         "pct_total": None, "mfi_x": None, "mfi_y": None,
         "status": _flow.DROP_CHANNEL_NOT_IN_FCS},
    ]
    t = _flow.population_table(rows, "FITC-A", "PE-A")
    # the leading columns are unchanged — status is appended
    assert t["columns"][:5] == ["population", "parent", "count", "% parent", "% total"]
    assert t["columns"][-1] == "status"
    assert t["rows"][0][-1] == _flow.GATE_STATUS_OK
    # the unresolved population is a ROW with no count, not an absence
    assert t["rows"][1][0] == "P1" and t["rows"][1][2] is None
    assert t["rows"][1][-1] == _flow.DROP_CHANNEL_NOT_IN_FCS


# --- the engine half (tiny synthetic FCS) -------------------------------------------------------

_CHANNELS = ["FSC-A", "SSC-A", "FITC-A", "PE-A"]


@pytest.fixture()
def fcs_path(tmp_path):
    flowio = pytest.importorskip("flowio")
    pytest.importorskip("flowutils")
    import numpy as np

    rng = np.random.default_rng(0)
    events = np.clip(rng.normal([50000, 20000, 2000, 300], [6000, 4000, 600, 120], (600, 4)),
                     1, 262143).astype(np.float32)
    p = tmp_path / "synth.fcs"
    with open(p, "wb") as fh:
        flowio.create_fcs(fh, events.flatten().tolist(), _CHANNELS)
    return str(p)


def _run(fcs_path, **params):
    from skills.facs_gating.run_real import run

    return run(fcs_path, {"x_channel": "FITC-A", "y_channel": "PE-A", "bins": 32,
                          "max_events": 600, **params})


def _row(figure_table, name):
    return next(r for r in figure_table["rows"] if r[0] == name)


def test_an_unresolvable_channel_is_a_verdict_row_not_a_vanished_population(fcs_path):
    gates = {"gates": [
        {"id": "P1", "type": "rect", "x": "FITC-A", "y": "PE-A", "x_min": 0.0, "x_max": 1.0},
        {"id": "GHOST", "type": "rect", "x": "APC-A", "y": "PE-A", "x_min": 0.0, "x_max": 1.0},
    ]}
    spec = _run(fcs_path, gates=gates)
    names = [r[0] for r in spec["table"]["rows"]]
    assert "GHOST" in names, "a gate naming a channel the FCS lacks must not vanish"
    ghost = _row(spec["table"], "GHOST")
    assert ghost[2] is None                                   # no count claimed
    assert ghost[-1] == _flow.DROP_CHANNEL_NOT_IN_FCS         # ...and it says why
    assert _row(spec["table"], "P1")[2] is not None           # the resolvable gate still counted
    assert spec["layout"]["meta"]["gates_unresolved"] == [
        {"population": "GHOST", "reason": _flow.DROP_CHANNEL_NOT_IN_FCS}]


def test_a_child_of_an_unresolved_gate_is_never_counted_against_all_events(fcs_path):
    """The worst of the three: an unresolved parent fell back to the root mask, so the child's
    %-parent was silently computed against EVERY event — a wrong number presented as a right one."""
    gates = {"gates": [
        {"id": "GHOST", "type": "rect", "x": "APC-A", "y": "PE-A", "x_min": 0.0, "x_max": 1.0},
        {"id": "CHILD", "parent": "GHOST", "type": "rect", "x": "FITC-A", "y": "PE-A",
         "x_min": 0.0, "x_max": 1.0},
    ]}
    spec = _run(fcs_path, gates=gates)
    child = _row(spec["table"], "CHILD")
    assert child[2] is None and child[3] is None              # no count, no %-parent
    assert child[-1] == _flow.DROP_PARENT_UNRESOLVED
    total = _row(spec["table"], "All events")[2]
    assert child[2] != total


def test_a_parse_dropped_gate_also_reaches_the_table(fcs_path):
    spec = _run(fcs_path, gates={"gates": [{"id": "NOGEOM", "type": "rect"}]})
    row = _row(spec["table"], "NOGEOM")
    assert row[2] is None and row[-1] == _flow.DROP_NO_GEOMETRY


# --- A15: the gate space is recorded, and is not data-dependent ----------------------------------

def test_transform_provenance_is_recorded_from_the_fcs_metadata(fcs_path):
    xf = _run(fcs_path)["layout"]["meta"]["transform"]
    assert xf["name"] == "logicle"
    assert xf["t_source"] == "fcs_pnr"                        # NOT the data's max |value|
    assert set(xf["t_per_channel"]) == set(_CHANNELS)
    assert set(xf["t_per_channel"].values()) == {262144.0}    # each channel's declared $PnR
    assert (xf["m"], xf["w"], xf["a"]) == (4.5, 0.5, 0.0)     # reconstructible shape params


def test_an_outlier_event_no_longer_moves_the_whole_gate_space(tmp_path):
    """The defect, run directly: t used to be max|event|, so ONE saturating event rescaled every
    channel and therefore every count, %-parent and MFI in the table."""
    flowio = pytest.importorskip("flowio")
    pytest.importorskip("flowutils")
    import numpy as np

    rng = np.random.default_rng(1)
    base = np.clip(rng.normal([5000, 4000, 2000, 300], [500, 400, 200, 60], (400, 4)),
                   1, 262143).astype(np.float32)
    spiked = base.copy()
    spiked[0] = [262143, 262143, 262143, 262143]              # one saturating event

    paths = []
    for name, ev in (("clean.fcs", base), ("spiked.fcs", spiked)):
        p = tmp_path / name
        with open(p, "wb") as fh:
            flowio.create_fcs(fh, ev.flatten().tolist(), _CHANNELS)
        paths.append(str(p))

    gates = {"gates": [{"id": "P1", "type": "rect", "x": "FITC-A", "y": "PE-A",
                        "x_min": 0.0, "x_max": 0.5, "y_min": 0.0, "y_max": 0.5}]}
    a, b = (_run(p, gates=gates) for p in paths)
    assert a["layout"]["meta"]["transform"]["t_per_channel"] == \
        b["layout"]["meta"]["transform"]["t_per_channel"]
    # the shared events fall in the same place, so the count differs by at most the spiked event
    ca, cb = _row(a["table"], "P1")[2], _row(b["table"], "P1")[2]
    assert abs(ca - cb) <= 1, (ca, cb)


def test_transform_t_can_be_pinned_so_a_gate_spec_is_portable(fcs_path):
    xf = _run(fcs_path, transform_t=65536.0)["layout"]["meta"]["transform"]
    assert xf["t_source"] == "param"
    assert set(xf["t_per_channel"].values()) == {65536.0}


def test_arcsinh_does_not_claim_a_t_it_never_used(fcs_path):
    xf = _run(fcs_path, transform="arcsinh", cofactor=150.0)["layout"]["meta"]["transform"]
    assert xf["t_source"] == "not_applicable" and xf["t_per_channel"] == {}
    assert xf["cofactor"] == 150.0


# --- the methods prose says the same thing the figure does --------------------------------------

def test_methods_states_the_gate_space_and_the_uncounted_populations(fcs_path):
    from companions import methods
    from skills.registry import load_skill

    gates = {"gates": [
        {"id": "P1", "type": "rect", "x": "FITC-A", "y": "PE-A", "x_min": 0.0, "x_max": 1.0},
        {"id": "GHOST", "type": "rect", "x": "APC-A", "y": "PE-A", "x_min": 0.0, "x_max": 1.0},
    ]}
    figure = _run(fcs_path, gates=gates)
    text, _cites = methods.build_body(load_skill("facs_gating"), {"gates": gates}, figure=figure)

    assert "top of scale T = 262144" in text
    assert "$PnR" in text                                    # where t came from
    assert "m = 4.5" in text and "w = 0.5" in text            # the reconstructible shape
    assert "could NOT be evaluated" in text and "GHOST" in text


def test_methods_omits_the_clause_when_replaying_from_params_only():
    """litsynth replays recorded params with no figure — the prose must not invent a gate space."""
    from companions import methods
    from skills.registry import load_skill

    text, _ = methods.build_body(load_skill("facs_gating"), {"transform": "logicle"})
    assert "top of scale" not in text and "could NOT be evaluated" not in text
