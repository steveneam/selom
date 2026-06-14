"""Benchmark scorecard — compare conditions across many metrics (paper Figs 6F/S6C).

Reads a conditions × metrics table. Two layouts of the same benchmark (Fig 6F shows
both): ``radar`` (default) draws one Scatterpolar polygon per condition over the shared
metric axes; ``heatmap`` draws a metrics × conditions colour grid — better when there
are many metrics or conditions to scan. Metrics are min–max normalized per column by
default so differently-scaled scores are comparable. The stub is a fixed
3-condition × 5-metric example of the same wire shape.
"""

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.scorecard.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict | None = None) -> dict:
    metrics = ["Identity", "Maturation", "Coverage", "Proportion", "Off-target"]
    series = {
        "Protocol A": [0.92, 0.61, 0.80, 0.74, 0.30],
        "Protocol B": [0.70, 0.85, 0.65, 0.60, 0.55],
        "Protocol C": [0.55, 0.40, 0.95, 0.88, 0.20],
    }
    if str((params or {}).get("layout") or "radar").lower() == "heatmap":
        return scorecard_heatmap_spec(metrics, series, "Benchmark scorecard (stub)", [0, 1])
    return scorecard_spec(metrics, series, True, "Benchmark scorecard (stub)", [0, 1])


def scorecard_spec(metrics, series, fill, title, radial_range=None) -> dict:
    """Shared radar spec — used by both the stub and the real engine. ``series`` maps a
    condition name to its per-metric values (aligned to ``metrics``). The polygon is
    closed by repeating the first metric/value."""
    metrics = list(metrics)
    closed = metrics + metrics[:1]
    data = []
    for name, values in series.items():
        vals = [round(float(v), 4) for v in values]
        data.append(
            {
                "type": "scatterpolar",
                "name": str(name),
                "theta": closed,
                "r": vals + vals[:1],
                "fill": "toself" if fill else "none",
                "opacity": 0.6 if fill else 1.0,
            }
        )

    radial = {"visible": True}
    if radial_range is not None:
        radial["range"] = list(radial_range)
    return {
        "data": data,
        "layout": {
            "title": {"text": title},
            "polar": {"radialaxis": radial},
            "legend": {"title": {"text": "condition"}},
        },
    }


def scorecard_heatmap_spec(metrics, series, title, zrange=None) -> dict:
    """Shared scorecard-heatmap spec — the same benchmark as ``scorecard_spec`` drawn as
    a metrics × conditions colour grid (rows = metrics, columns = conditions). ``series``
    maps a condition name to its per-metric values (aligned to ``metrics``). ``zrange``
    pins the colour scale (e.g. ``[0, 1]`` when normalized) so panels stay comparable;
    pass ``None`` to autoscale raw scores. No xaxis/yaxis is emitted so the categorical
    tick labels render straight from ``x``/``y``."""
    metrics = list(metrics)
    conditions = list(series.keys())
    z = [[round(float(series[c][i]), 4) for c in conditions] for i in range(len(metrics))]
    trace = {
        "type": "heatmap",
        "x": [str(c) for c in conditions],
        "y": [str(m) for m in metrics],
        "z": z,
        "colorscale": "Viridis",
        "colorbar": {"title": {"text": "score"}},
    }
    if zrange is not None:
        trace["zmin"], trace["zmax"] = float(zrange[0]), float(zrange[1])
    return {"data": [trace], "layout": {"title": {"text": title}}}
