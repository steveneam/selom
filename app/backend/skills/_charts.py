"""Generic figure-styling vocabulary for **any** categorical bar or grouped comparison — not
ERG-specific (owner steer 2026-06-24: the mean ± spread / points / error / pattern / significance
styling applies to *all* bar and line graphs, not just the ERG ones). The ERG skills are the first
consumers; any future bar/line skill (dose-response, abundance, cell-type means, …) calls the same
builders so the look + param vocabulary are consistent everywhere.

Two layers:

* **Stats / colour primitives** (pure, domain-agnostic): :func:`spread_stats` (sem|sd|ci95|minmax),
  :func:`compare_groups` + :func:`sig_stars` (significance), :func:`rgba`, :func:`jitter`. These are
  re-exported by ``skills._erg`` for back-compat.
* **Figure builders**: :func:`bar_figure` — a mean ± spread bar with optional individual points,
  per-category hatch patterns, computed-or-overridden significance brackets, and reference lines.

See docs/records/erg-module/mean-spread-styling-spec.md (the 7 reference styles + the param vocabulary).
"""
from __future__ import annotations

import math

# The significance machinery moved down into `_stats` — the general engine must not depend on this
# bar-shaped module, and every categorical skill (box, violin, composition …) now needs it too.
# Re-exported here so this module's published contract, and `_erg`'s re-export of it, are unchanged.
from skills._stats import (  # noqa: F401  (re-export)
    compare_groups,
    sig_stars,
)
from skills._stats import bracket_shapes as _bracket_shapes
from skills._stats import test_pairs as _test_pairs

# Display label for an error metric (caption / table header).
ERR_LABEL = {"sem": "SEM", "sd": "SD", "ci95": "95% CI", "minmax": "range"}

# Deterministic hatch sequence for categories with no explicit pattern (golden-stable, no RNG).
PATTERN_CYCLE = ["", "/", "\\", "x", "-", "|", "+", "."]

# Deterministic line/series palette for keys with no explicit colour (golden-stable, no RNG) — so a
# series always gets ONE stable colour (and its band matches), never a per-trace auto-colour.
LINE_PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b"]


# --- stats / colour primitives ----------------------------------------------------------
def spread_stats(values, kind: str = "sem") -> dict:
    """Mean + an error metric for a group of values → ``{mean, err, lo, hi, sd, n}`` (raw, unrounded
    — the caller rescales/rounds). ``kind``: ``sem`` (default, sd/√n) · ``sd`` · ``ci95`` (t-quantile
    half-width, not a hard-coded 1.96) · ``minmax`` (asymmetric: ``lo = mean − min``, ``hi = max −
    mean``). ``err`` is the symmetric magnitude (= ``max(lo, hi)`` for minmax). n<2 guard (err 0 —
    never a NaN bar). Non-finite dropped. ci95 lazy-imports scipy for the t-quantile."""
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    n = len(vals)
    if n == 0:
        return {"mean": 0.0, "err": 0.0, "lo": 0.0, "hi": 0.0, "sd": 0.0, "n": 0}
    mean = sum(vals) / n
    if n < 2:
        return {"mean": mean, "err": 0.0, "lo": 0.0, "hi": 0.0, "sd": 0.0, "n": n}
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
    sem = sd / math.sqrt(n)
    k = str(kind or "sem").strip().lower()
    if k == "sd":
        err = lo = hi = sd
    elif k == "ci95":
        from scipy.stats import t
        err = lo = hi = float(t.ppf(0.975, n - 1)) * sem
    elif k == "minmax":
        lo, hi = mean - min(vals), max(vals) - mean
        err = max(lo, hi)
    else:  # sem
        err = lo = hi = sem
    return {"mean": mean, "err": err, "lo": lo, "hi": hi, "sd": sd, "n": n}


