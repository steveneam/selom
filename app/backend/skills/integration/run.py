"""Entrypoint for the scRNA integration skill — dispatches stub vs. real engine.

Multi-library batch correction: several single-cell samples are co-embedded so the
same cell type from different batches lands together (rather than splitting by batch).
The real engine in ``run_real.py`` runs Scanpy + Harmony; the stub here is a
dependency-free deterministic UMAP-shaped scatter that shows the *post-integration*
state — both batches interspersed across shared clusters — so the contract / golden
tests and the light skeleton run end-to-end with ZERO heavy deps.

Engine selection via ``SELOM_SKILLS_ENGINE`` (shared ``_engine.use_real_engine``):
real iff scanpy AND harmonypy are importable (``uv sync --extra omics``), else stub.
"""

import math

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy", "harmonypy"):
        from skills.integration.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Dependency-free deterministic "integrated" scatter (no scanpy/numpy import).

    Three shared clusters, each populated by points from BOTH batches placed via trig
    offsets — so the two colours interleave inside every cluster, the visual signature
    of a successful integration (batches mixed, cell-type structure kept). Stable across
    runs without any RNG. Returns a valid editable Plotly spec.
    """
    centers = [(0.0, 0.0), (5.0, 1.0), (2.5, 4.5)]
    batches = ["Batch A", "Batch B"]
    points_per_cluster = 8

    traces = []
    for batch_index, batch_name in enumerate(batches):
        xs, ys = [], []
        for cluster_index, (center_x, center_y) in enumerate(centers):
            for j in range(points_per_cluster):
                # offset both batches around the SAME centres (interleaved => mixed)
                angle = cluster_index * 2.39996 + j * 0.7 + batch_index * 0.35
                radius = 0.6 + 0.4 * ((j % 5) / 4.0)
                xs.append(round(center_x + radius * math.cos(angle), 4))
                ys.append(round(center_y + radius * math.sin(angle), 4))
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "name": batch_name,
            "x": xs,
            "y": ys,
        })

    return {
        "data": traces,
        "layout": {"title": {"text": "scRNA integration — Harmony (stub)"}},
    }
