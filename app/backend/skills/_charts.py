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

See docs/erg-module/mean-spread-styling-spec.md (the 7 reference styles + the param vocabulary).
"""
from __future__ import annotations

import math

# Display label for an error metric (caption / table header).
ERR_LABEL = {"sem": "SEM", "sd": "SD", "ci95": "95% CI", "minmax": "range"}

# Deterministic hatch sequence for categories with no explicit pattern (golden-stable, no RNG).
PATTERN_CYCLE = ["", "/", "\\", "x", "-", "|", "+", "."]


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


def sig_stars(p) -> str:
    """p-value → significance stars (GraphPad convention): ``***`` <0.001 · ``**`` <0.01 ·
    ``*`` <0.05 · ``ns`` otherwise. None/non-finite → ``ns``."""
    if p is None or not math.isfinite(float(p)):
        return "ns"
    p = float(p)
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"


def compare_groups(a, b, test: str = "welch"):
    """Two-group two-sided p-value, or None when either side has n<2. ``test``: ``welch`` (default,
    unequal-variance t) · ``student`` (equal-variance t) · ``mannwhitney`` (rank). scipy lazy."""
    a = [float(x) for x in a if x is not None and math.isfinite(float(x))]
    b = [float(x) for x in b if x is not None and math.isfinite(float(x))]
    if len(a) < 2 or len(b) < 2:
        return None
    from scipy import stats

    t = str(test or "welch").strip().lower()
    try:
        if t in ("mannwhitney", "mwu", "u"):
            return float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue)
        return float(stats.ttest_ind(a, b, equal_var=(t == "student")).pvalue)
    except (ValueError, ZeroDivisionError):
        return None


def jitter(center: int, n: int, width: float = 0.34) -> list[float]:
    """Deterministic horizontal spread of n points around an integer position (no RNG → golden-stable)."""
    if n <= 1:
        return [float(center)]
    step = width / (n - 1)
    return [center - width / 2.0 + k * step for k in range(n)]


def resolve_stars(override, vals_a, vals_b, sig_test):
    """Stars for one comparison: a manual override (``"**"`` / a literal p like ``"0.003"``) when
    given, else computed by :func:`compare_groups` on the raw values (the owner's "both available" —
    Selom computes but every star stays overridable)."""
    if override:
        o = str(override).strip()
        if o in ("*", "**", "***", "ns"):
            return o
        try:
            return sig_stars(float(o))
        except ValueError:
            pass
    return sig_stars(compare_groups(vals_a, vals_b, test=sig_test))


# --- shape / overlay builders -----------------------------------------------------------
def _pattern_for(key, i, patterns):
    if patterns and key in patterns:
        return patterns[key]
    return PATTERN_CYCLE[i % len(PATTERN_CYCLE)]


def _bar_marker(bar_fill, colors, keys, patterns):
    """The bar ``marker`` for the chosen fill: ``filled`` (solid colour — byte-identical default),
    ``pattern`` (per-category hatch: solid where the pattern is empty, else a white bar with a
    coloured hatch), or ``open`` (white fill + coloured outline)."""
    if bar_fill == "pattern":
        shapes = [_pattern_for(k, i, patterns) for i, k in enumerate(keys)]
        fills = [colors[i] if shapes[i] == "" else "#ffffff" for i in range(len(keys))]
        return {"color": fills, "line": {"color": colors, "width": 1.2},
                "pattern": {"shape": shapes, "fgcolor": colors, "bgcolor": "#ffffff",
                            "size": 6, "solidity": 0.35}}
    if bar_fill == "open":
        return {"color": "#ffffff", "line": {"color": colors, "width": 1.6}}
    return {"color": colors, "line": {"color": "#333333", "width": 1}}  # filled (default)


def sig_brackets(cat_values, idx_of, means, his, pt_y, comparisons, sig_test):
    """Significance brackets above the bars. Each comparison is ``(keyA, keyB[, override])``; stars
    come from the override else :func:`compare_groups`. Returns ``(shapes, annotations, y_top)``: a
    horizontal bar with end ticks + a star annotation per comparison, stacked so they don't overlap,
    and the top y so the caller can grow the axis. Unknown key → skipped."""
    vals_of = dict((k, v) for k, v in cat_values)
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
        stars = resolve_stars(override, vals_of.get(a, []), vals_of.get(b, []), sig_test)
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
               bar_fill="filled", comparisons=None, sig_test="welch", hline=None, hline_label="",
               vline=None, vline_label="", legend=False, caption="", round_fn=None,
               jitter_width=0.34):
    """A mean ± spread bar for any categorical comparison → ``(spec, table_rows)``.

    ``cat_values`` = ordered ``[(key, [raw values]), …]``. ``colors``/``labels``/``patterns`` are
    optional per-key dicts (defaults: grey palette / ``str(key)`` / the hatch cycle). ``round_fn``
    rescales+rounds a value for display (default ``round(v, 4)``; ERG passes its unit-aware rounder).

    Styling vocabulary (mean-spread-styling-spec): ``error`` (sem|sd|ci95|minmax) · ``show_error`` ·
    ``points`` (jittered individuals) · ``bar_fill`` (filled|pattern|open) · ``comparisons``
    (significance brackets, computed or overridden ``(a, b[, override])``) · ``hline``/``vline``
    (reference line) · ``legend`` (per-category pattern legend). ``table_rows`` = ``[key, n, mean,
    err]``. The ``filled · sem · no brackets/line/legend`` path is the original look."""
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
                                   means, his, pt_y, comparisons, sig_test)
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