def rgba(hexcolor, alpha) -> str:
    """``'#rrggbb'`` (or 3-digit shorthand) → ``'rgba(r,g,b,a)'`` — for translucent fills Plotly
    won't derive from a hex line colour. Mirrors ``_tracegrid._rgba``."""
    h = str(hexcolor or "#888888").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, IndexError):
        r = g = b = 136
    return f"rgba({r},{g},{b},{round(float(alpha), 3)})"


def jitter(center: int, n: int, width: float = 0.34) -> list[float]:
    """Deterministic horizontal spread of n points around an integer position (no RNG → golden-stable)."""
    if n <= 1:
        return [float(center)]
    step = width / (n - 1)
    return [center - width / 2.0 + k * step for k in range(n)]


def resolve_stars(override, vals_a, vals_b, sig_test):
    """Stars for one comparison — thin wrapper over :func:`skills._stats.resolve_stars`, which also
    returns the p-value; this keeps the stars-only signature this module has always published."""
    from skills._stats import resolve_stars as _resolve

    return _resolve(override, vals_a, vals_b, sig_test)[0]


# --- shape / overlay builders -----------------------------------------------------------
def _pattern_for(key, i, patterns):
    if patterns and key in patterns:
        return patterns[key]
    return PATTERN_CYCLE[i % len(PATTERN_CYCLE)]


def _bar_marker(bar_fill, colors, keys, patterns):
    """The bar ``marker`` for the chosen fill: ``filled`` (solid colour — byte-identical default),
    ``pattern`` (per-category hatch — every bar visibly filled: a solid colour where the pattern is
    empty, else a light tint of the colour behind a dense same-colour hatch), or ``open`` (white
    fill + coloured outline)."""
    if bar_fill == "pattern":
        shapes = [_pattern_for(k, i, patterns) for i, k in enumerate(keys)]
        # Hatched bars get a light tint background (never an empty white bar — owner caught this);
        # un-hatched (shape "") bars stay the full solid colour.
        tints = [colors[i] if shapes[i] == "" else rgba(colors[i], 0.22) for i in range(len(keys))]
        return {"color": tints, "line": {"color": colors, "width": 1.3},
                "pattern": {"shape": shapes, "fgcolor": colors, "bgcolor": tints,
                            "size": 8, "solidity": 0.5}}
    if bar_fill == "open":
        return {"color": "#ffffff", "line": {"color": colors, "width": 1.6}}
    return {"color": colors, "line": {"color": "#333333", "width": 1}}  # filled (default)


def sig_brackets(cat_values, idx_of, means, his, pt_y, comparisons, sig_test, *,
                 correction: str = "none"):
    """Significance brackets above the bars — the bar-shaped front door to :mod:`skills._stats`.

    Each comparison is ``(keyA, keyB[, override])``; stars come from the override else the test.
    Returns ``(shapes, annotations, y_top)``: a horizontal bar with end ticks + a star annotation
    per comparison, stacked so they don't overlap, and the top y so the caller can grow the axis.
    Unknown key → skipped.

    All this still owns is the bar's own geometry — where the ink stops (mean + error, and any
    plotted point). The statistics, the stacking and the drawing are ``_stats``', shared with every
    other categorical skill."""
    vals_of = dict((k, v) for k, v in cat_values)
    data_top = max([*(m + h for m, h in zip(means, his)), *pt_y, 0.0])
    results = _test_pairs(_pairs3(comparisons), vals_of, test=sig_test, correction=correction)
    return _bracket_shapes(results, idx_of, data_top, orientation="v")


def _pairs3(comparisons):
    """``(a, b)`` / ``(a, b, override)`` tuples → the uniform 3-tuple ``_stats`` takes."""
    return [(c[0], c[1], c[2] if len(c) > 2 else None) for c in (comparisons or [])]


