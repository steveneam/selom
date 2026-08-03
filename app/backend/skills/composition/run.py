"""Composition / proportion bar across conditions.

Plots a category × condition table (e.g. cell-type deconvolution proportions, or cluster
composition per sample) as grouped or stacked bars. Pairs naturally with ``annotate``
(cell-type makeup) and deconvolution outputs. Real engine in ``run_real.py``; the stub
here is a deterministic grouped bar of the same wire shape.
"""

from skills._engine import use_real_engine
from skills._stats import resolve_order

# WHY THIS SKILL HAS `order` BUT NOT `pairs` / `add_count`.
# The shared significance engine (skills/_stats.py) gives every categorical skill pairwise tests,
# brackets and n= labels. Composition takes only the ordering half, and that is a data fact, not an
# oversight: its input is a category x condition matrix with ONE value per cell (see run_real —
# `series = {col: num[col].tolist()}`). There is no replicate distribution to test, so every
# bracket would compare n=1 against n=1, `compare_groups` would return None, and the figure would
# print "ns" over every pair no matter what the data said. A bracket that cannot be anything but
# "ns" is a claim the data cannot support. `add_count` is out for the same reason — n is always 1.
# If composition ever ingests replicate-level input, both drop in unchanged.


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.composition.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    """Deterministic composition: 4 cell types × two conditions (DR vs PD)."""
    categories = ["Rods", "Müller glia", "Microglia", "Bipolar"]
    series = {"DR": [21.8, 2.6, 9.5, 10.4], "PD": [4.5, 22.2, 15.2, 14.3]}
    return _composition_spec(categories, series, "grouped", "h", "Composition (stub)", params)


def _composition_spec(categories, series, mode, orientation, title, params=None) -> dict:
    """Editable composition-bar spec (shared by stub + real engine).

    ``order`` (``skills._stats.resolve_order``) reorders the CATEGORY axis explicitly, alongside
    the existing data-driven ``sort_by``; unnamed categories keep their incoming order."""
    categories, series = _ordered(categories, series, (params or {}).get("order"))
    horizontal = str(orientation).lower().startswith("h")
    data = []
    for name, values in series.items():
        vals = [round(float(v), 4) for v in values]
        trace = {"type": "bar", "name": str(name)}
        if horizontal:
            trace.update({"orientation": "h", "x": vals, "y": list(categories)})
        else:
            trace.update({"x": list(categories), "y": vals})
        data.append(trace)

    value_axis = {"title": {"text": "proportion / count"}}
    cat_axis = {"title": {"text": "category"}, "type": "category"}
    return {
        "data": data,
        "layout": {
            "title": {"text": title},
            "barmode": "stack" if str(mode).lower() == "stacked" else "group",
            "xaxis": value_axis if horizontal else cat_axis,
            "yaxis": cat_axis if horizontal else value_axis,
            "legend": {"title": {"text": "condition"}},
            "bargap": 0.25,
            "plot_bgcolor": "white",
        },
    }


def _ordered(categories, series, order):
    """Apply an explicit category ``order``, carrying every series' values along with it.

    The reorder is a permutation of INDICES applied to each series, so a value can never come
    unstuck from its category — the failure mode that would silently mislabel every bar."""
    categories = [str(c) for c in categories]
    resolved = resolve_order(categories, order)
    if resolved == categories:
        return categories, series
    pos = {c: i for i, c in enumerate(categories)}
    idx = [pos[c] for c in resolved]
    return resolved, {name: [vals[i] for i in idx] for name, vals in series.items()}
