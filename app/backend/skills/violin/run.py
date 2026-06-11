"""Marker-gene expression violins, one per cluster.

Stub (dependency-free, deterministic) vs. the real scanpy engine. Picks a marker
gene (param ``gene``, else the highest-variance gene) and draws a violin of its
log1p expression for each ``groupby`` level (Leiden cluster by default).
"""

import math

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy"):
        from skills.violin.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic violins for four clusters (trig spread, no RNG)."""
    means = [0.4, 1.8, 0.9, 2.6]
    traces = []
    for gi, mean in enumerate(means):
        ys = [round(mean + 0.6 * math.sin(gi * 1.7 + j * 0.5), 4) for j in range(24)]
        traces.append(
            {
                "type": "violin",
                "name": f"cluster {gi}",
                "y": ys,
                "box": {"visible": True},
                "meanline": {"visible": True},
                "points": False,
            }
        )
    return {
        "data": traces,
        "layout": {
            "title": {"text": "Marker expression by cluster (stub)"},
            "xaxis": {"title": {"text": "cluster"}},
            "yaxis": {"title": {"text": "expression (log1p)"}},
        },
    }