def band_traces(x, lower, upper, *, color="#888888", alpha=0.25, boundary="none",
                name="", legendgroup=None, xaxis=None, yaxis=None):
    """A continuous ± error band for a **standard (axised) line plot** — the 2-trace ``tonexty``
    fill block (lower bound invisible → upper bound filled down to it). The flat-line analogue of
    ``_tracegrid._overlay_behind``'s band (which targets a hidden panel axis): this emits against
    the default x/y axis, so any non-grid line skill (intensity-response, dose-response, a time
    course …) can drop a shaded band behind its mean line.

    Returns ``[lower_trace, upper_trace]`` — add them to ``data`` BEFORE the mean line so the line
    draws on top. ``boundary`` (none|solid|dashed) styles the band edges; ``legendgroup`` ties the
    band to its series; ``xaxis``/``yaxis`` target a non-default subplot when given."""
    x = [round(float(v), 4) for v in x]
    lo = [round(float(v), 6) for v in lower]
    hi = [round(float(v), 6) for v in upper]
    b = str(boundary or "none").lower()
    bline = ({"width": 0.8, "color": color, "dash": "dash"} if b == "dashed"
             else {"width": 0.8, "color": color} if b == "solid"
             else {"width": 0})
    base = {"type": "scatter", "mode": "lines", "hoverinfo": "skip", "showlegend": False}
    if xaxis:
        base["xaxis"] = xaxis
    if yaxis:
        base["yaxis"] = yaxis
    t_lo = {**base, "x": x, "y": lo, "line": dict(bline)}
    t_hi = {**base, "x": x, "y": hi, "line": dict(bline), "fill": "tonexty",
            "fillcolor": rgba(color, alpha)}
    if name:
        t_hi["name"] = name
    if legendgroup is not None:
        t_lo["legendgroup"] = t_hi["legendgroup"] = str(legendgroup)
    return [t_lo, t_hi]


def ref_line(value, label, *, axis: str):
    """A dashed reference line across the plot at ``value`` on ``axis`` ('y' → horizontal, 'x' →
    vertical), with an optional label, paper-referenced on the other axis so it spans the full plot."""
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


