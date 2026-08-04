"""Ridge plot (joyplot) — one density curve per group, stacked and overlapping.

The distribution-shape companion to ``boxplot`` and ``violin``. A box reduces a distribution to five
numbers, which is exactly what hides bimodality: two well-separated modes and one broad unimodal
spread produce near-identical boxes. A ridge shows the shape, and stacking makes a dozen groups
comparable in the vertical space a dozen violins would need.

Real engine in ``run_real.py``; the stub here is a deterministic three-group stack.

**The KDE is hand-rolled and that is deliberate.** It is ~15 lines of Gaussian sum with Silverman's
bandwidth, and writing it here means the dependency-free stub draws the SAME curve as the real
engine rather than a fabricated stand-in — the stub/real split is a wire-shape contract, and a stub
whose geometry comes from somewhere else is the fake-science landmine WS1.1 exists to stop. scipy's
``gaussian_kde`` (which cnsplots uses) agrees with this to ~1e-12 on the same bandwidth; the
regression test pins that.
"""

import math

from skills._engine import to_bool, use_real_engine
from skills._stats import count_labels, resolve_order
from skills._table import table

_GRID = 200            # points per curve — smooth at any width, cheap to edit in the browser
_MAX_GROUPS = 25
_MIN_VALUES = 3        # below this a density estimate describes the bandwidth, not the data


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.ridge.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    """Deterministic three-group stack — one bimodal group a box plot would flatten."""
    groups = {
        "Rods": [round(3.0 + 0.35 * math.sin(i * 1.7) + 0.02 * i, 3) for i in range(40)],
        "Cones": [round(1.9 + 0.30 * math.cos(i * 2.1), 3) for i in range(40)],
        # Two separated modes: identical quartiles to a broad unimodal spread, obviously different here.
        "Bipolar": ([round(0.9 + 0.12 * math.sin(i * 1.3), 3) for i in range(20)]
                    + [round(2.6 + 0.12 * math.cos(i * 1.1), 3) for i in range(20)]),
    }
    return ridge_spec(groups, params, "log expression", "cell type",
                      "Expression distribution (stub)")


def silverman_bandwidth(values) -> float:
    """Silverman's rule-of-thumb bandwidth — ``0.9 * min(sd, IQR/1.34) * n^(-1/5)``.

    The same default ``scipy.stats.gaussian_kde`` and R's ``density()`` reach for. The IQR term is
    what keeps one outlier from inflating the bandwidth and smearing the whole curve flat.
    Degenerate input (zero spread) falls back to a small positive width so the Gaussian sum stays
    defined rather than dividing by zero.
    """
    vals = sorted(float(v) for v in values)
    n = len(vals)
    if n < 2:
        return 1.0
    mean = sum(vals) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
    iqr = _quantile(vals, 0.75) - _quantile(vals, 0.25)
    spread = min(sd, iqr / 1.34) if iqr > 0 else sd
    if spread <= 0:
        spread = abs(mean) * 0.01 or 1.0
    return 0.9 * spread * n ** (-0.2)


