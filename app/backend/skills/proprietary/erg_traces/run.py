"""ERG representative trace grid — stacked floating waveforms (flash intensity down the
rows × condition across the columns), no per-panel axes, one shared scale bar. The
publication layout Prism/Excel can't make. Proprietary (docs/records/erg-module/spec.md).

Stub = a dependency-free synthetic 7×6 grid (golden-stable). Real path
(``run_real``) reads a long ERG waveform table and renders the chosen representatives.
Both go through the generic ``_tracegrid`` primitive.
"""
import math

from skills import _erg
from skills._engine import use_real_engine
from skills._table import table
from skills._tracegrid import grid_spec

# Relative b-wave size per condition for the synthetic stub (Control ≫ 3'UTR > PDE6B > flats).
_COND_AMP = {
    "Control": 1.0,
    "Untreated": 0.10,
    "AAV8-RK-PDE6B": 0.34,
    "AAV8-RK-GFP-polyA-stuffer": 0.09,
    "AAV8-CMV-GFP": 0.09,
    "AAV8-RK-PDE6B-3UTR": 0.62,
}


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas", "numpy"):
        from skills.proprietary.erg_traces.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _wave(t: float, amp: float) -> float:
    """Synthetic scotopic waveform: a negative a-wave (~40 ms) + a positive b-wave (~95 ms)."""
    a = math.exp(-((t - 40.0) / 10.0) ** 2)
    b = math.exp(-((t - 95.0) / 26.0) ** 2)
    return round(amp * (118.0 * b - 42.0 * a), 2)


def _stub_figure(params: dict) -> dict:
    times = list(range(0, 301, 10))
    panels, rows_tbl = [], []
    for col, cond in enumerate(_erg.CONDITION_ORDER):
        base = _COND_AMP[cond]
        for row in range(7):
            amp = base * (0.22 + 0.78 * (row / 6.0))  # brighter flashes (lower rows) bigger
            panels.append({
                "row": row, "col": col, "x": times,
                "y": [_wave(t, amp) for t in times],
                "color": _erg.COLORS[cond], "name": f"{cond} g{row + 1}", "group": cond,
            })
            rows_tbl.append([cond, _erg.INTENSITIES_LOG[row],
                             round(118.0 * amp, 1), round(42.0 * amp, 1)])

    spec = grid_spec(
        panels, nrows=7, ncols=6,
        scalebar={"x_len": float(params.get("scale_ms", 100.0)), "x_unit": "ms",
                  "y_len": float(params.get("scale_uv", 200.0)), "y_unit": "µV"},
        row_labels=[str(v) for v in _erg.INTENSITIES_LOG],
        col_labels=[_erg.COL_LABELS[c] for c in _erg.CONDITION_ORDER],
        title="ERG representative traces (stub)",
    )
    spec["table"] = table(
        ["condition", "intensity (log cd·s/m²)", "b-wave (µV)", "a-wave (µV)"],
        rows_tbl, title="ERG a/b-wave (stub)")
    return spec
