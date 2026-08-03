"""Grouped box-and-whisker distributions.

Compares a numeric measure across categorical groups as box plots (quartiles +
median, 1.5×IQR whiskers, outliers), the distribution-comparison companion to
``violin``. Pairs with method/condition benchmarks — e.g. a per-method correlation
comparison (Cepo vs Limma vs HVG, Kim et al. 2023 Fig 2C). Real engine in
``run_real.py`` (long-form CSV → one box per group); the stub here is a
deterministic three-group comparison of the same wire shape.
"""

from skills._engine import to_bool, use_real_engine
from skills._stats import (
    attach_brackets,
    count_labels,
    pairs_table,
    parse_pairs,
    resolve_order,
    test_pairs,
)

# Plotly ``boxpoints`` spellings exposed via the ``points`` param.
_POINTS = {"outliers": "outliers", "all": "all", "none": False,
           "suspectedoutliers": "suspectedoutliers"}


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.boxplot.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    """Deterministic method-concordance comparison: Cepo > Limma > HVG (Fig 2C shape)."""
    groups = {
        "Cepo":  [0.86, 0.88, 0.84, 0.90, 0.87, 0.89, 0.83, 0.91],
        "Limma": [0.71, 0.68, 0.74, 0.66, 0.72, 0.70, 0.63, 0.76],
        "HVG":   [0.58, 0.61, 0.55, 0.64, 0.59, 0.52, 0.66, 0.57],
    }
    return boxplot_spec(groups, params, "mean cross-dataset correlation",
                        "cell-identity method", "Method concordance (stub)")


def boxplot_spec(groups: dict, params: dict, value_label: str, group_label: str,
                 title: str) -> dict:
    """Editable Plotly box spec (shared by stub + real engine).

    ``groups`` = {label: [values]}. One ``box`` trace per group so each is
    independently editable and legend-toggleable; Plotly computes the quartiles /
    whiskers / outliers from the raw values client-side.

    Grouping + annotation vocabulary (``skills._stats``, shared with every other categorical
    skill): ``order`` (explicit category order) · ``add_count`` (``n=`` welded to each label) ·
    ``pairs`` (``"A~B, C~D"`` → test + bracket + stars, with ``sig_test`` and ``correction``).
    With no ``pairs`` the spec is unchanged, which is what keeps the golden stable.
    """
    horizontal = str(params.get("orientation", "v")).lower().startswith("h")
    boxpoints = _POINTS.get(str(params.get("points", "outliers")).lower(), "outliers")
    notched = to_bool(params.get("notched", False))

    order = resolve_order(list(groups.keys()), params.get("order"))
    values_of = {k: groups[k] for k in order}
    # add_count welds n= to the trace NAME rather than emitting a separate annotation, so the
    # count cannot drift out of alignment when the axis reorders (see _stats.count_labels).
    names = (count_labels(order, values_of) if to_bool(params.get("add_count", False))
             else {k: str(k) for k in order})

    data = []
    for key in order:
        vals = [round(float(v), 4) for v in values_of[key]]
        trace = {"type": "box", "name": names[key], "boxpoints": boxpoints,
                 "notched": notched}
        trace["x" if horizontal else "y"] = vals
        data.append(trace)

    value_axis = {"title": {"text": value_label}, "zeroline": False}
    cat_axis = {"title": {"text": group_label}, "type": "category"}
    layout = {
        "title": {"text": title},
        "xaxis": value_axis if horizontal else cat_axis,
        "yaxis": cat_axis if horizontal else value_axis,
        "legend": {"title": {"text": group_label}},
        "boxgap": 0.3,
        "showlegend": False,
        "plot_bgcolor": "white",
    }
    spec = {"data": data, "layout": layout}

    results = test_pairs(parse_pairs(params.get("pairs")), values_of,
                         test=str(params.get("sig_test", "welch")),
                         correction=str(params.get("correction", "none")))
    if results:
        attach_brackets(spec, results, order, values_of, value_axis,
                        orientation="h" if horizontal else "v")
        tbl = pairs_table(results, test=str(params.get("sig_test", "welch")),
                          correction=str(params.get("correction", "none")))
        if tbl:
            spec["table"] = tbl
    return spec
