"""STRING protein-protein interaction network for a gene list (live STRING API).

Sends the input genes to the STRING database (string-db.org) and draws the returned
interaction network as an editable Plotly node-link: nodes = proteins, edges = STRING
interactions. When the input carries log2 fold changes the nodes are coloured by log2FC
(diverging — up/down hubs read off at a glance); otherwise by degree (sequential) to
surface the hub proteins.

Entrypoint dispatches the dependency-free stub vs. the real engine (``run_real.py``, the
live STRING REST API — STRING data is CC BY 4.0, attributed in the methods text). The stub
is a fixed phototransduction PPI so the golden test runs offline with zero heavy deps and
no network.
"""

import math

from skills._engine import use_real_engine

EDGE = "#9aa6b2"
# blue = down-regulated, white = no change, red = up-regulated (unambiguous diverging scale).
DIVERGING = [[0.0, "#2166ac"], [0.5, "#f7f7f7"], [1.0, "#b2182b"]]
SEQUENTIAL = "Viridis"


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas", "networkx"):
        from skills.string_network.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def network_spec(nodes: list[dict], edge_x: list, edge_y: list, title: str, color_mode: str) -> dict:
    """Editable Plotly node-link spec, shared by the stub and the real engine.

    ``nodes`` = [{x, y, label, hover, size, color}]; ``edge_x``/``edge_y`` are the flattened
    edge segments (x0,x1,None,…). ``color_mode`` is ``"fc"`` (diverging, symmetric about 0) or
    ``"degree"`` (sequential) and drives the colour scale + colourbar.
    """
    colors = [n["color"] for n in nodes]
    marker = {
        "size": [n["size"] for n in nodes],
        "sizemode": "diameter",
        "color": colors,
        "line": {"color": "#0b0f17", "width": 1},
    }
    if color_mode == "fc":
        m = max((abs(c) for c in colors), default=1.0) or 1.0
        marker.update(
            colorscale=DIVERGING, cmin=-m, cmid=0, cmax=m,
            showscale=True, colorbar={"title": {"text": "log2FC"}},
        )
    else:
        marker.update(
            colorscale=SEQUENTIAL, showscale=True,
            colorbar={"title": {"text": "degree"}},
        )
    return {
        "data": [
            {
                "type": "scatter", "mode": "lines", "name": "interactions",
                "x": edge_x, "y": edge_y,
                "line": {"color": EDGE, "width": 1}, "hoverinfo": "none", "showlegend": False,
            },
            {
                "type": "scatter", "mode": "markers+text", "name": "proteins",
                "x": [n["x"] for n in nodes], "y": [n["y"] for n in nodes],
                "text": [n["label"] for n in nodes],
                "textposition": "top center", "textfont": {"size": 9},
                "hovertext": [n["hover"] for n in nodes], "hoverinfo": "text",
                "marker": marker,
            },
        ],
        "layout": {
            "title": {"text": title},
            "xaxis": {"visible": False}, "yaxis": {"visible": False},
            "hovermode": "closest", "showlegend": False,
        },
    }


def _stub_figure() -> dict:
    """Deterministic phototransduction PPI (8 proteins, FC-coloured) for the golden test."""
    names = ["RHO", "GNAT1", "PDE6B", "PDE6A", "SAG", "GRK1", "RCVRN", "GNB1"]
    fc = {"RHO": -2.1, "GNAT1": -1.8, "PDE6B": -1.9, "PDE6A": -1.7,
          "SAG": -1.2, "GRK1": -0.9, "RCVRN": -1.0, "GNB1": -0.6}
    edges = [("RHO", "GNAT1"), ("GNAT1", "PDE6B"), ("PDE6B", "PDE6A"), ("RHO", "GRK1"),
             ("GRK1", "SAG"), ("RHO", "SAG"), ("GNAT1", "GNB1"), ("RHO", "RCVRN")]
    pos = {
        n: (round(math.cos(2 * math.pi * i / len(names)), 4), round(math.sin(2 * math.pi * i / len(names)), 4))
        for i, n in enumerate(names)
    }
    deg = {n: 0 for n in names}
    for a, b in edges:
        deg[a] += 1
        deg[b] += 1
    nodes = [
        {
            "x": pos[n][0], "y": pos[n][1], "label": n,
            "hover": f"{n}<br>{deg[n]} interactions · log2FC {fc[n]:+.2f}",
            "size": round(12 + 3 * deg[n] ** 0.5, 1), "color": fc[n],
        }
        for n in names
    ]
    edge_x: list = []
    edge_y: list = []
    for a, b in edges:
        edge_x += [pos[a][0], pos[b][0], None]
        edge_y += [pos[a][1], pos[b][1], None]
    return network_spec(nodes, edge_x, edge_y, "STRING interaction network (stub)", "fc")
