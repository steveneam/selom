"""Flow-cytometry gating & population stats — two engines behind one entrypoint.

STUB (this file) = a dependency-free, deterministic synthetic view: a two-blob 2-D
density in transformed [0,1] display space, one rectangle gate drawn over the lower
blob, and a fixed three-row population table. Golden-stable, zero heavy deps.

REAL (``run_real``) loads the FCS via FlowIO, compensates + transforms with FlowUtils,
renders the chosen ``plot`` as editable Plotly, evaluates the gate tree in clean-room
numpy, and attaches the population StatsTable. Both go through the shared,
dependency-free ``skills._flow`` builders so the wire shape is identical.
"""
import math

from skills import _flow
from skills._engine import use_real_engine

# The stub's fixed display channels + transform (a realistic CD-marker dot-plot).
_X_LABEL, _Y_LABEL = "FITC-A", "PE-A"


def run(data_path: str, params: dict) -> dict:
    # FlowIO + FlowUtils (both BSD-3, numpy-only) run on pandas 3.0, so the real engine is a
    # first-class, shared-venv engine gated like every other skill — covered by the WS1.1 prod
    # boot guard + honest provenance (unlike the retired FlowKit sidecar plan; RISKS #12).
    if use_real_engine("flowio", "flowutils"):
        from skills.facs_gating.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _blob(cx, cy, sx, sy, n, seed):
    """Deterministic gaussian-ish point cloud (LCG + Box-Muller) in [0,1] display space.

    Pure stdlib so the stub stays dependency-free and byte-for-byte reproducible — the
    golden pins the exact points, so the density bins are stable across runs/machines.
    """
    xs, ys = [], []
    state = seed & 0x7FFFFFFF
    for _ in range(n):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        u1 = max(state / 0x7FFFFFFF, 1e-9)
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        u2 = state / 0x7FFFFFFF
        r = math.sqrt(-2.0 * math.log(u1))
        xs.append(round(min(max(cx + sx * r * math.cos(2 * math.pi * u2), 0.0), 1.0), 4))
        ys.append(round(min(max(cy + sy * r * math.sin(2 * math.pi * u2), 0.0), 1.0), 4))
    return xs, ys


def _stub_figure(params: dict) -> dict:
    # Two populations: a lower-left blob (the gated P1) and an upper-right blob.
    ax, ay = _blob(0.35, 0.34, 0.07, 0.07, 500, seed=11)
    bx, by = _blob(0.70, 0.72, 0.08, 0.08, 500, seed=29)
    x, y = ax + bx, ay + by

    bins = int(params.get("bins", 256) or 256)
    spec = {"data": [_flow.density_trace(x, y, bins)],
            "layout": _flow.figure_layout("density", _X_LABEL, _Y_LABEL,
                                          "Flow cytometry — gated density (stub)", "logicle")}

    # One rectangle gate over the lower-left blob.
    gates, _dropped = _flow.parse_gates(
        {"gates": [{"id": "P1", "type": "rect", "x": _X_LABEL, "y": _Y_LABEL,
                    "x_min": 0.20, "x_max": 0.52, "y_min": 0.20, "y_max": 0.52,
                    "label": "P1"}]},
        _X_LABEL, _Y_LABEL)
    shapes, annos = _flow.gate_shapes(gates, _X_LABEL, _Y_LABEL)
    spec["layout"]["shapes"] = shapes
    spec["layout"]["annotations"] = annos

    rows = [
        {"population": "All events", "parent": None, "count": 1000,
         "pct_parent": 100.0, "pct_total": 100.0, "mfi_x": 0.53, "mfi_y": 0.53},
        {"population": "P1", "parent": "All events", "count": 500,
         "pct_parent": 50.0, "pct_total": 50.0, "mfi_x": 0.35, "mfi_y": 0.34},
        {"population": "P1 / high", "parent": "P1", "count": 128,
         "pct_parent": 25.6, "pct_total": 12.8, "mfi_x": 0.41, "mfi_y": 0.40},
    ]
    spec["table"] = _flow.population_table(rows, _X_LABEL, _Y_LABEL,
                                           title="Population statistics (stub)")
    return spec
