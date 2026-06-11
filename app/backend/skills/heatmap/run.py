"""Expression heatmap of marker / top-variable genes (row z-scored).

scRNA path ranks markers per cluster and shows mean expression per cluster; bulk
CSV path shows the top-variance genes across samples. Both render a single Plotly
heatmap trace on a diverging RdBu scale centred at zero. The stub is a deterministic
z-matrix in the same shape.
"""

import math

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.heatmap.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    n_genes, n_groups = 20, 6
    genes = [f"GENE{i + 1}" for i in range(n_genes)]
    groups = [f"c{j}" for j in range(n_groups)]
    z = [[round(math.sin(i * 0.5 + j * 1.1), 3) for j in range(n_groups)] for i in range(n_genes)]
    return heatmap_spec(z, groups, genes, "Marker heatmap (stub)", "cluster")


def heatmap_spec(z, x_labels, y_labels, title, x_title) -> dict:
    """Shared heatmap spec — used by both the stub and the real engine."""
    return {
        "data": [
            {
                "type": "heatmap",
                "z": z,
                "x": x_labels,
                "y": y_labels,
                "colorscale": "RdBu",
                "reversescale": True,
                "zmid": 0,
                "colorbar": {"title": {"text": "z-score"}},
            }
        ],
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": x_title}},
            "yaxis": {"title": {"text": "gene"}, "automargin": True},
        },
    }
