"""Expression heatmap of marker / top-variable genes (row z-scored).

scRNA path ranks markers per cluster and shows mean expression per cluster; bulk
CSV path shows the top-variance genes across samples. Both render a single Plotly
heatmap trace on a diverging RdBu scale centred at zero. The stub is a deterministic
z-matrix in the same shape.
"""

import math

from skills._engine import use_real_engine
from skills._genes import display_symbols


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


def heatmap_spec(z, x_labels, y_labels, title, x_title, dendro=None) -> dict:
    """Shared heatmap spec — used by both the stub and the real engine.

    ``dendro`` (optional) ``{"icoord", "dcoord"}`` from a SciPy row dendrogram draws the
    clustering tree in a left gutter, aligned to the (already leaf-ordered) heatmap rows —
    the standard clustermap look. Row labels move to the right so the tree owns the left.
    When ``dendro`` is None the spec is exactly the single-trace heatmap as before.
    """
    # Show readable gene SYMBOLS on the axis (``ENSG…~STRIP2`` → ``STRIP2``); plain symbols / IDs and
    # the stub's ``GENE1…`` labels pass through unchanged (so the stub golden is byte-identical).
    y_labels = display_symbols(y_labels)
    heat = {
        "type": "heatmap",
        "z": z,
        "x": x_labels,
        "y": y_labels,
        "colorscale": "RdBu",
        "reversescale": True,
        "zmid": 0,
        "colorbar": {"title": {"text": "z-score"}},
    }
    if not dendro:
        return {
            "data": [heat],
            "layout": {
                "title": {"text": title},
                "xaxis": {"title": {"text": x_title}},
                "yaxis": {"title": {"text": "gene"}, "automargin": True},
            },
        }

    # Combined clustermap: heatmap on x/y, dendrogram lines on x2/y2 (shared vertical span).
    # Match the conventional layout: tree on the left, row labels on the right (set via
    # yaxis.side below), and a small horizontal colour key tucked at the bottom-left so it
    # never competes with the labels.
    n = len(y_labels)
    heat["colorbar"] = {
        "title": {"text": "z-score", "side": "top", "font": {"size": 10}},
        "orientation": "h",
        "len": 0.3,
        "thickness": 10,
        "x": 0.0,
        "xanchor": "left",
        "y": -0.16,
        "yanchor": "top",
        "tickfont": {"size": 9},
    }
    xs, ys, max_d = [], [], 0.0
    for xc, yc in zip(dendro["dcoord"], dendro["icoord"]):
        xs += [round(float(v), 4) for v in xc] + [None]
        ys += [round(float(v), 4) for v in yc] + [None]
        max_d = max(max_d, max(xc))
    dendro_trace = {
        "type": "scatter",
        "mode": "lines",
        "x": xs,
        "y": ys,
        "xaxis": "x2",
        "yaxis": "y2",
        "line": {"color": "#94a3b8", "width": 1},
        "hoverinfo": "skip",
        "showlegend": False,
    }
    return {
        "data": [heat, dendro_trace],
        "layout": {
            "title": {"text": title},
            # heatmap occupies the right ~85%; row labels on the right so the tree owns the left
            "xaxis": {"title": {"text": x_title}, "domain": [0.16, 1.0]},
            "yaxis": {"title": {"text": "gene"}, "automargin": True, "side": "right"},
            # dendrogram gutter: leaves (distance 0) abut the heatmap on the right, root at left
            "xaxis2": {"domain": [0.0, 0.14], "range": [max_d * 1.05, 0],
                       "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": ""},
            "yaxis2": {"domain": [0.0, 1.0], "range": [0, 10 * n], "anchor": "x2",
                       "showticklabels": False, "showgrid": False, "zeroline": False, "ticks": ""},
        },
    }
