"""Ranked lollipop chart — a stem topped with a dot, one per category.

The cleaner alternative to a bar chart for a RANKED single value: the bar's filled area carries
no information when the point of the figure is the ordering, and at 20+ categories a bar chart is
mostly ink. Stems + dots read as a ranking.

Real engine in ``run_real.py`` (long-form CSV → one lollipop per category); the stub here is a
deterministic ranked comparison of the same wire shape.

Two things this carries that a bar does NOT, and they are the reason it is its own skill rather
than a ``bar_figure`` flag:

* **A bootstrap CI on the median.** ``_charts.bar_figure`` is mean±SEM by construction (its whole
  vocabulary — ``error``, ``show_error``, the ``[key, n, mean, err]`` table — is parametric). A
  ranked figure is usually ranked on the MEDIAN, whose interval has no closed form, so it is a
  seeded percentile bootstrap. Bolting a non-parametric estimator onto the parametric spine would
  have meant a second error path through a golden-pinned function.
* **An honest refusal on a pre-aggregated table.** One row per category means n=1 everywhere: no
  interval exists and no pairwise test is possible. That case is *normal* here (a ranked list of
  scores usually arrives already aggregated) and rare on a bar chart, so it is handled rather than
  degraded — see ``_ci`` and the ``pairs`` guard below.

Everything else is the shared categorical vocabulary (``skills._stats``): ``order`` · ``add_count``
· ``pairs`` → test + bracket + stars, with ``sig_test`` and ``correction``.
"""

import math
import random

from skills._engine import to_bool, use_real_engine
from skills._stats import (
    attach_brackets,
    count_labels,
    pairs_table,
    parse_pairs,
    resolve_order,
    test_pairs,
)
from skills._table import table

# Deterministic bootstrap: a figure must redraw byte-identically, so the resampler is seeded and
# the count is fixed. cnsplots does the same (``_LOLLIPOP_BOOTSTRAP_SEED``) for the same reason.
_BOOT_SAMPLES = 1000
_BOOT_SEED = 20260804
_MAX_CATEGORIES = 60          # keep the editable spec light
_STEM_ALPHA = 0.55            # cnsplots draws stems at alpha 0.4 — the dot is the datum
_STEM_COLOR = "#7c8896"       # neutral: the stem is furniture, so it must not read as a series
# Plotly's marker.size is a PIXEL DIAMETER. cnsplots' markersize=20 is matplotlib's `s`, an area in
# points², i.e. a ~5pt diameter — copying the number across would draw a 20px blob. Getting this
# backwards is exactly how `enrichment` shipped 1-3 PIXEL dots (parity audit F1.5).
_DOT_SIZE = 9


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.lollipop.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    """Deterministic ranked pathway scores — the shape a ranked enrichment/score table has."""
    groups = {
        "Phototransduction":   [4.8, 5.2, 4.6, 5.0, 4.9],
        "Visual cycle":        [3.9, 4.3, 3.6, 4.1, 3.8],
        "Synaptic signalling": [3.1, 2.8, 3.4, 3.0, 3.2],
        "Glial activation":    [2.2, 2.6, 1.9, 2.4, 2.1],
        "Oxidative stress":    [1.4, 1.1, 1.7, 1.3, 1.5],
    }
    return lollipop_spec(groups, params, "enrichment score", "pathway",
                         "Ranked pathway scores (stub)")


def _central(values, estimator: str) -> float:
    vals = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not vals:
        return 0.0
    if estimator == "mean":
        return sum(vals) / len(vals)
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0


def _ci(values, estimator: str, level: float = 0.95):
    """``(lo, hi)`` around the central value, or ``None`` when the data cannot support one.

    Percentile bootstrap for BOTH estimators, deliberately: the mean's t-interval and the median's
    bootstrap interval would otherwise be two different claims wearing one column header, and the
    figure's error bar would change meaning when the user flips ``estimator``. One mechanism, one
    caption. Returns None below 3 values — a 2-point bootstrap resamples from two numbers and draws
    an interval that describes the resampler, not the data.
    """
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if len(vals) < 3:
        return None
    rng = random.Random(_BOOT_SEED)
    n = len(vals)
    stats = []
    for _ in range(_BOOT_SAMPLES):
        sample = [vals[rng.randrange(n)] for _ in range(n)]
        stats.append(_central(sample, estimator))
    stats.sort()
    tail = (1.0 - level) / 2.0
    lo = stats[max(0, int(math.floor(tail * (_BOOT_SAMPLES - 1))))]
    hi = stats[min(_BOOT_SAMPLES - 1, int(math.ceil((1.0 - tail) * (_BOOT_SAMPLES - 1))))]
    return lo, hi


