"""ERG b-wave bar — group mean ± SEM per condition at one flash intensity, with every
eye overlaid as an individual data point (Reviewer 2: "include individual data points in
all quantitative graphs"). Proprietary ERG module (docs/records/erg-module/spec.md, R22).

Stub = a dependency-free bar seeded from the real Group-4 (log 1.0 cd·s/m²) reference
b-waves, so the golden figure is shape-faithful. Real path (``run_real``) reads the long
``erg_metrics_long`` table. Both go through the shared ``bar_spec`` builder here (pure
Python, no numpy/pandas), which also returns the rows for the native Statistics table.
"""
from skills import _charts, _erg
from skills._table import table

# Display order — the Fig 1E condition order shared with the trace grid.
_ORDER = _erg.CONDITION_ORDER

# Stub per-condition b-waves at Group4 (log 1.0), the QC-clean reference eyes
# (selection_report_v2; the cataract 3'UTR eye 251 already dropped). Deterministic.
_STUB_VALS = {
    "Control": [214.5, 195.1, 209.9, 232.2, 191.2, 200.4, 184.4, 237.0],
    "Untreated": [42.4, 33.5, 51.7, 42.8],
    "AAV8-RK-PDE6B": [22.2, 107.3, 41.0, 102.1, 99.1, 106.4, 118.5],
    "AAV8-RK-GFP-polyA-stuffer": [30.7, 28.4, 58.4],
    "AAV8-CMV-GFP": [22.1, 41.8, 23.8, 62.0],
    "AAV8-RK-PDE6B-3UTR": [123.7, 187.0, 130.0],
}


def run(data_path: str, params: dict) -> dict:
    from skills._engine import use_real_engine

    if use_real_engine("pandas"):
        from skills.proprietary.erg_bwave_bar.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


# Per-condition hatch pattern (the Fig 1E look) — solid for Control + the 3'UTR rescue, hatched for
# the rest, mirroring the GraphPad figure. Passed to the generic builder; other conditions cycle.
_PATTERN = {
    "Control": "", "Untreated": ".", "AAV8-RK-PDE6B": "x",
    "AAV8-RK-GFP-polyA-stuffer": "/", "AAV8-CMV-GFP": "\\", "AAV8-RK-PDE6B-3UTR": "",
}


def bar_spec(cond_values, *, intensity_label: str, title: str, unit: str = "µV",
             factor: float = 1.0, show_points: bool = True, wave_label: str = "b-wave",
             error: str = "sem", show_error: bool = True, bar_fill: str = "filled",
             comparisons=None, sig_test: str = "welch", correction: str = "none",
             hline=None, hline_label: str = "", vline=None, vline_label: str = "",
             legend: bool = False):
    """ERG a/b-wave bar — a thin wrapper over the generic :func:`skills._charts.bar_figure` that
    supplies the ERG condition colours/labels/hatch patterns and the display-unit rounder. The full
    styling vocabulary (``error``/``show_error``/``bar_fill``/``comparisons``/``hline``/``vline``/
    ``legend``) is the generic one — identical for any bar skill. ``cond_values`` = ordered
    ``[(condition, [values])]``; returns ``(spec, table_rows=[condition, n, mean, err])``. The
    default (filled · sem · no brackets/line/legend) is byte-identical to the original look."""
    return _charts.bar_figure(
        cond_values, y_title=f"{wave_label} amplitude ({unit})", title=title,
        colors=_erg.COLORS, labels=_erg.COL_LABELS, patterns=_PATTERN,
        error=error, show_error=show_error, points=show_points, point_name="eyes",
        bar_fill=bar_fill, comparisons=comparisons, sig_test=sig_test, correction=correction,
        hline=hline, hline_label=hline_label, vline=vline, vline_label=vline_label,
        legend=legend, caption=intensity_label,
        round_fn=lambda v: _erg.disp_round(v, factor))


def _stub_figure(params: dict) -> dict:
    show_points = str(params.get("points", True)).lower() not in ("false", "0", "no")
    cond_values = [(c, _STUB_VALS[c]) for c in _ORDER]
    spec, tbl_rows = bar_spec(cond_values, intensity_label="1.0 log cd·s/m²",
                              title="Scotopic b-wave by condition (stub)", show_points=show_points)
    spec["table"] = table(["condition", "n (eyes)", "mean b-wave (µV)", "SEM (µV)"],
                          tbl_rows, title="ERG b-wave (mean ± SEM)")
    return spec