# --- the generic bar figure -------------------------------------------------------------
def bar_figure(cat_values, *, y_title="value", title="", colors=None, labels=None, patterns=None,
               error="sem", show_error=True, points=True, point_name="points",
               bar_fill="filled", comparisons=None, sig_test="welch", correction="none",
               hline=None, hline_label="", vline=None, vline_label="", legend=False, caption="",
               round_fn=None, jitter_width=0.34):
    """A mean ± spread bar for any categorical comparison → ``(spec, table_rows)``.

    ``cat_values`` = ordered ``[(key, [raw values]), …]``. ``colors``/``labels``/``patterns`` are
    optional per-key dicts (defaults: grey palette / ``str(key)`` / the hatch cycle). ``round_fn``
    rescales+rounds a value for display (default ``round(v, 4)``; ERG passes its unit-aware rounder).

    Styling vocabulary (mean-spread-styling-spec): ``error`` (sem|sd|ci95|minmax) · ``show_error`` ·
    ``points`` (jittered individuals) · ``bar_fill`` (filled|pattern|open) · ``comparisons``
    (significance brackets, computed or overridden ``(a, b[, override])``) · ``correction``
    (multiple-comparison adjustment across those brackets — the same vocabulary box/violin use) ·
    ``hline``/``vline`` (reference line) · ``legend`` (per-category pattern legend). ``table_rows``
    = ``[key, n, mean, err]``. The ``filled · sem · no brackets/line/legend`` path is the original
    look."""
    rnd = round_fn or (lambda v: round(float(v), 4))
    labels = labels or {}
    keys = [k for k, _ in cat_values]
    positions = list(range(len(cat_values)))
    means, errs, los, his, cols, ticktext, tbl_rows = [], [], [], [], [], [], []
    pt_x, pt_y = [], []
    for i, (key, vals) in enumerate(cat_values):
        st = spread_stats(vals, error)
        mean = rnd(st["mean"])
        means.append(mean)
        errs.append(rnd(st["err"]))
        los.append(rnd(st["lo"]))
        his.append(rnd(st["hi"]))
        cols.append((colors or {}).get(key, "#888888"))
        ticktext.append(labels.get(key, str(key)))
        tbl_rows.append([key, st["n"], mean, rnd(st["err"])])
        if points:
            for x, v in zip(jitter(i, len(vals), jitter_width), vals):
                pt_x.append(round(x, 4))
                pt_y.append(rnd(v))

    error_y = ({"type": "data", "symmetric": False, "array": his, "arrayminus": los,
                "visible": True, "thickness": 1.2, "width": 6, "color": "#333333"}
               if str(error).lower() == "minmax"
               else {"type": "data", "array": errs, "visible": True,
                     "thickness": 1.2, "width": 6, "color": "#333333"})
    err_label = ERR_LABEL.get(str(error).lower(), "SEM")
    bar = {"type": "bar", "x": positions, "y": means,
           "marker": _bar_marker(bar_fill, cols, keys, patterns),
           "width": 0.62, "name": f"mean ± {err_label}", "showlegend": False, "hoverinfo": "x+y"}
    if show_error:
        bar["error_y"] = error_y
    data = [bar]
    if points and pt_x:
        data.append({"type": "scatter", "mode": "markers", "x": pt_x, "y": pt_y,
                     "marker": {"color": "rgba(20,20,20,0.82)", "size": 6,
                                "line": {"color": "#ffffff", "width": 0.8}},
                     "name": point_name, "showlegend": False, "hoverinfo": "y"})
    if legend:  # per-category pattern legend (proxy bar traces — legend entry only, no data)
        for i, key in enumerate(keys):
            data.append({"type": "bar", "x": [None], "y": [None],
                         "marker": _bar_marker(bar_fill, [cols[i]], [key], patterns),
                         "name": labels.get(key, str(key)).replace("<br>", " "),
                         "showlegend": True, "hoverinfo": "skip"})

    shapes, extra_annos = [], []
    y_top = max([*(m + h for m, h in zip(means, his)), *pt_y, 0.0])
    if comparisons:
        s, a, y_top = sig_brackets(cat_values, {k: i for i, k in enumerate(keys)},
                                   means, his, pt_y, comparisons, sig_test,
                                   correction=correction)
        shapes += s
        extra_annos += a
    if hline is not None:
        s, a = ref_line(rnd(hline), hline_label, axis="y")
        shapes.append(s)
        extra_annos += a
    if vline is not None:
        s, a = ref_line(vline, vline_label, axis="x")
        shapes.append(s)
        extra_annos += a

    yaxis = {"title": {"text": y_title}, "zeroline": True, "rangemode": "tozero"}
    if y_top > 0 and (comparisons or hline is not None):  # grow the axis so brackets/line aren't clipped
        yaxis["range"] = [0, round(y_top * 1.08, 4)]
        yaxis.pop("rangemode", None)
    annotations = []
    if caption:
        annotations.append({"xref": "paper", "yref": "paper", "x": 0.99, "y": 0.99,
                            "xanchor": "right", "yanchor": "top", "showarrow": False,
                            "text": caption, "font": {"size": 11, "color": "#555555"}})
    layout = {
        "title": {"text": title},
        "xaxis": {"tickmode": "array", "tickvals": positions, "ticktext": ticktext,
                  "type": "linear", "range": [-0.6, len(cat_values) - 0.4], "tickangle": -20},
        "yaxis": yaxis,
        "bargap": 0.35, "showlegend": bool(legend), "plot_bgcolor": "white",
        "annotations": [*annotations, *extra_annos],
    }
    if shapes:
        layout["shapes"] = shapes
    return {"data": data, "layout": layout}, tbl_rows


# --- the generic mean ± spread LINE (for any single-axis line graph) --------------------
# The line analogue of bar_figure (owner steer 2026-06-24, D12: the line/spread styling is generic,
# not ERG-only — exactly like the bar styling). Any line skill (intensity-response, dose-response,
# a time course, a growth curve …) gets mean ± spread with one vocabulary. The ERG trace GRID is a
# different layout (small multiples on hidden panel axes) and keeps its own overlay emitter in
# _tracegrid, but shares the SAME stats + replicate aggregation below, so the math is identical.