def lollipop_spec(groups: dict, params: dict, value_label: str, group_label: str,
                  title: str) -> dict:
    """Editable Plotly lollipop spec (shared by stub + real engine).

    ``groups`` = ``{label: [values]}``; a pre-aggregated table arrives as ``{label: [one value]}``
    and is handled (no interval, no brackets) rather than faked.

    Orientation defaults to **horizontal**, unlike every other categorical skill here. A lollipop's
    reason to exist is a ranking, rankings are usually read top-to-bottom, and horizontal is the one
    layout where a long category name gets real estate instead of a -20° tick rotation — which is
    open audit row 21 (long labels colliding with the axis title). Vertical is one param away.
    """
    horizontal = not str(params.get("orientation", "h")).lower().startswith("v")
    estimator = "mean" if str(params.get("estimator", "median")).lower() == "mean" else "median"
    show_ci = to_bool(params.get("error_bars", True))
    show_tip = to_bool(params.get("add_tip", False))
    baseline = _as_float(params.get("baseline"), 0.0)

    central = {k: _central(v, estimator) for k, v in groups.items()}
    # Rank first, THEN let an explicit `order` override — so `order` names a few categories to pin
    # and the rest stay ranked, rather than reverting to whatever order the file happened to have.
    sort = str(params.get("sort", "desc")).strip().lower()
    if sort in ("asc", "ascending"):
        natural = sorted(groups, key=lambda k: central[k])
    elif sort in ("none", "input", "file"):
        natural = list(groups)
    else:
        natural = sorted(groups, key=lambda k: central[k], reverse=True)
    order = resolve_order(list(groups.keys()), params.get("order"), natural=natural)[
        :_MAX_CATEGORIES]
    values_of = {k: groups[k] for k in order}
    labels = (count_labels(order, values_of) if to_bool(params.get("add_count", False))
              else {k: str(k) for k in order})
    # A horizontal ranking reads top-to-bottom, but Plotly's category axis grows UPWARD, so the
    # rank-1 category would land at the bottom. Reverse the drawn order to put it at the top; the
    # bracket index map is built from this same list, so positions stay consistent.
    drawn = list(reversed(order)) if horizontal else list(order)

    cis = {k: (_ci(values_of[k], estimator) if show_ci else None) for k in order}

    stem_cat, stem_val = [], []
    for key in drawn:
        stem_cat += [labels[key], labels[key], None]
        stem_val += [round(baseline, 4), round(central[key], 4), None]
    # The stem is FURNITURE, not a second series, so its colour is set explicitly to a neutral
    # grey rather than left to the theme. Left alone it takes the next colourway slot and the
    # figure renders a blue stem under an orange dot — one mark reading as two unrelated series.
    # (Found by rendering it; the spec asserts nothing about which colour a trace is handed.)
    # `theme._apply_base` only sets `layout.colorway`, so an explicit trace colour survives.
    stems = {"type": "scatter", "mode": "lines", "name": "stem", "showlegend": False,
             "hoverinfo": "skip", "line": {"color": _STEM_COLOR, "width": 2.0},
             "opacity": _STEM_ALPHA}
    stems["y" if horizontal else "x"] = stem_cat
    stems["x" if horizontal else "y"] = stem_val

    dot_cat = [labels[k] for k in drawn]
    dot_val = [round(central[k], 4) for k in drawn]
    dots = {"type": "scatter", "mode": "markers", "name": estimator,
            "showlegend": False, "hoverinfo": "x+y",
            "marker": {"size": _DOT_SIZE, "line": {"color": "#ffffff", "width": 1.0}}}
    dots["y" if horizontal else "x"] = dot_cat
    dots["x" if horizontal else "y"] = dot_val
    if show_tip:
        dots["mode"] = "markers+text"
        dots["text"] = [_tip(central[k]) for k in drawn]
        dots["textposition"] = "middle right" if horizontal else "top center"
    if any(cis[k] for k in drawn):
        # Asymmetric on purpose: a bootstrap interval is not symmetric about its estimate, and
        # halving it into a single ± would print a number the data never produced.
        plus = [round((cis[k][1] - central[k]) if cis[k] else 0.0, 4) for k in drawn]
        minus = [round((central[k] - cis[k][0]) if cis[k] else 0.0, 4) for k in drawn]
        dots["error_x" if horizontal else "error_y"] = {
            "type": "data", "symmetric": False, "array": plus, "arrayminus": minus,
            "visible": True, "thickness": 1.1, "width": 4, "color": "#333333"}

    value_axis = {"title": {"text": value_label}, "zeroline": True}
    cat_axis = {"title": {"text": group_label}, "type": "category"}
    layout = {
        "title": {"text": title},
        "xaxis": value_axis if horizontal else cat_axis,
        "yaxis": cat_axis if horizontal else value_axis,
        "showlegend": False,
        "plot_bgcolor": "white",
    }
    spec = {"data": [stems, dots], "layout": layout}

    spec["table"] = _value_table(order, values_of, central, cis, group_label, value_label,
                                 estimator, show_ci)
    # A pre-aggregated table holds ONE value per category, so every pairwise test is n=1 vs n=1 and
    # every bracket would read "ns" whatever the data says. `composition` takes the ordering half
    # only for exactly this reason; here the same call is made per-run, because the same skill sees
    # both shapes.
    testable = sum(1 for k in order if len(values_of[k]) > 1)
    results = (test_pairs(parse_pairs(params.get("pairs")), values_of,
                          test=str(params.get("sig_test", "welch")),
                          correction=str(params.get("correction", "none")))
               if testable else [])
    if results:
        # Brackets are drawn against the DRAWN order, and index 0 is whatever sits at the axis
        # origin — which the horizontal reversal above flips.
        attach_brackets(spec, results, drawn, values_of, value_axis,
                        orientation="h" if horizontal else "v")
        # BOTH tables now — the swap is gone (docs/stats-tables/spec.md, slice 3). The figure used
        # to carry exactly one, so asking for `pairs` DISCARDED the ranked values (rank, n and the
        # asymmetric bootstrap CI bounds, none of which are readable off a dot) to make room for the
        # p-values behind the drawn stars. That trade was made the right way round — stars whose
        # p-values appear nowhere is the worse failure — but it was forced by the wire shape, not by
        # anything about the science.
        #
        # Array order is the runner's and it carries meaning (D4, no `role` field): the ranked values
        # are the primary result, and the pairwise table is the PROVENANCE of marks already drawn on
        # the canvas. The frontend stacks them in this order with both open.
        tbl = pairs_table(results, test=str(params.get("sig_test", "welch")),
                          correction=str(params.get("correction", "none")))
        if tbl:
            spec["table"] = [spec["table"], tbl]
    return spec


