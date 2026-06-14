"""Clustered correlation heatmap (sample×sample or feature×feature).

Reads a numeric feature × sample matrix and renders the Pearson/Spearman correlation
matrix as a single editable Plotly heatmap on a diverging RdBu scale fixed to [-1, 1],
with rows and columns *symmetrically* reordered by hierarchical clustering so
correlated items sit together — the standard replicate-concordance / batch-structure
view (paper Figs 2A/4E/6C). Distinct from ``heatmap`` (z-scored expression values).
The stub is a deterministic symmetric matrix of the same wire shape.
"""

import math

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas", "scipy"):
        from skills.corr_heatmap.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    n = 6
    labels = [f"S{i + 1}" for i in range(n)]
    # cos(k·(i−j)) is symmetric with a unit diagonal — a valid correlation-like matrix.
    z = [[round(math.cos(0.6 * (i - j)), 3) for j in range(n)] for i in range(n)]
    return corr_spec(z, labels, "Sample correlation (stub)")


def corr_spec(z, labels, title) -> dict:
    """Shared correlation-heatmap spec — used by both the stub and the real engine.

    Square cells (``scaleanchor``), diverging RdBu centred at 0 and clamped to the
    correlation range so colour is comparable across figures.
    """
    labels = list(labels)
    return {
        "data": [
            {
                "type": "heatmap",
                "z": z,
                "x": labels,
                "y": labels,
                "colorscale": "RdBu",
                "reversescale": True,
                "zmid": 0,
                "zmin": -1,
                "zmax": 1,
                "colorbar": {"title": {"text": "r"}},
            }
        ],
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": ""}, "type": "category", "automargin": True},
            "yaxis": {
                "title": {"text": ""},
                "type": "category",
                "automargin": True,
                "scaleanchor": "x",
                "scaleratio": 1,
            },
        },
    }
