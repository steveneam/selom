"""Composition / proportion bar across conditions.

Plots a category × condition table (e.g. cell-type deconvolution proportions, or cluster
composition per sample) as grouped or stacked bars. Pairs naturally with ``annotate``
(cell-type makeup) and deconvolution outputs. Real engine in ``run_real.py``; the stub
here is a deterministic grouped bar of the same wire shape.
"""

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.composition.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic composition: 4 cell types × two conditions (DR vs PD)."""
    categories = ["Rods", "Müller glia", "Microglia", "Bipolar"]
    series = {"DR": [21.8, 2.6, 9.5, 10.4], "PD": [4.5, 22.2, 15.2, 14.3]}
    return _composition_spec(categories, series, "grouped", "h", "Composition (stub)")


def _composition_spec(categories, series, mode, orientation, title) -> dict:
    """Editable composition-bar spec (shared by stub + real engine)."""
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