def _quantile(sorted_vals, q: float) -> float:
    """Linear-interpolation quantile (numpy's default 'linear' method)."""
    if not sorted_vals:
        return 0.0
    pos = (len(sorted_vals) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def gaussian_kde(values, grid, bandwidth: float) -> list:
    """Density of ``values`` evaluated on ``grid`` — a normalized sum of Gaussians, one per point.

    Returns a true probability density (it integrates to 1), NOT a peak-normalized curve. Which one
    is drawn is a display decision made in :func:`ridge_spec`, and keeping it out of here is what
    lets the ``scale="common"`` mode compare groups honestly.
    """
    if bandwidth <= 0:
        bandwidth = 1.0
    norm = 1.0 / (len(values) * bandwidth * math.sqrt(2.0 * math.pi))
    out = []
    for x in grid:
        total = 0.0
        for v in values:
            z = (x - v) / bandwidth
            if -40.0 < z < 40.0:            # exp underflows past this; skipping it is exact enough
                total += math.exp(-0.5 * z * z)
        out.append(total * norm)
    return out


def ridge_spec(groups: dict, params: dict, value_label: str, group_label: str,
               title: str) -> dict:
    """Editable Plotly ridge spec (shared by stub + real engine).

    ``groups`` = ``{label: [values]}``. Each ridge is a CLOSED filled polygon (``fill: "toself"``),
    not a ``layout.shape``: a shapes-only diagram is a picture rather than an editable figure and
    fails ``smoke.check_figure``'s non-empty-``data`` rule, correctly — the same call ``venn`` made.

    ``scale`` is the honesty knob. cnsplots peak-normalizes every ridge (``y / y.max()``), which is
    the ridgeline convention and makes SHAPES comparable — but it also draws a 5-observation group
    exactly as tall as a 5000-observation one. ``common`` keeps the true densities on one scale so
    height means something. Peak-normalized stays the default because it is the convention a reader
    expects, and the ``n=`` label carries the count either way.
    """
    order = resolve_order(list(groups.keys()), params.get("order"))[:_MAX_GROUPS]
    usable = {k: [float(v) for v in groups[k]] for k in order if len(groups[k]) >= _MIN_VALUES}
    # A group is dropped only when a density estimate is undefined for it — too few points, or no
    # spread at all. Dropped groups are NAMED in the table rather than vanishing, because a missing
    # ridge otherwise reads as "this group had no data".
    dropped = [k for k in order if k not in usable
               or len(set(usable.get(k, []))) < 2]
    usable = {k: v for k, v in usable.items() if len(set(v)) >= 2}
    if not usable:
        raise ValueError(
            f"ridge: no group has {_MIN_VALUES}+ values with any spread — a density estimate "
            "would describe the bandwidth rather than the data. Try boxplot (style=strip), which "
            "draws every individual value and needs no estimate."
        )
    order = [k for k in order if k in usable]

    overlap = _clamp(_as_float(params.get("overlap"), 0.55), 0.0, 0.95)
    peak_normalized = str(params.get("scale", "peak")).strip().lower() != "common"
    show_median = to_bool(params.get("median_line", True))
    labels = (count_labels(order, usable) if to_bool(params.get("add_count", True))
              else {k: str(k) for k in order})

    lo = min(v for vals in usable.values() for v in vals)
    hi = max(v for vals in usable.values() for v in vals)
    pad = (hi - lo) * 0.05 or (abs(hi) * 0.05 or 1.0)
    grid = [lo - pad + (hi - lo + 2 * pad) * i / (_GRID - 1) for i in range(_GRID)]

    densities = {k: gaussian_kde(v, grid, silverman_bandwidth(v)) for k, v in usable.items()}
    if peak_normalized:
        curves = {k: [(y / (max(d) or 1.0)) for y in d] for k, d in densities.items()}
    else:
        ceiling = max((max(d) for d in densities.values()), default=1.0) or 1.0
        curves = {k: [y / ceiling for y in d] for k, d in densities.items()}

    step = 1.0 - overlap
    baselines = {k: (len(order) - 1 - i) * step for i, k in enumerate(order)}

    data, tick_vals, tick_text, table_rows = [], [], [], []
    # TOP ridge first, so it is drawn BEHIND and each lower ridge occludes the one above it. That
    # cascade is what makes a joyplot read as overlapping sheets of paper. Drawn the other way the
    # stack still "works" and every assertion passes, but the depth cue is inverted and the figure
    # reads as a tangle — which is how it rendered the first time.
    for key in order:
        base = baselines[key]
        curve = curves[key]
        # Closed polygon: along the top of the curve, then back along the baseline.
        xs = [round(x, 4) for x in grid] + [round(x, 4) for x in reversed(grid)]
        ys = ([round(base + y, 4) for y in curve]
              + [round(base, 4)] * len(grid))
        # NEITHER `fillcolor` NOR `line.color` is set, and both omissions are load-bearing. On a
        # `fill: "toself"` scatter Plotly derives the fill from the trace's LINE colour at half
        # alpha, so pinning the outline to a neutral grey silently repaints every ridge grey and
        # the colourway never arrives (it did, on the first pass). Leaving both unset lets the theme
        # colour the fill and its matching edge together, as cnsplots does (`edgecolor=colors[i]`).
        #
        # That inherited half-alpha is also the right answer here, rather than cnsplots' opaque
        # fill. cnsplots can afford occlusion because it draws at overlap 0.5 with no median marks;
        # at the overlaps this exposes, an opaque front ridge buries most of the one behind it, and
        # comparing SHAPES is the entire reason to choose a ridge over a box. The per-ridge outline
        # and baseline are what keep a blended overlap from reading as a category of its own.
        data.append({"type": "scatter", "mode": "lines", "name": labels[key],
                     "x": xs, "y": ys, "fill": "toself",
                     "line": {"width": 1.0},
                     "hoverinfo": "name", "showlegend": False})
        tick_vals.append(round(base, 4))
        tick_text.append(labels[key])

    if show_median:
        med_x, med_y = [], []
        for key in order:
            base = baselines[key]
            vals = sorted(usable[key])
            m = _quantile(vals, 0.5)
            height = _height_at(grid, curves[key], m)
            med_x += [round(m, 4), round(m, 4), None]
            med_y += [round(base, 4), round(base + height, 4), None]
        if med_x:
            data.append({"type": "scatter", "mode": "lines", "name": "median",
                         "x": med_x, "y": med_y, "showlegend": False, "hoverinfo": "skip",
                         "line": {"color": "rgba(20,20,20,0.65)", "width": 1.2}})

    for key in order:
        vals = sorted(usable[key])
        table_rows.append([str(key), len(vals),
                           round(_quantile(vals, 0.5), 4),
                           round(_quantile(vals, 0.25), 4),
                           round(_quantile(vals, 0.75), 4),
                           round(min(vals), 4), round(max(vals), 4),
                           round(silverman_bandwidth(vals), 4)])

    layout = {
        "title": {"text": title},
        "xaxis": {"title": {"text": value_label}, "zeroline": False,
                  "range": [round(lo - pad, 4), round(hi + pad, 4)]},
        # Ticks sit at each ridge's BASELINE, which is what replaces cnsplots' free-floating text
        # labels — those are drawn at the data minimum and run off the left edge on any real range.
        "yaxis": {"title": {"text": group_label}, "tickmode": "array",
                  "tickvals": tick_vals, "ticktext": tick_text,
                  "zeroline": False, "showgrid": False,
                  "range": [-step * 0.35, (len(order) - 1) * step + 1.25]},
        "showlegend": False,
        "plot_bgcolor": "white",
    }
    spec = {"data": data, "layout": layout}
    spec["table"] = _ridge_table(table_rows, dropped, peak_normalized, group_label, value_label)
    return spec


def _height_at(grid, curve, x: float) -> float:
    """The curve's height at ``x`` — nearest grid point, which at 200 points is sub-pixel."""
    best, best_d = 0.0, None
    for gx, gy in zip(grid, curve):
        d = abs(gx - x)
        if best_d is None or d < best_d:
            best, best_d = gy, d
    return best


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _as_float(raw, fallback: float) -> float:
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return fallback
    return v if math.isfinite(v) else fallback


def _ridge_table(rows, dropped, peak_normalized: bool, group_label: str,
                 value_label: str) -> dict:
    """Five-number summary + the bandwidth per ridge.

    The bandwidth is a column because it is the one parameter that decides what the reader SEES: a
    curve is as bimodal as its bandwidth allows, and a density plot that does not disclose its
    smoothing is asking to be taken on trust.
    """
    columns = [group_label or "group", "n", "median", "Q1", "Q3", "min", "max", "bandwidth"]
    note = ("each ridge peak-normalized, so shapes compare but heights do not"
            if peak_normalized else
            "one common density scale, so heights compare directly")
    note += "; Gaussian KDE, Silverman bandwidth"
    if dropped:
        note += (f"; excluded (too few values or no spread): "
                 f"{', '.join(str(d) for d in dropped[:6])}"
                 f"{'…' if len(dropped) > 6 else ''}")
    return table(columns, rows, f"Distribution summary ({note})")
