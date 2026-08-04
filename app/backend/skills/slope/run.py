"""Slope chart — the same subject measured twice, drawn as the line between its two values.

Before/after is currently forced into a bar chart, and a bar chart of paired data throws the pairing
away: two bars show two group means and say nothing about whether individuals moved together. The
line per subject IS the datum here — a figure where most subjects rise while the group mean barely
moves is a completely different result from one where half rise and half fall, and both produce
identical bars.

Real engine in ``run_real.py``; the stub here is a deterministic before/after of the same wire shape.

**The statistic follows the geometry.** cnsplots' ``slopeplot`` draws this and computes nothing —
honest, but it leaves the reader eyeballing it. Selom tests it, and tests it PAIRED
(``_stats.compare_paired``): an unpaired Welch on the two columns would compare marginal
distributions and discard exactly the structure the picture is built on. That choice is the reason
this is its own skill rather than a ``line`` mode — every other line plot here aggregates replicates
at each x, which is the one thing a paired design must not do.
"""

import math

from skills._engine import to_bool, use_real_engine
from skills._stats import TEST_LABEL, compare_paired, resolve_order, sig_stars
from skills._table import _sig, table

_MAX_SUBJECTS = 400        # segments past this stop being readable and bloat the editable spec
_MAX_GROUPS = 12
# Direction colours. Explicit rather than colourway-assigned: these encode a MEANING (up / down),
# not a series identity, so they must not shuffle when the style's colourway changes.
_UP = "#c0392b"
_DOWN = "#2f6db0"
_FLAT = "#8a939e"
_DIRECTION = (("increased", _UP), ("decreased", _DOWN), ("unchanged", _FLAT))


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.slope.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    """Deterministic paired before/after — most subjects fall, two rise (the shape a bar hides)."""
    paired = {
        "Control": {
            "S1": (0.82, 0.61), "S2": (0.77, 0.55), "S3": (0.91, 0.70),
            "S4": (0.68, 0.74), "S5": (0.85, 0.63),
        },
        "Treated": {
            "S6": (0.79, 0.42), "S7": (0.88, 0.39), "S8": (0.73, 0.51),
            "S9": (0.80, 0.86), "S10": (0.84, 0.44),
        },
    }
    return slope_spec(paired, ("baseline", "week 12"), params,
                      "response index", "cohort", "Paired response (stub)")


