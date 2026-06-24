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
from skills._charts import band_traces, point_markers
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


def ir_spec(cond_series, fits, *, title: str, unit: str = "µV", factor: float = 1.0,
            spread: str = "error_bars", points: bool = True, band_alpha: float = 0.25,
            boundary: str = "none", band_color: str | None = None):
    """Editable intensity-response spec (shared by stub + real).

    ``cond_series`` = ordered list of ``(condition, xs_log, ys_mean, lowers, uppers, errs, pts)``,
    where ``lowers``/``uppers`` are the per-intensity spread bounds (µV), ``errs`` the symmetric
    magnitude, and ``pts`` the individual ``(x, value)`` data points (empty for the stub). ``fits`` =
    ``{condition: {vmax, log_k, n, r2} | None}``. Per condition: the mean b-wave at each intensity as
    markers + (where a fit exists) a smooth Naka-Rushton line sampled from ``_erg.naka_rushton``.

    Styling vocabulary shared with the bar + trace grid (``skills._charts``): ``spread``
    (error_bars|band|both|none — band via :func:`band_traces`, error bars on the mean markers),
    ``points`` (overlay every eye's individual amplitude via :func:`point_markers` — the reviewer's
    "individual data points in all quantitative graphs"), ``band_alpha``/``boundary``/``band_color``.
    ``unit``/``factor`` set the b-wave display unit (default µV, factor 1.0 → byte-identical): the
    amplitudes, spread, points, fit line, and Vmax all rescale together. Returns ``(spec, table_rows)``
    with rows ``[condition, Vmax, logK, n, R²]`` for the native table."""
    value_label = f"b-wave amplitude ({unit})"
    all_x = [x for (_c, xs, *_rest) in cond_series for x in xs]
    xlo, xhi = (min(all_x), max(all_x)) if all_x else (0.0, 1.0)
    grid = [round(xlo + (xhi - xlo) * k / 80.0, 3) for k in range(81)]
    spread = str(spread or "error_bars").lower()

    def dr(v):
        return _erg.disp_round(v, factor)

    data, tbl_rows = [], []
    for cond, xs, ys, lowers, uppers, errs, pts in cond_series:
        color = _erg.COLORS.get(cond, "#888888")
        label = _erg.COL_LABELS.get(cond, cond).replace("<br>", " ")
        xr = [round(float(x), 3) for x in xs]
        # Shaded ± spread band behind the markers (skipped when zero-width, e.g. every intensity n<2).
        if spread in ("band", "both") and any(u != lo for lo, u in zip(lowers, uppers)):
            data += band_traces(xr, [dr(v) for v in lowers], [dr(v) for v in uppers],
                                color=band_color or color, alpha=band_alpha, boundary=boundary,
                                legendgroup=cond)
        # Every eye's individual amplitude as points (reviewer ask), behind the mean markers.
        if points and pts:
            data += point_markers([([round(float(x), 3) for x, _ in pts], [dr(v) for _, v in pts])],
                                  color=color, size=5, legendgroup=cond, name=label)
        # The mean amplitude per intensity as markers, with error bars when requested.
        central = {
            "type": "scatter", "mode": "markers", "x": xr, "y": [dr(v) for v in ys],
            "marker": {"color": color, "size": 7, "line": {"color": "#ffffff", "width": 0.6}},
            "name": label, "legendgroup": cond, "hoverinfo": "x+y+name",
        }
        if spread in ("error_bars", "both"):
            central["error_y"] = {"type": "data", "array": [dr(v) for v in errs],
                                  "visible": True, "thickness": 1, "width": 3, "color": color}
        data.append(central)
        f = fits.get(cond)
        if f:
            line_y = [dr(_erg.naka_rushton(x, f["vmax"], f["log_k"], f["n"])) for x in grid]
            data.append({
                "type": "scatter", "mode": "lines", "x": grid, "y": line_y,
                "line": {"color": color, "width": 1.6}, "name": f"{label} (fit)",
                "legendgroup": cond, "showlegend": False, "hoverinfo": "skip",
            })
            n_cell = f"{f['n']} (fixed)" if f.get("fixed") else f["n"]
            tbl_rows.append([cond, dr(f["vmax"]), f["log_k"], n_cell, f["r2"]])
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
        sem = round(vmax * 0.07, 2)
        lowers = [round(y - sem, 2) for y in ys]
        uppers = [round(y + sem, 2) for y in ys]
        errs = [sem] * len(xs)
        # No per-eye rows in the deterministic stub → no individual points (keeps the golden stable).
        cond_series.append((cond, xs, ys, lowers, uppers, errs, []))
        fits[cond] = {"vmax": vmax, "log_k": log_k, "n": n, "r2": 1.0} if do_fit else None
    spec, tbl_rows = ir_spec(cond_series, fits, title="b-wave intensity-response (stub)")
    spec["table"] = table(
        ["condition", "Vmax (µV)", "log K (cd·s/m²)", "n", "R²"], tbl_rows,
        title="Naka-Rushton fit")
    return spec