def aggregate_replicates(replicates, error="sem", x_ref=None):
    """Average n replicate ``(x, y)`` series onto a shared x grid + a per-point spread metric.

    ``replicates`` = ``[(x_list, y_list), …]``; ``x_ref`` defaults to the first replicate's x. Aligns
    by rounded x so partial missingness degrades gracefully (a point present in only some replicates
    still contributes). Returns ``(x_ref, mean, lower, upper, err, n)`` where ``lower``/``upper`` are
    the asymmetric band bounds (``mean − lo``, ``mean + hi``) and ``err`` the symmetric magnitude.
    :func:`spread_stats` guards n<2 (err 0 → never a NaN band). The one replicate-averaging
    implementation shared by every mean ± spread figure (flat line AND the ERG trace grid)."""
    if not replicates:
        return [], [], [], [], [], 0
    ref = [float(v) for v in (x_ref if x_ref is not None else replicates[0][0])]
    maps = [dict(zip([round(float(xx), 6) for xx in xs], ys)) for xs, ys in replicates]
    mean, lower, upper, errs = [], [], [], []
    for x in ref:
        key = round(float(x), 6)
        vals = [m[key] for m in maps if key in m]
        st = spread_stats(vals, error)
        mean.append(st["mean"])
        lower.append(st["mean"] - st["lo"])
        upper.append(st["mean"] + st["hi"])
        errs.append(st["err"])
    return ref, mean, lower, upper, errs, len(replicates)


def error_markers(x, y, errs, *, every=1, color="#444444", width=1.0, cap=3.0, size=4,
                  xaxis=None, yaxis=None, name="", legendgroup=None):
    """Per-point error bars on a standard axis (the flat-line analogue of the grid's error overlay).
    ``every`` thins a dense series (draw every Nth point; null elsewhere → nothing drawn there).
    Returns ONE scatter trace."""
    every = max(1, int(every or 1))
    arr = [float(e) if (i % every == 0 and e is not None) else None for i, e in enumerate(errs)]
    tr = {"type": "scatter", "mode": "markers",
          "x": [round(float(v), 6) for v in x], "y": [round(float(v), 6) for v in y],
          "marker": {"color": color, "size": float(size)},
          "error_y": {"type": "data", "array": arr, "visible": True,
                      "thickness": float(width), "width": float(cap), "color": color},
          "hoverinfo": "x+y", "showlegend": False}
    if xaxis:
        tr["xaxis"] = xaxis
    if yaxis:
        tr["yaxis"] = yaxis
    if name:
        tr["name"] = name
    if legendgroup is not None:
        tr["legendgroup"] = str(legendgroup)
    return tr


def individual_lines(replicates, *, color="#999999", alpha=0.18, width=0.6,
                     xaxis=None, yaxis=None, legendgroup=None):
    """Faint replicate lines behind a mean line (the flat-line analogue of the grid's extra_lines).
    ``replicates`` = ``[(x, y), …]``. Returns one scatter trace per replicate."""
    out = []
    for xs, ys in replicates:
        tr = {"type": "scatter", "mode": "lines", "opacity": float(alpha),
              "x": [round(float(v), 6) for v in xs], "y": [round(float(v), 6) for v in ys],
              "line": {"width": float(width), "color": color}, "hoverinfo": "skip",
              "showlegend": False}
        if xaxis:
            tr["xaxis"] = xaxis
        if yaxis:
            tr["yaxis"] = yaxis
        if legendgroup is not None:
            tr["legendgroup"] = str(legendgroup)
        out.append(tr)
    return out


