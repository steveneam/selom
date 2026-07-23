"""Clean-room real-engine smoke test for the ``facs_gating`` skill (heavy lane).

@slow + skip-if-flowio/flowutils-missing, so the fast contract gate never needs the
science stack. Uses a tiny synthetic FCS written with FlowIO (CI-safe, no proprietary
sample needed). Exercises the real path end to end: FCS load → compensate/transform →
each Plotly view → the clean-room gate tree → the population StatsTable
(count / %parent / %total / median MFI). The engine runs in-process on pandas 3.0 via
FlowIO + FlowUtils (no FlowKit — RISKS #12).
"""

import numpy as np
import pytest

pytestmark = pytest.mark.slow

flowio = pytest.importorskip("flowio")
flowutils = pytest.importorskip("flowutils")

from skills.contract import run_skill_with_table  # noqa: E402

_CHANNELS = ["FSC-A", "SSC-A", "FITC-A", "PE-A"]


def _synthetic_fcs(path):
    """Two Gaussian blobs across four channels → a minimal valid FCS via FlowIO."""
    rng = np.random.default_rng(0)
    n = 1500
    b1 = rng.normal([50000, 20000, 2000, 300], [6000, 4000, 600, 120], (n, 4))
    b2 = rng.normal([80000, 60000, 300, 8000], [7000, 6000, 120, 900], (n, 4))
    events = np.clip(np.vstack([b1, b2]), 1, 262143).astype(np.float32)
    with open(path, "wb") as fh:
        flowio.create_fcs(fh, events.flatten().tolist(), _CHANNELS)
    return str(path)


@pytest.fixture()
def fcs_path(tmp_path):
    return _synthetic_fcs(tmp_path / "synth.fcs")


@pytest.fixture(autouse=True)
def _force_real(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "real")


def _run(fcs_path, params):
    return run_skill_with_table("facs_gating", fcs_path, params)


def test_density_with_rectangle_gate(fcs_path):
    gates = '{"gates": [{"id": "P1", "type": "rect", "x": "FITC-A", "y": "PE-A",' \
            ' "x_min": 0.0, "x_max": 1.0, "y_min": 0.0, "y_max": 1.0, "label": "P1"}]}'
    figure, table = _run(fcs_path, {"x_channel": "FITC-A", "y_channel": "PE-A",
                                    "plot": "density", "gates": gates})
    # editable Plotly + the gate shape drawn
    assert figure["data"] and figure["data"][0]["type"] == "histogram2d"
    assert any(s.get("type") == "rect" for s in figure["layout"].get("shapes", []))
    # population table: root + the gate, with the stat columns
    assert table is not None
    assert table["columns"][:5] == ["population", "parent", "count", "% parent", "% total"]
    names = [r[0] for r in table["rows"]]
    assert "All events" in names and "P1" in names
    p1 = next(r for r in table["rows"] if r[0] == "P1")
    total = next(r for r in table["rows"] if r[0] == "All events")
    assert p1[2] == total[2]           # full-range gate captures every event
    assert p1[3] == pytest.approx(100.0)  # % parent
    assert p1[5] is not None           # median MFI computed on compensated events


@pytest.mark.parametrize("transform", ["logicle", "arcsinh", "log", "linear"])
def test_transforms_render(fcs_path, transform):
    figure, _ = _run(fcs_path, {"plot": "density", "transform": transform, "bins": 64})
    assert figure["data"] and isinstance(figure["layout"], dict)


@pytest.mark.parametrize("plot", ["density", "contour", "histogram", "scatter"])
def test_every_plot_kind(fcs_path, plot):
    figure, _ = _run(fcs_path, {"plot": plot, "max_events": 2000, "bins": 64})
    assert figure["data"], f"{plot} produced no trace"


def test_quadrant_gate_reports_four_populations(fcs_path):
    gates = '{"gates": [{"id": "Q1", "type": "quadrant", "x": "FITC-A", "y": "PE-A",' \
            ' "x_split": 0.4, "y_split": 0.4}]}'
    figure, table = _run(fcs_path, {"x_channel": "FITC-A", "y_channel": "PE-A",
                                    "plot": "scatter", "max_events": 2000, "gates": gates})
    # quadrant crosshair drawn as two lines
    assert sum(1 for s in figure["layout"].get("shapes", []) if s.get("type") == "line") == 2
    quad_rows = [r for r in table["rows"] if str(r[0]).startswith("Q1-")]
    assert len(quad_rows) == 4
    assert sum(int(r[2]) for r in quad_rows) == next(
        int(r[2]) for r in table["rows"] if r[0] == "All events")


def test_operator_compensation_matrix(fcs_path):
    comp = '{"detectors": ["FITC-A", "PE-A"], "matrix": [[1, 0.15], [0.08, 1]]}'
    figure, table = _run(fcs_path, {"x_channel": "FITC-A", "y_channel": "PE-A",
                                    "compensate": "matrix", "comp_matrix": comp})
    assert figure["data"] and table is not None
