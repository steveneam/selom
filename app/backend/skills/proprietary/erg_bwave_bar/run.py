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


# Per-condition hatch pattern (the Fig 1E look) — solid for Control + the 3'UTR rescue, hatched for
# the rest, mirroring the GraphPad figure. Unknown conditions cycle a deterministic pattern sequence.
_PATTERN = {
    "Control": "", "Untreated": ".", "AAV8-RK-PDE6B": "x",
    "AAV8-RK-GFP-polyA-stuffer": "/", "AAV8-CMV-GFP": "\\", "AAV8-RK-PDE6B-3UTR": "",
}
_PATTERN_CYCLE = ["", "/", "\\", "x", "-", "|", "+", "."]


def _pattern_for(cond: str, i: int) -> str:
    return _PATTERN.get(cond, _PATTERN_CYCLE[i % len(_PATTERN_CYCLE)])


def _bar_marker(bar_fill: str, colors: list, conds: list):
    """The bar ``marker`` for the chosen fill: ``filled`` (solid condition colour — byte-identical
    default), ``pattern`` (per-condition hatch: solid where the pattern is empty, else a white bar
    with a condition-coloured hatch), or ``open`` (white fill + condition-coloured outline)."""
    if bar_fill == "pattern":
        shapes = [_pattern_for(c, i) for i, c in enumerate(conds)]
        fills = [colors[i] if shapes[i] == "" else "#ffffff" for i in range(len(conds))]
        return {"color": fills, "line": {"color": colors, "width": 1.2},
                "pattern": {"shape": shapes, "fgcolor": colors, "bgcolor": "#ffffff",
                            "size": 6, "solidity": 0.35}}
    if bar_fill == "open":
        return {"color": "#ffffff", "line": {"color": colors, "width": 1.6}}
    return {"color": colors, "line": {"color": "#333333", "width": 1}}  # filled (default)


def _resolve_stars(override, vals_a, vals_b, sig_test):
    """Stars for one comparison: a manual override (``"**"`` / a literal p like ``"0.003"``) when
    given, else computed by ``_erg.compare_groups`` on the raw per-eye values (Both-available, the
    owner's choice — Selom computes but every star stays overridable)."""
    if override:
        o = str(override).strip()
        if o in ("*", "**", "***", "ns"):
            return o
        try:
            return _erg.sig_stars(float(o))
        except ValueError:
            pass
    return _erg.sig_stars(_erg.compare_groups(vals_a, vals_b, test=sig_test))


def _sig_brackets(cond_values, idx_of, means, his, pt_y, comparisons, sig_test, factor):
    """Significance brackets above the bars. Each comparison is ``(condA, condB[, override])``; the
    stars come from the override else ``_erg.compare_groups``. Returns ``(shapes, annotations,
    y_top)``: a horizontal bar with end ticks + a star annotation per comparison, stacked so they
    don't overlap, and the top y so the caller can grow the axis. Unknown condition → skipped."""
    vals_of = dict(cond_values)
    data_top = max([*(m + h for m, h in zip(means, his)), *pt_y, 0.0])
    step = (data_top or 1.0) * 0.12
    tick = step * 0.35
    shapes, annos = [], []
    level = 0
    for comp in comparisons:
        a, b = comp[0], comp[1]
        override = comp[2] if len(comp) > 2 else None
        if a not in idx_of or b not in idx_of:
            continue
        ia, ib = idx_of[a], idx_of[b]
        stars = _resolve_stars(override, vals_of.get(a, []), vals_of.get(b, []), sig_test)
        y = data_top + step * (level + 1)
        x0, x1 = min(ia, ib), max(ia, ib)
        line = {"color": "#333333", "width": 1.2}
        shapes.append({"type": "line", "xref": "x", "yref": "y", "x0": x0, "x1": x1,
                       "y0": round(y, 4), "y1": round(y, 4), "line": line})
        for xe in (x0, x1):  # downward end ticks
            shapes.append({"type": "line", "xref": "x", "yref": "y", "x0": xe, "x1": xe,
                           "y0": round(y, 4), "y1": round(y - tick, 4), "line": line})
        annos.append({"xref": "x", "yref": "y", "x": (x0 + x1) / 2.0, "y": round(y + tick * 0.4, 4),
                      "text": stars, "showarrow": False, "yanchor": "bottom",
                      "font": {"size": 14 if stars != "ns" else 11, "color": "#333333"}})
        level += 1
    return shapes, annos, (data_top + step * (level + 1) if level else data_top)