def point_markers(replicates, *, color="#444444", size=5, xaxis=None, yaxis=None,
                  legendgroup=None, name=""):
    """Each replicate's individual DATA POINTS as one markers trace (the line analogue of the bar's
    per-eye points) — every ``(x, y)`` across all replicates, at its true x. Returns one trace (``[]``
    if no replicates). Colour = the series colour so multi-series points stay distinguishable."""
    px, py = [], []
    for xs, ys in replicates:
        for xx, yy in zip(xs, ys):
            px.append(round(float(xx), 6))
            py.append(round(float(yy), 6))
    if not px:
        return []
    tr = {"type": "scatter", "mode": "markers", "x": px, "y": py,
          "marker": {"color": color, "size": float(size), "line": {"color": "#ffffff", "width": 0.6},
                     "opacity": 0.8},
          "name": f"{name} points" if name else "points", "showlegend": False, "hoverinfo": "x+y"}
    if xaxis:
        tr["xaxis"] = xaxis
    if yaxis:
        tr["yaxis"] = yaxis
    if legendgroup is not None:
        tr["legendgroup"] = str(legendgroup)
    return [tr]


def spread_line_traces(x, *, replicates=None, mean=None, lower=None, upper=None, errs=None,
                       central="mean", spread="band", error="sem", color="#1f77b4", name="",
                       legendgroup=None, line_width=1.8, mode="lines", band_alpha=0.25,
                       boundary="none", error_every=1, marker_size=4, points=False,
                       band_color=None, show_legend=True, xaxis=None, yaxis=None, round_fn=None):
    """Traces for ONE line series with the chosen central tendency + spread overlay, on a standard
    axis. Pass raw ``replicates`` ``[(x, y), …]`` (aggregated here) OR pre-computed
    ``mean``/``lower``/``upper``/``errs`` (already aligned to ``x``).

    ``central``: ``representative`` (first replicate, no spread) | ``mean`` | ``none`` (NO central
    line — show the raw replicates / points only). ``spread``: ``band|error_bars|individual|both|none``.
    ``points``: overlay each replicate's individual DATA POINTS as markers (with or without the mean —
    the line analogue of the bar's per-eye points). ``band_color`` overrides the band fill colour
    (defaults to the line colour, so the band always matches the trace). Returns the traces in draw
    order — band/individual behind, the central line, then error/points in front. n<2 degrades to the
    bare line (no zero-width band)."""
    rnd = round_fn or (lambda v: round(float(v), 6))
    central = str(central or "mean").lower()
    spread = str(spread or "band").lower()
    reps = list(replicates or [])
    line_y = None
    if central == "representative" and reps:
        x = list(reps[0][0])
        line_y = [rnd(v) for v in reps[0][1]]
        n = 1
        spread = "none"
    elif central == "none":
        n = len(reps)
        if reps and not list(x or []):
            x = list(reps[0][0])
    else:  # mean
        if mean is None:
            x, mean, lower, upper, errs, n = aggregate_replicates(reps, error, x_ref=x)
        else:
            n = len(reps) if reps else 2  # caller supplied an aggregate → assume spread is wanted
        line_y = [rnd(v) for v in mean]

    behind, front = [], []
    if line_y is not None and n >= 2 and spread in ("band", "both") and lower is not None and upper is not None:
        behind += band_traces(x, [rnd(v) for v in lower], [rnd(v) for v in upper],
                              color=band_color or color, alpha=band_alpha, boundary=boundary,
                              legendgroup=legendgroup, xaxis=xaxis, yaxis=yaxis)
    # Individual replicate LINES: faint behind a mean; the main (more visible) content for central=none.
    if reps and (spread == "individual" or central == "none"):
        behind += individual_lines(reps, color=color, alpha=0.5 if central == "none" else 0.18,
                                   xaxis=xaxis, yaxis=yaxis, legendgroup=legendgroup)
    if line_y is not None and n >= 2 and spread in ("error_bars", "both") and errs is not None:
        front.append(error_markers(x, line_y, [rnd(v) for v in errs], every=error_every,
                                   color=color, xaxis=xaxis, yaxis=yaxis, legendgroup=legendgroup))
    if points and reps:
        front += point_markers(reps, color=color, size=marker_size + 1, xaxis=xaxis, yaxis=yaxis,
                               legendgroup=legendgroup, name=name)

    mid = []
    if line_y is not None:
        line = {"type": "scatter", "mode": mode,
                "x": [round(float(v), 6) for v in x], "y": line_y,
                "line": {"width": float(line_width), "color": color},
                "name": name or "mean", "showlegend": bool(show_legend), "hoverinfo": "x+y"}
        if legendgroup is not None:
            line["legendgroup"] = str(legendgroup)
        if xaxis:
            line["xaxis"] = xaxis
        if yaxis:
            line["yaxis"] = yaxis
        mid = [line]
    return [*behind, *mid, *front]


