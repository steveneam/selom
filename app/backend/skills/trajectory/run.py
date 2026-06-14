"""Trajectory & pseudotime (PAGA + diffusion pseudotime).

Builds a diffusion map, abstracts the cluster graph with PAGA, and orders cells along
diffusion pseudotime from a chosen root. The figure is the canonical trajectory view: the
embedding coloured by pseudotime (viridis) with the PAGA connectivity graph overlaid —
nodes = cluster centroids (size = cell count), edges = connectivity (width = weight). All
Scanpy (BSD-3), no R, no GPU. Real engine in ``run_real.py``; the stub here is a
deterministic version of the same wire shape.
"""

from skills._engine import use_real_engine

VIRIDIS = "Viridis"
EDGE_COLOR = "#475569"
NODE_COLOR = "#0f172a"
# bold lineage-curve colours that read over a Viridis cell field
LINEAGE_COLORS = ["#ef4444", "#2563eb", "#d946ef", "#059669", "#f59e0b"]


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy"):
        from skills.trajectory.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic pseudotime embedding + PAGA overlay: 3 clusters along a linear
    trajectory (0 -> 1 -> 2), pseudotime rising across them."""
    import math

    centers = [(0.0, 0.0), (5.0, 1.0), (9.0, 3.5)]
    per = 10
    cell_x, cell_y, pseudotime = [], [], []
    for ci, (cx, cy) in enumerate(centers):
        for j in range(per):
            angle = ci * 2.39996 + j * 0.7
            radius = 0.6 + 0.4 * ((j % 5) / 4.0)
            cell_x.append(round(cx + radius * math.cos(angle), 4))
            cell_y.append(round(cy + radius * math.sin(angle), 4))
            pseudotime.append(round((ci + (j % 5) / 4.0) / 3.0, 4))

    edges = [(0.0, 0.0, 5.0, 1.0, 6.0), (5.0, 1.0, 9.0, 3.5, 4.0)]
    nodes = [(0.0, 0.0, "0", 28.0), (5.0, 1.0, "1", 24.0), (9.0, 3.5, "2", 20.0)]
    # one smooth lineage threading the cluster centroids (Plotly splines the control points)
    lineages = [([0.0, 5.0, 9.0], [0.0, 1.0, 3.5], "Lineage 1")]
    return _trajectory_spec(
        cell_x, cell_y, pseudotime, edges, nodes,
        "Trajectory & pseudotime (stub)", "root cluster 0 · 3 clusters", lineages,
    )


def _trajectory_spec(cell_x, cell_y, pseudotime, edges, nodes, title, subtitle, lineages=None) -> dict:
    """Assemble the editable pseudotime-embedding + PAGA-overlay spec (stub + real).

    ``lineages`` is an optional list of ``(xs, ys, name)`` smooth principal-curve
    lineages (simpleppt + spline) drawn prominently on top of the faint PAGA backbone —
    the "flowy" Slingshot-style look. Left None it adds nothing.
    """
    data = [
        {
            "type": "scattergl",
            "mode": "markers",
            "name": "cells",
            "x": cell_x,
            "y": cell_y,
            "marker": {
                "color": pseudotime,
                "colorscale": VIRIDIS,
                "showscale": True,
                "colorbar": {"title": {"text": "pseudotime"}},
                "size": 4,
                "opacity": 0.65,
            },
            "hovertemplate": "pseudotime %{marker.color:.2f}<extra></extra>",
        }
    ]
    # PAGA edges — one line trace each so width can encode connectivity; off the legend.
    for x0, y0, x1, y1, width in edges:
        data.append(
            {
                "type": "scatter",
                "mode": "lines",
                "x": [x0, x1],
                "y": [y0, y1],
                "line": {"color": EDGE_COLOR, "width": width},
                "opacity": 0.6,
                "hoverinfo": "skip",
                "showlegend": False,
            }
        )
    # Smooth principal-curve lineages, drawn over the cells/backbone (spline shape so the
    # theme keeps them prominent rather than demoting them like a PAGA edge).
    for i, (lx, ly, name) in enumerate(lineages or []):
        data.append(
            {
                "type": "scatter",
                "mode": "lines",
                "name": name,
                "x": lx,
                "y": ly,
                "line": {"color": LINEAGE_COLORS[i % len(LINEAGE_COLORS)], "width": 4, "shape": "spline"},
                "opacity": 0.95,
                "hoverinfo": "skip",
            }
        )
    # PAGA nodes — cluster centroids, size = cell count.
    data.append(
        {
            "type": "scatter",
            "mode": "markers+text",
            "name": "clusters",
            "x": [n[0] for n in nodes],
            "y": [n[1] for n in nodes],
            "text": [n[2] for n in nodes],
            "textposition": "top center",
            "marker": {
                "size": [n[3] for n in nodes],
                "color": NODE_COLOR,
                "line": {"color": "white", "width": 1.5},
            },
            "hovertemplate": "cluster %{text}<extra></extra>",
        }
    )
    return {
        "data": data,
        "layout": {
            "title": {"text": title, "subtitle": {"text": subtitle}},
            "xaxis": {"title": {"text": "UMAP 1"}, "zeroline": False},
            "yaxis": {"title": {"text": "UMAP 2"}, "zeroline": False},
            "legend": {"title": {"text": ""}},
            "plot_bgcolor": "white",
        },
    }