def _ref_line(value, label, *, axis: str):
    """A reference line across the plot at ``value`` on ``axis`` ('y' → horizontal, 'x' → vertical),
    dashed, with an optional label. Paper-referenced on the OTHER axis so it spans the full plot."""
    horiz = axis == "y"
    shape = {"type": "line", "line": {"color": "#888888", "width": 1.4, "dash": "dash"}}
    if horiz:
        shape |= {"xref": "paper", "x0": 0, "x1": 1, "yref": "y", "y0": value, "y1": value}
    else:
        shape |= {"yref": "paper", "y0": 0, "y1": 1, "xref": "x", "x0": value, "x1": value}
    annos = []
    if label:
        annos.append({"xref": "paper" if horiz else "x", "yref": "y" if horiz else "paper",
                      "x": 0.01 if horiz else value, "y": value if horiz else 0.99,
                      "text": label, "showarrow": False, "xanchor": "left",
                      "yanchor": "bottom" if horiz else "top", "font": {"size": 10, "color": "#888888"}})
    return shape, annos


def bar_spec(cond_values, *, intensity_label: str, title: str, unit: str = "µV",
             factor: float = 1.0, show_points: bool = True, wave_label: str = "b-wave",
             error: str = "sem", show_error: bool = True, bar_fill: str = "filled",
             comparisons=None, sig_test: str = "welch", hline=None, hline_label: str = "",
             vline=None, vline_label: str = "", legend: bool = False):
    """Editable bar spec (shared by stub + real). ``cond_values`` = ordered list of
    ``(condition, [values])``. ``unit``/``factor`` set the display unit (default µV, factor 1.0):
    means, error bars, overlaid eye points, table, and y-axis title rescale together. ``wave_label``
    titles the y-axis.

    Styling (docs/erg-module/mean-spread-styling-spec.md): ``error`` (sem|sd|ci95|minmax, default
    sem — owner default) picks the spread; ``bar_fill`` (filled|pattern|open) the look — ``pattern``
    is the per-condition GraphPad hatch (Fig 1E); ``comparisons`` = ``[(condA, condB), …]`` draws
    significance brackets (p from ``sig_p`` override else ``_erg.compare_groups(test=sig_test)``);
    ``hline``/``vline`` add a labelled reference line; ``legend`` shows a per-condition pattern
    legend. The default (sem · filled · no comparisons · no line · no legend) is byte-identical to
    the original. Returns ``(spec, table_rows)`` with ``table_rows`` = ``[condition, n, mean, err]``."""
    value_label = f"{wave_label} amplitude ({unit})"
    err_label = _erg.ERR_LABEL.get(str(error).lower(), "SEM")
    positions = list(range(len(cond_values)))
    conds = [c for c, _ in cond_values]
    means, errs, los, his, colors, ticktext, tbl_rows = [], [], [], [], [], [], []
    pt_x, pt_y = [], []
    for i, (cond, vals) in enumerate(cond_values):
        st = _erg.spread_stats(vals, error)
        mean = _erg.disp_round(st["mean"], factor)
        means.append(mean)
        errs.append(_erg.disp_round(st["err"], factor))
        los.append(_erg.disp_round(st["lo"], factor))
        his.append(_erg.disp_round(st["hi"], factor))
        colors.append(_erg.COLORS.get(cond, "#888888"))
        ticktext.append(_erg.COL_LABELS.get(cond, cond))
        tbl_rows.append([cond, st["n"], mean, _erg.disp_round(st["err"], factor)])
        if show_points:
            for x, v in zip(_jitter(i, len(vals)), vals):
                pt_x.append(round(x, 4))
                pt_y.append(_erg.disp_round(v, factor))

    error_y = ({"type": "data", "symmetric": False, "array": his, "arrayminus": los,
                "visible": True, "thickness": 1.2, "width": 6, "color": "#333333"}
               if str(error).lower() == "minmax"
               else {"type": "data", "array": errs, "visible": True,
                     "thickness": 1.2, "width": 6, "color": "#333333"})
    bar = {
        "type": "bar", "x": positions, "y": means,
        "marker": _bar_marker(bar_fill, colors, conds),
        "width": 0.62, "name": f"mean ± {err_label}", "showlegend": False, "hoverinfo": "x+y",
    }
    if show_error:  # error bars are toggleable (owner ask) — omit the key entirely when hidden
        bar["error_y"] = error_y
    data = [bar]
    if show_points and pt_x:
        data.append({
            "type": "scatter", "mode": "markers", "x": pt_x, "y": pt_y,
            "marker": {"color": "rgba(20,20,20,0.82)", "size": 6,
                       "line": {"color": "#ffffff", "width": 0.8}},
            "name": "eyes", "showlegend": False, "hoverinfo": "y",
        })
    # Optional per-condition pattern legend (proxy bar traces — no data, legend entry only).
    if legend:
        for i, cond in enumerate(conds):
            data.append({
                "type": "bar", "x": [None], "y": [None],
                "marker": _bar_marker(bar_fill, [colors[i]], [cond]),
                "name": _erg.COL_LABELS.get(cond, cond).replace("<br>", " "),
                "showlegend": True, "hoverinfo": "skip",
            })

    shapes, extra_annos = [], []
    y_top = max([*(m + h for m, h in zip(means, his)), *pt_y, 0.0])
    if comparisons:
        s, a, y_top = _sig_brackets(cond_values, {c: i for i, c in enumerate(conds)},
                                    means, his, pt_y, comparisons, sig_test, factor)
        shapes += s
        extra_annos += a
    if hline is not None:
        s, a = _ref_line(_erg.disp_round(hline, factor), hline_label, axis="y")
        shapes.append(s)
        extra_annos += a
    if vline is not None:
        s, a = _ref_line(vline, vline_label, axis="x")
        shapes.append(s)
        extra_annos += a

    yaxis = {"title": {"text": value_label}, "zeroline": True, "rangemode": "tozero"}
    if y_top > 0 and (comparisons or hline is not None):  # grow the axis so brackets/line aren't clipped
        yaxis["range"] = [0, round(y_top * 1.08, 4)]
        yaxis.pop("rangemode", None)
    layout = {
        "title": {"text": title},
        "xaxis": {"tickmode": "array", "tickvals": positions, "ticktext": ticktext,
                  "type": "linear", "range": [-0.6, len(cond_values) - 0.4], "tickangle": -20},
        "yaxis": yaxis,
        "bargap": 0.35, "showlegend": bool(legend), "plot_bgcolor": "white",
        "annotations": [{"xref": "paper", "yref": "paper", "x": 0.99, "y": 0.99,
                         "xanchor": "right", "yanchor": "top", "showarrow": False,
                         "text": intensity_label, "font": {"size": 11, "color": "#555555"}},
                        *extra_annos],
    }
    if shapes:
        layout["shapes"] = shapes
    return {"data": data, "layout": layout}, tbl_rows


def _stub_figure(params: dict) -> dict:
    show_points = str(params.get("points", True)).lower() not in ("false", "0", "no")
    cond_values = [(c, _STUB_VALS[c]) for c in _ORDER]
    spec, tbl_rows = bar_spec(cond_values, intensity_label="1.0 log cd·s/m²",
                              title="Scotopic b-wave by condition (stub)", show_points=show_points)
    spec["table"] = table(["condition", "n (eyes)", "mean b-wave (µV)", "SEM (µV)"],
                          tbl_rows, title="ERG b-wave (mean ± SEM)")
    return spec