def _tip(value: float) -> str:
    return f"{value:.2f}" if abs(value) >= 0.01 or value == 0 else f"{value:.3g}"


def _as_float(raw, fallback: float) -> float:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return fallback
    return v if math.isfinite(v) else fallback


def _value_table(order, values_of, central, cis, group_label, value_label,
                 estimator: str, show_ci: bool) -> dict:
    """The ranked values as a Statistics table — rank, n, the central value, and its interval.

    The CI columns appear ONLY when an interval was actually computed for at least one category. A
    column of ``n/a`` headed "95% CI" on a pre-aggregated table advertises a claim the run never
    made; the note says which estimator and where the interval came from.
    """
    has_ci = show_ci and any(cis.get(k) for k in order)
    columns = ["rank", group_label, "n", f"{estimator} {value_label}".strip()]
    if has_ci:
        columns += ["CI low", "CI high"]
    rows = []
    for rank, key in enumerate(order, start=1):
        n = sum(1 for v in values_of[key] if v is not None and math.isfinite(float(v)))
        row = [rank, str(key), n, round(central[key], 4)]
        if has_ci:
            ci = cis.get(key)
            row += [round(ci[0], 4), round(ci[1], 4)] if ci else ["n/a", "n/a"]
        rows.append(row)
    note = f"ranked by {estimator}"
    if has_ci:
        note += (f"; 95% CI from a seeded percentile bootstrap "
                 f"({_BOOT_SAMPLES} resamples, n>=3 required)")
    return table(columns, rows, f"Ranked values ({note})")
