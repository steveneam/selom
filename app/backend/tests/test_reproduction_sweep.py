"""Reproduction Engine R3 — the threshold/contrast sweep (loop stage 9, guard 1).

Pure-Python; codifies the manual ``fig5_sweep*.py``. Covers the per-contrast count gate,
finding the authors' *unstated* setting, proving a printed number irreproducible (the
Fig 5 headline → paper-irreproducible), the down-in-both intersection (the 49 case), and
the ``methods_vs_numbers`` inconsistency wiring onto the ledger.
"""

import reproduction as R  # noqa: F401 — kept for symmetry with the oracle suite
import sweep as S
from reproduction import Golden, Ledger, Panel, Paper

UNI = ["g1", "g2", "g3", "g4", "g5", "g6"]


def _rows_a():
    # universe g1..g6 — (gene, padj, p, lfc)
    return [
        {"gene": "g1", "padj": 0.20, "p": 0.010, "lfc": -2.0},
        {"gene": "g2", "padj": 0.30, "p": 0.020, "lfc": -1.0},
        {"gene": "g3", "padj": 0.01, "p": 0.001, "lfc": 3.0},
        {"gene": "g4", "padj": 0.60, "p": 0.200, "lfc": 0.5},
        {"gene": "g5", "padj": 0.80, "p": 0.600, "lfc": -0.2},
        {"gene": "g6", "padj": 0.04, "p": 0.005, "lfc": 2.0},
    ]


def test_signature_count_gate():
    rows = _rows_a()
    assert S.signature_count(rows, UNI, stat="padj", thr=0.05) == 2          # g3, g6
    assert S.signature_count(rows, UNI, stat="p", thr=0.05) == 4             # g1,g2,g3,g6
    assert S.signature_count(rows, UNI, stat="p", thr=0.05, direction="down") == 2  # g1,g2
    assert S.signature_count(rows, UNI, stat="p", thr=0.05, lfc_min=1.0) == 4  # |lfc|>=1 all 4
    # universe restriction (SOP rule 3): a significant gene outside the universe is excluded.
    assert S.signature_count(rows, ["g3"], stat="p", thr=0.05) == 1


def test_sweep_finds_unstated_setting():
    # The printed count reproduces only at an unstated threshold, not the stated method.
    sweep, inc = S.run_sweep(
        "5sig", "signature", 4, {"A": _rows_a()}, UNI,
        contrast="A", stated_setting={"stat": "padj", "thr": 0.05},
    )
    assert sweep.irreproducible is False
    assert sweep.reproducing_setting["stat"] == "p"
    assert sweep.reproducing_setting["thr"] == 0.05
    assert sweep.stated_value == 2  # stated padj<0.05 yields 2, not the printed 4
    assert inc is not None and inc.kind == "methods_vs_numbers"


def test_sweep_proves_irreproducible():
    # The Fig 5 shape: the printed count is unreachable at ANY swept setting.
    sweep, inc = S.run_sweep(
        "5sig", "signature", 5, {"A": _rows_a()}, UNI,
        contrast="A", stated_setting={"stat": "padj", "thr": 0.05},
    )
    assert sweep.irreproducible is True
    assert sweep.reproducing_setting is None
    assert inc is not None and inc.kind == "methods_vs_numbers"


def test_sweep_down_in_both_intersection():
    a = _rows_a()
    b = [
        {"gene": "g1", "padj": 0.5, "p": 0.30, "lfc": -0.1},
        {"gene": "g2", "padj": 0.5, "p": 0.01, "lfc": -1.5},
        {"gene": "g3", "padj": 0.5, "p": 0.20, "lfc": 1.0},
        {"gene": "g4", "padj": 0.5, "p": 0.40, "lfc": 0.2},
        {"gene": "g5", "padj": 0.5, "p": 0.02, "lfc": -0.8},
        {"gene": "g6", "padj": 0.5, "p": 0.50, "lfc": 0.3},
    ]
    # down-in-both at p<0.05: A_down={g1,g2}, B_down={g2,g5} -> {g2} = 1
    sweep, inc = S.run_sweep(
        "5dn", "down_both", 1, {"A": a, "B": b}, UNI,
        intersect=("A", "B"),
        stated_setting={"stat": "p", "thr": 0.05, "direction": "down"},
    )
    assert sweep.irreproducible is False
    assert sweep.reproducing_setting is not None
    assert inc is None  # the stated method reproduces it -> no inconsistency


def test_sweep_panel_wires_ledger():
    panel = Panel(paper_id="rpgrip1", figure="5", panel="sig", skill_id="deg",
                  golden=[Golden(metric="signature", value=5)])
    ledger = Ledger(paper=Paper(id="rpgrip1", slug="rpgrip1"), panels=[panel])
    sweep = S.sweep_panel(ledger, panel, "signature", {"A": _rows_a()}, UNI,
                          contrast="A", stated_setting={"stat": "padj", "thr": 0.05})
    assert ledger.sweeps and ledger.sweeps[0] is sweep
    assert len(ledger.paper.inconsistencies) == 1
    assert sweep.inconsistency_ref == 0
    assert panel.golden[0].inconsistency_ref == 0
