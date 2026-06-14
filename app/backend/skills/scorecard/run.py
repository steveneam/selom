"""Benchmark scorecard — radar/spider chart comparing conditions across metrics.

Reads a conditions × metrics table and draws one Scatterpolar polygon per condition
over the shared metric axes, so several models / protocols can be ranked on many
scores at once (paper Figs 6F/S6C — organoid fidelity benchmark). Metrics are min–max
normalized per column by default so differently-scaled scores share one radius. The
stub is a fixed 3-condition × 5-metric example of the same wire shape.
"""

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.scorecard.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    metrics = ["Identity", "Maturation", "Coverage", "Proportion", "Off-target"]
    series = {
        "Protocol A": [0.92, 0.61, 0.80, 0.74, 0.30],
        "Protocol B": [0.70, 0.85, 0.65, 0.60, 0.55],
        "Protocol C": [0.55, 0.40, 0.95, 0.88, 0.20],
    }
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
