"""Offline stub entrypoint for the scRNA UMAP skill.

This is a dependency-free stub so the skeleton runs end-to-end with ZERO heavy deps:
it fabricates a small deterministic 2D scatter (no scanpy/anndata/numpy import) and
returns a valid editable Plotly figure spec. The REAL engine lives in `run_scanpy.py`
behind the `[omics]` extra (`uv sync --extra omics`).
"""

import math


def run(data_path: str, params: dict) -> dict:
    # Three labelled clusters, ~10 points each (~30 total), placed deterministically
    # via trig offsets so the output is stable across runs without any RNG.
    centers = [(0.0, 0.0), (5.0, 1.0), (2.5, 4.5)]
    names = ["Cluster 0", "Cluster 1", "Cluster 2"]
    points_per_cluster = 10

    traces = []
    for cluster_index, (center_x, center_y) in enumerate(centers):
        xs, ys = [], []
        for j in range(points_per_cluster):
            angle = cluster_index * 2.39996 + j * 0.7
            radius = 0.6 + 0.4 * ((j % 5) / 4.0)
            xs.append(round(center_x + radius * math.cos(angle), 4))
            ys.append(round(center_y + radius * math.sin(angle), 4))
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "name": names[cluster_index],
            "x": xs,
            "y": ys,
        })

    return {
        "data": traces,
        "layout": {"title": {"text": "scRNA UMAP (stub)"}},
    }