def slope_spec(paired: dict, levels, params: dict, value_label: str, group_label: str,
               title: str) -> dict:
    """Editable Plotly slope spec (shared by stub + real engine).

    ``paired`` = ``{group: {subject: (before, after)}}`` — one group when the data has no grouping
    column. ``levels`` = the two condition names, in drawn order.

    Segments are emitted as THREE traces (increased / decreased / unchanged) with ``None``
    separators rather than one trace per subject. That is the difference between 3 legend entries a
    reader can toggle and 400 they cannot, and it makes the direction split — the thing the figure
    exists to show — a first-class control instead of a colour the eye has to tally.
    """
    before_name, after_name = (str(levels[0]), str(levels[1]))
    show_mean = str(params.get("summary", "mean")).strip().lower()
    show_points = to_bool(params.get("points", True))

    groups = resolve_order(list(paired.keys()), params.get("order"))[:_MAX_GROUPS]
    grouped = bool(params.get("_grouped"))

    segments = {name: {"x": [], "y": []} for name, _ in _DIRECTION}
    dots = {before_name: {"x": [], "y": []}, after_name: {"x": [], "y": []}}
    summary_x, summary_y = [], []
    tick_vals, tick_text = [], []
    table_rows = []
    drawn = 0

    for gi, group in enumerate(groups):
        subjects = paired[group]
        x0, x1 = (gi - 0.18, gi + 0.18) if grouped else (0.0, 1.0)
        if grouped:
            tick_vals.append(gi)
            tick_text.append(str(group))
        for subject, (b, a) in subjects.items():
            if drawn >= _MAX_SUBJECTS:
                break
            if not (_finite(b) and _finite(a)):
                continue
            key = "increased" if a > b else ("decreased" if a < b else "unchanged")
            seg = segments[key]
            seg["x"] += [x0, x1, None]
            seg["y"] += [round(b, 4), round(a, 4), None]
            dots[before_name]["x"].append(x0)
            dots[before_name]["y"].append(round(b, 4))
            dots[after_name]["x"].append(x1)
            dots[after_name]["y"].append(round(a, 4))
            drawn += 1

        befores = [b for b, a in subjects.values() if _finite(b) and _finite(a)]
        afters = [a for b, a in subjects.values() if _finite(b) and _finite(a)]
        if show_mean in ("mean", "median") and befores:
            cb, ca = _central(befores, show_mean), _central(afters, show_mean)
            summary_x += [x0, x1, None]
            summary_y += [round(cb, 4), round(ca, 4), None]
        table_rows.append(_group_row(group, befores, afters, params))
        if not grouped:
            tick_vals, tick_text = [0.0, 1.0], [before_name, after_name]

    data = []
    for name, color in _DIRECTION:
        seg = segments[name]
        if not seg["x"]:
            continue
        data.append({"type": "scatter", "mode": "lines", "name": name,
                     "x": seg["x"], "y": seg["y"], "showlegend": True,
                     "line": {"color": color, "width": 1.1}, "opacity": 0.55,
                     "hoverinfo": "skip", "legendgroup": name})
    if show_points:
        for label, color in ((before_name, "#4c5763"), (after_name, "#1f2a37")):
            pts = dots[label]
            if pts["x"]:
                data.append({"type": "scatter", "mode": "markers", "name": label,
                             "x": pts["x"], "y": pts["y"], "showlegend": True,
                             "marker": {"color": color, "size": 6,
                                        "line": {"color": "#ffffff", "width": 0.8}},
                             "hoverinfo": "y"})
    if summary_x:
        data.append({"type": "scatter", "mode": "lines+markers",
                     "name": f"{show_mean} of subjects",
                     "x": summary_x, "y": summary_y, "showlegend": True,
                     "line": {"color": "#111111", "width": 2.6},
                     "marker": {"size": 8, "color": "#111111"}, "hoverinfo": "y"})
    if not data:
        raise ValueError(
            "slope: no subject had a value at BOTH conditions, so there is nothing paired to draw"
        )

    # A LINEAR x axis carrying explicit ticks, not a category axis: the two conditions sit at fixed
    # offsets inside each group cluster, which a category axis has no way to express.
    layout = {
        "title": {"text": title},
        "xaxis": {"tickmode": "array", "tickvals": tick_vals, "ticktext": tick_text,
                  "type": "linear",
                  "range": [-0.6, (len(groups) - 0.4) if grouped else 1.6],
                  "title": {"text": group_label if grouped else ""}},
        "yaxis": {"title": {"text": value_label}, "zeroline": False},
        "showlegend": True,
        "plot_bgcolor": "white",
    }
    spec = {"data": data, "layout": layout}
    spec["table"] = _slope_table(table_rows, params, before_name, after_name, group_label)
    return spec


def _finite(v) -> bool:
    try:
        return v is not None and math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _central(values, how: str) -> float:
    vals = sorted(float(v) for v in values)
    if not vals:
        return 0.0
    if how == "median":
        mid = len(vals) // 2
        return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0
    return sum(vals) / len(vals)


def _group_row(group, befores, afters, params: dict) -> list:
    """One group's paired summary: n, both central values, the mean change, and the paired p."""
    how = "median" if str(params.get("summary", "mean")).lower() == "median" else "mean"
    test = str(params.get("sig_test", "paired_t")).strip().lower()
    n = len(befores)
    if not n:
        return [str(group), 0, "n/a", "n/a", "n/a", "n/a", "ns"]
    cb, ca = _central(befores, how), _central(afters, how)
    up = sum(1 for b, a in zip(befores, afters) if a > b)
    down = sum(1 for b, a in zip(befores, afters) if a < b)
    p = compare_paired(befores, afters, test=test)
    return [str(group), n, round(cb, 4), round(ca, 4), round(ca - cb, 4),
            f"{up} up / {down} down",
            _sig(p) if p is not None else "n/a", sig_stars(p)]


def _slope_table(rows, params: dict, before_name: str, after_name: str,
                 group_label: str) -> dict:
    """The paired result per group.

    ``up / down`` is a column rather than a footnote because it is the number a bar chart destroys:
    a group whose mean barely moves because half its subjects rose and half fell is a different
    finding from one where nobody moved, and only the direction split separates them.
    """
    how = "median" if str(params.get("summary", "mean")).lower() == "median" else "mean"
    test = str(params.get("sig_test", "paired_t")).strip().lower()
    label = TEST_LABEL.get(test, test)
    columns = [group_label or "group", "n pairs", f"{how} {before_name}", f"{how} {after_name}",
               "change", "direction", "p", ""]
    return table(columns, rows,
                 f"Paired change ({label}, two-sided; pairs missing either condition are excluded)")
