"""Entrypoint for the scRNA UMAP skill — dispatches stub vs. real engine.

`run()` is the registry entrypoint (see skill.json). It selects the engine so the
SAME entrypoint works in two modes:

  * REAL  — the scanpy engine in ``run_scanpy.py``, used when the scverse stack is
    installed (``uv sync --extra scrna``) and ``SELOM_UMAP_ENGINE`` != "stub".
  * STUB  — a dependency-free deterministic 2D scatter, so the light skeleton (and
    CI / contract tests) run end-to-end with ZERO heavy deps.

Engine selection via ``SELOM_UMAP_ENGINE`` (default "auto"):
  auto   -> real if scanpy is importable, else stub
  scanpy -> force real (raises if scanpy is missing)
  stub   -> force stub
"""

import math
import os
from importlib.util import find_spec


def run(data_path: str, params: dict) -> dict:
    engine = os.environ.get("SELOM_UMAP_ENGINE", "auto").lower()
    use_real = engine == "scanpy" or (engine == "auto" and find_spec("scanpy") is not None)
    if use_real:
        from skills.umap_scrna.run_scanpy import run as run_real
        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Dependency-free deterministic UMAP-shaped scatter (no scanpy/numpy import).

    Three labelled clusters, ~10 points each, placed via trig offsets so the output
    is stable across runs without any RNG. Returns a valid editable Plotly spec.
    """
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
