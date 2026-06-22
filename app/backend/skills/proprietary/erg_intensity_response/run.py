"""ERG intensity-response — b-wave vs flash intensity per condition, with a Naka-Rushton
saturating fit overlaid (V = Vmax·Iⁿ/(Iⁿ+Kⁿ)). Proprietary ERG module (spec R23).

Stub = a dependency-free figure built from known Naka-Rushton parameters per condition, so
the curve + golden are deterministic and need no scipy. Real path (``run_real``) aggregates
the long ``erg_metrics_long`` table per (condition × intensity) and fits each condition with
``_erg.naka_rushton_fit`` (scipy). Both go through the shared ``ir_spec`` builder, which
samples the same ``_erg.naka_rushton`` forward to draw the fit line and returns the rows for
the native Vmax/K/n Statistics table.
"""
from skills import _erg
from skills._table import table

_ORDER = _erg.CONDITION_ORDER

# Stub Naka-Rushton params per condition (Vmax µV, logK log cd·s/m², n) — illustrative,
# ordered Control ≫ 3'UTR > PDE6B > flats. The stub samples these exactly (no noise), so r²=1.
_STUB_NR = {
    "Control": (210.0, 0.0, 0.9),
    "Untreated": (44.0, 1.5, 0.7),
    "AAV8-RK-PDE6B": (95.0, 1.2, 0.8),
    "AAV8-RK-GFP-polyA-stuffer": (38.0, 1.6, 0.7),
    "AAV8-CMV-GFP": (42.0, 1.5, 0.7),
    "AAV8-RK-PDE6B-3UTR": (140.0, 0.8, 0.85),
}


def run(data_path: str, params: dict) -> dict:
    from skills._engine import use_real_engine

    if use_real_engine("pandas", "numpy"):
        from skills.proprietary.erg_intensity_response.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def ir_spec(cond_series, fits, *, title: str,
            value_label: str = "b-wave amplitude (µV)"):
    """Editable intensity-response spec (shared by stub + real).

    ``cond_series`` = ordered list of ``(condition, xs_log, ys_mean, sems)``; ``fits`` =
    ``{condition: {vmax, log_k, n, r2} | None}``. Per condition: a markers+SEM scatter of the
    means and (where a fit exists) a smooth Naka-Rushton line sampled from ``_erg.naka_rushton``.
    Returns ``(spec, table_rows)`` with rows ``[condition, Vmax, logK, n, R²]`` for the native table.
    """
    all_x = [x for (_c, xs, _y, _s) in cond_series for x in xs]
    xlo, xhi = (min(all_x), max(all_x)) if all_x else (0.0, 1.0)
    grid = [round(xlo + (xhi - xlo) * k / 80.0, 3) for k in range(81)]

    data, tbl_rows = [], []
    for cond, xs, ys, sems in cond_series:
        color = _erg.COLORS.get(cond, "#888888")
        label = _erg.COL_LABELS.get(cond, cond).replace("<br>", " ")
        data.append({
            "type": "scatter", "mode": "markers", "x": [round(float(x), 3) for x in xs],
            "y": [round(float(v), 2) for v in ys],
            "error_y": {"type": "data", "array": [round(float(s), 2) for s in sems],
                        "visible": True, "thickness": 1, "width": 3, "color": color},
            "marker": {"color": color, "size": 7, "line": {"color": "#ffffff", "width": 0.6}},
            "name": label, "legendgroup": cond, "hoverinfo": "x+y+name",
        })
        f = fits.get(cond)
        if f:
            line_y = [round(_erg.naka_rushton(x, f["vmax"], f["log_k"], f["n"]), 2) for x in grid]
            data.append({
                "type": "scatter", "mode": "lines", "x": grid, "y": line_y,
                "line": {"color": color, "width": 1.6}, "name": f"{label} (fit)",
                "legendgroup": cond, "showlegend": False, "hoverinfo": "skip",
            })
            n_cell = f"{f['n']} (fixed)" if f.get("fixed") else f["n"]
            tbl_rows.append([cond, f["vmax"], f["log_k"], n_cell, f["r2"]])
        else:
            tbl_rows.append([cond, "—", "—", "—", "—"])

    layout = {
        "title": {"text": title},
        "xaxis": {"title": {"text": "flash intensity (log cd·s/m²)"}},
        "yaxis": {"title": {"text": value_label}, "rangemode": "tozero"},
        "legend": {"title": {"text": "condition"}},
        "showlegend": True, "plot_bgcolor": "white",
    }
    return {"data": data, "layout": layout}, tbl_rows


def _stub_figure(params: dict) -> dict:
    do_fit = str(params.get("fit", True)).lower() not in ("false", "0", "no")
    cond_series, fits = [], {}
    for cond in _ORDER:
        vmax, log_k, n = _STUB_NR[cond]
        xs = list(_erg.INTENSITIES_LOG)
        ys = [round(_erg.naka_rushton(x, vmax, log_k, n), 2) for x in xs]
        sems = [round(vmax * 0.07, 2)] * len(xs)
        cond_series.append((cond, xs, ys, sems))
        fits[cond] = {"vmax": vmax, "log_k": log_k, "n": n, "r2": 1.0} if do_fit else None
    spec, tbl_rows = ir_spec(cond_series, fits, title="b-wave intensity-response (stub)")
    spec["table"] = table(
        ["condition", "Vmax (µV)", "log K (cd·s/m²)", "n", "R²"], tbl_rows,
        title="Naka-Rushton fit")
    return spec
