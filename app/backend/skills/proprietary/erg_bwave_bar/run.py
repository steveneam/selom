"""ERG b-wave bar — group mean ± SEM per condition at one flash intensity, with every
eye overlaid as an individual data point (Reviewer 2: "include individual data points in
all quantitative graphs"). Proprietary ERG module (docs/erg-module/spec.md, R22).

Stub = a dependency-free bar seeded from the real Group-4 (log 1.0 cd·s/m²) reference
b-waves, so the golden figure is shape-faithful. Real path (``run_real``) reads the long
``erg_metrics_long`` table. Both go through the shared ``bar_spec`` builder here (pure
Python, no numpy/pandas), which also returns the rows for the native Statistics table.
"""
from skills import _erg
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


def _jitter(center: int, n: int, width: float = 0.34) -> list[float]:
    """Deterministic horizontal spread of n points around an integer bar position
    (no RNG, so the golden is stable)."""
    if n <= 1:
        return [float(center)]
    step = width / (n - 1)
    return [center - width / 2.0 + k * step for k in range(n)]


def bar_spec(cond_values, *, intensity_label: str, title: str, unit: str = "µV",
             factor: float = 1.0, show_points: bool = True):
    """Editable bar spec (shared by stub + real). ``cond_values`` = ordered list of
    ``(condition, [values])``. ``unit``/``factor`` set the display unit (default µV, factor
    1.0 → byte-identical): the bar means, SEMs, overlaid eye points, table, and y-axis title
    all rescale together. Returns ``(spec, table_rows)`` where ``spec`` is a pure
    ``{data, layout}`` (one bar trace of means + error_y SEM, one overlaid points trace)
    and ``table_rows`` are ``[condition, n, mean, SEM]`` for the native Statistics table."""
    value_label = f"b-wave amplitude ({unit})"
    positions = list(range(len(cond_values)))
    means, sems, colors, ticktext, tbl_rows = [], [], [], [], []
    pt_x, pt_y = [], []
    for i, (cond, vals) in enumerate(cond_values):
        st = _erg.summary_stats(vals)
        mean, sem = _erg.disp_round(st["mean"], factor), _erg.disp_round(st["sem"], factor)
        means.append(mean)
        sems.append(sem)
        colors.append(_erg.COLORS.get(cond, "#888888"))
        ticktext.append(_erg.COL_LABELS.get(cond, cond))
        tbl_rows.append([cond, st["n"], mean, sem])
        if show_points:
            for x, v in zip(_jitter(i, len(vals)), vals):
                pt_x.append(round(x, 4))
                pt_y.append(_erg.disp_round(v, factor))

    data = [{
        "type": "bar", "x": positions, "y": means,
        "error_y": {"type": "data", "array": sems, "visible": True,
                    "thickness": 1.2, "width": 6, "color": "#333333"},
        "marker": {"color": colors, "line": {"color": "#333333", "width": 1}},
        "width": 0.62, "name": "mean ± SEM", "showlegend": False, "hoverinfo": "x+y",
    }]
    if show_points and pt_x:
        data.append({
            "type": "scatter", "mode": "markers", "x": pt_x, "y": pt_y,
            "marker": {"color": "rgba(20,20,20,0.82)", "size": 6,
                       "line": {"color": "#ffffff", "width": 0.8}},
            "name": "eyes", "showlegend": False, "hoverinfo": "y",
        })

    layout = {
        "title": {"text": title},
        "xaxis": {"tickmode": "array", "tickvals": positions, "ticktext": ticktext,
                  "type": "linear", "range": [-0.6, len(cond_values) - 0.4], "tickangle": -20},
        "yaxis": {"title": {"text": value_label}, "zeroline": True, "rangemode": "tozero"},
        "bargap": 0.35, "showlegend": False, "plot_bgcolor": "white",
        "annotations": [{"xref": "paper", "yref": "paper", "x": 0.99, "y": 0.99,
                         "xanchor": "right", "yanchor": "top", "showarrow": False,
                         "text": intensity_label, "font": {"size": 11, "color": "#555555"}}],
    }
    return {"data": data, "layout": layout}, tbl_rows


def _stub_figure(params: dict) -> dict:
    show_points = str(params.get("points", True)).lower() not in ("false", "0", "no")
    cond_values = [(c, _STUB_VALS[c]) for c in _ORDER]
    spec, tbl_rows = bar_spec(cond_values, intensity_label="1.0 log cd·s/m²",
                              title="Scotopic b-wave by condition (stub)", show_points=show_points)
    spec["table"] = table(["condition", "n (eyes)", "mean b-wave (µV)", "SEM (µV)"],
                          tbl_rows, title="ERG b-wave (mean ± SEM)")
    return spec
