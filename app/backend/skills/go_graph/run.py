"""GO enrichment as a DAG node-link graph (P1 / DECISIONS #10).

Complements the `enrichment` dotplot: instead of a flat ranked list, it draws the
top enriched GO terms *in their is_a/part_of hierarchy* — so you see how the hit
terms relate (parent/child), editable as a Plotly node-link figure.

Entrypoint dispatches the dependency-free stub vs. the real engine (`run_real.py`,
which needs the built `go_dag.json` + scipy/pandas/networkx). The stub is a fixed
small DAG so the golden test runs with zero heavy deps.
"""

from skills._engine import use_real_engine

NODE = "#22d3ee"
EDGE = "#5b6b80"


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scipy", "pandas", "networkx"):
        from skills.go_graph.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def nodelink_spec(nodes: list[dict], edge_x: list, edge_y: list, title: str) -> dict:
    """Editable Plotly node-link spec, shared by the stub and the real engine.

    ``nodes`` = [{x, y, label, hover, size, color}]; ``edge_x``/``edge_y`` are the
    flattened edge segments (x0,x1,None,...). Colour = -log10 adjusted p.
    """
    return {
        "data": [
            {
                "type": "scatter", "mode": "lines", "name": "is_a / part_of",
                "x": edge_x, "y": edge_y,
                "line": {"color": EDGE, "width": 1}, "hoverinfo": "none", "showlegend": False,
            },
            {
                "type": "scatter", "mode": "markers+text", "name": "GO terms",
                "x": [n["x"] for n in nodes], "y": [n["y"] for n in nodes],
                "text": [n["label"] for n in nodes],
                "textposition": "top center", "textfont": {"size": 9},
                "hovertext": [n["hover"] for n in nodes], "hoverinfo": "text",
                "marker": {
                    "size": [n["size"] for n in nodes], "sizemode": "diameter",
                    "color": [n["color"] for n in nodes], "colorscale": "Viridis",
                    "showscale": True, "colorbar": {"title": {"text": "-log10 padj"}},
                    "line": {"color": "#0b0f17", "width": 1},
                },
            },
        ],
        "layout": {
            "title": {"text": title},
            "xaxis": {"visible": False}, "yaxis": {"visible": False},
            "hovermode": "closest", "showlegend": False,
        },
    }


def _stub_figure() -> dict:
    """Deterministic 5-term GO DAG (two parent/child chains) for the golden test."""
    nodes = [
        {"x": 0.0, "y": 1.0, "label": "sensory perception", "hover": "GO:BP: sensory perception<br>40 genes, -log10 padj 3.1", "size": 26, "color": 3.1},
        {"x": 0.0, "y": 0.0, "label": "visual perception", "hover": "GO:BP: visual perception<br>22 genes, -log10 padj 4.8", "size": 22, "color": 4.8},
        {"x": 1.0, "y": 1.0, "label": "cell projection", "hover": "GO:CC: cell projection<br>35 genes, -log10 padj 2.6", "size": 24, "color": 2.6},
        {"x": 1.0, "y": 0.0, "label": "cilium", "hover": "GO:CC: cilium<br>18 genes, -log10 padj 4.2", "size": 20, "color": 4.2},
        {"x": 2.0, "y": 0.5, "label": "photoreceptor activity", "hover": "GO:MF: photoreceptor activity<br>9 genes, -log10 padj 3.7", "size": 14, "color": 3.7},
    ]
    edge_x = [0.0, 0.0, None, 1.0, 1.0, None]
    edge_y = [0.0, 1.0, None, 0.0, 1.0, None]
    return nodelink_spec(nodes, edge_x, edge_y, "GO enrichment graph (stub)")