def line_figure(series, *, x_title="x", y_title="value", title="", error="sem", spread="band",
                central="mean", colors=None, band_alpha=0.25, boundary="none", error_every=1,
                line_width=1.8, markers=False, points=False, band_color=None, legend=True,
                log_x=False, caption="", round_fn=None):
    """A full multi-series mean ± spread LINE plot for any line graph (the line analogue of
    :func:`bar_figure`) → ``(spec, table_rows)``.

    ``series`` = ordered ``[{"label", "x", "replicates": [(x,y),…]} | {"label","x","mean",
    "lower","upper","errs"}, …]`` (each may carry its own ``color``). One styling vocabulary —
    ``central`` (representative|mean|none) · ``spread`` (band|error_bars|individual|both|none) ·
    ``error`` (sem|sd|ci95|minmax) · ``points`` (individual data points) · ``band_alpha`` ·
    ``boundary`` · ``band_color`` — shared with the bar + the ERG grid. ``table_rows`` =
    ``[label, x, mean, err]`` (the numbers behind each line)."""
    rnd = round_fn or (lambda v: round(float(v), 6))
    data, tbl_rows = [], []
    mode = "lines+markers" if markers else "lines"
    for i, s in enumerate(series):
        color = (s.get("color") or (colors or {}).get(s.get("label"))
                 or LINE_PALETTE[i % len(LINE_PALETTE)])
        reps = s.get("replicates")
        x = s.get("x") or (reps[0][0] if reps else [])
        agg = {k: s.get(k) for k in ("mean", "lower", "upper", "errs") if s.get(k) is not None}
        if not agg and reps:
            _, mean, lower, upper, errs, _ = aggregate_replicates(reps, error, x_ref=x)
            agg = {"mean": mean, "lower": lower, "upper": upper, "errs": errs}
        data += spread_line_traces(
            x, replicates=reps, **agg, central=central, spread=spread, error=error, color=color,
            name=str(s.get("label", f"series {i + 1}")), legendgroup=str(s.get("label", i)),
            line_width=line_width, mode=mode, band_alpha=band_alpha, boundary=boundary,
            error_every=error_every, points=points, band_color=band_color,
            show_legend=bool(legend), round_fn=rnd)
        m = agg.get("mean", [])
        e = agg.get("errs", [None] * len(m))
        for xi, mi, ei in zip(x, m, e):
            tbl_rows.append([s.get("label", f"series {i + 1}"), xi, rnd(mi),
                             rnd(ei) if ei is not None else None])
    annotations = []
    if caption:
        annotations.append({"xref": "paper", "yref": "paper", "x": 0.99, "y": 0.99,
                            "xanchor": "right", "yanchor": "top", "showarrow": False,
                            "text": caption, "font": {"size": 11, "color": "#555555"}})
    layout = {
        "title": {"text": title},
        "xaxis": {"title": {"text": x_title}, "type": "log" if log_x else "linear"},
        "yaxis": {"title": {"text": y_title}, "zeroline": True},
        "showlegend": bool(legend), "plot_bgcolor": "white", "annotations": annotations,
    }
    return {"data": data, "layout": layout}, tbl_rows
