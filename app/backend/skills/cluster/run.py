"""Leiden clustering — cluster-size bar chart (+ adjustable resolution).

Entrypoint dispatches stub vs. the real scanpy engine (``run_real.py``). See
``skills._engine`` for selection. The stub is a dependency-free deterministic bar
chart so the golden test runs with zero heavy deps.
"""

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy"):
        from skills.cluster.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic cluster-size bar — six clusters, descending sizes."""
    sizes = [812, 533, 421, 318, 274, 142]
    names = [str(i) for i in range(len(sizes))]
    return {
        "data": [
            {
                "type": "bar",
                "name": "cells",
                "x": names,
                "y": sizes,
                "marker": {"color": "#22d3ee"},
            }
        ],
        "layout": {
            "title": {
                "text": "Leiden clusters (stub)",
                "subtitle": {"text": "6 clusters · silhouette 0.50 — higher = cleaner separation"},
            },
            "xaxis": {"title": {"text": "cluster"}},
            "yaxis": {"title": {"text": "cells"}},
            "bargap": 0.25,
        },
    }
