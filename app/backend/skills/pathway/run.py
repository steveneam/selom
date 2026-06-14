"""Reactome pathway map as a fold-change-coloured node-link (P1 / DECISIONS #10).

The sibling of `go_graph`: where that draws enriched GO terms in their is_a/part_of
DAG coloured by significance, this draws the top *Reactome* pathways for a gene list
in their **event hierarchy** (parent pathway -> child pathway), coloured by each
pathway's **mean log2 fold change** — so up- vs down-regulated programmes read off the
map at a glance. Reactome diagrams aren't natively editable Plotly, so we render the
enrichment as an editable node-link rather than embedding their SVG.

Entrypoint dispatches the dependency-free stub vs. the real engine (`run_real.py`,
which calls the live Reactome Analysis Service — open data, CC0; no gseapy/MSigDB per
DECISIONS #9). The stub is a fixed small hierarchy so the golden test runs offline with
zero heavy deps and no network.
"""

from skills._engine import use_real_engine

EDGE = "#5b6b80"
# Explicit diverging scale so the orientation is unambiguous regardless of Plotly's
# named-scale conventions: blue = down-regulated, white = no change, red = up-regulated.
DIVERGING = [[0.0, "#2166ac"], [0.5, "#f7f7f7"], [1.0, "#b2182b"]]


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas", "networkx"):
        from skills.pathway.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def pathway_spec(nodes: list[dict], edge_x: list, edge_y: list, title: str) -> dict:
    """Editable Plotly node-link spec, shared by the stub and the real engine.

    ``nodes`` = [{x, y, label, hover, size, color}]; ``edge_x``/``edge_y`` are the
    flattened edge segments (x0,x1,None,...). Colour = mean log2 fold change on a
    diverging scale symmetric about zero.
    """
    colors = [n["color"] for n in nodes]
    m = max((abs(c) for c in colors), default=1.0) or 1.0
    return {
        "data": [
            {
                "type": "scatter", "mode": "lines", "name": "parent / child",
                "x": edge_x, "y": edge_y,
                "line": {"color": EDGE, "width": 1}, "hoverinfo": "none", "showlegend": False,
            },
            {
                "type": "scatter", "mode": "markers+text", "name": "Reactome pathways",
                "x": [n["x"] for n in nodes], "y": [n["y"] for n in nodes],
                "text": [n["label"] for n in nodes],
                "textposition": "top center", "textfont": {"size": 9},
                "hovertext": [n["hover"] for n in nodes], "hoverinfo": "text",
                "marker": {
                    "size": [n["size"] for n in nodes], "sizemode": "diameter",
                    "color": colors, "colorscale": DIVERGING,
                    "cmin": -m, "cmid": 0, "cmax": m,
                    "showscale": True, "colorbar": {"title": {"text": "mean log2FC"}},
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
    """Deterministic 5-pathway Reactome hierarchy (two chains, up + down) for the golden
    test: a mitotic/cell-cycle programme up-regulated, a phototransduction programme down."""
    nodes = [
        {"x": 0.0, "y": 1.0, "label": "Cell Cycle, Mitotic",
         "hover": "Cell Cycle, Mitotic<br>R-HSA-69278 · 6/587 genes<br>FDR 2.6e-04 · mean log2FC +1.57",
         "size": 16.9, "color": 1.57},
        {"x": 0.0, "y": 0.0, "label": "Mitotic G1 phase and G1/S t…",
         "hover": "Mitotic G1 phase and G1/S transition<br>R-HSA-453279 · 5/164 genes<br>FDR 1.2e-05 · mean log2FC +1.58",
         "size": 16.5, "color": 1.58},
        {"x": 1.5, "y": 1.0, "label": "Signal Transduction",
         "hover": "Signal Transduction<br>R-HSA-162582 · 8/2740 genes<br>FDR 9.0e-03 · mean log2FC -1.50",
         "size": 17.7, "color": -1.5},
        {"x": 1.5, "y": 0.0, "label": "Visual phototransduction",
         "hover": "Visual phototransduction<br>R-HSA-2187338 · 4/159 genes<br>FDR 3.0e-04 · mean log2FC -1.98",
         "size": 16.0, "color": -1.98},
        {"x": 2.5, "y": 0.5, "label": "The phototransduction cascade",
         "hover": "The phototransduction cascade<br>R-HSA-2514856 · 4/59 genes<br>FDR 1.2e-05 · mean log2FC -1.98",
         "size": 16.0, "color": -1.98},
    ]
    edge_x = [0.0, 0.0, None, 1.5, 1.5, None, 1.5, 2.5, None]
    edge_y = [0.0, 1.0, None, 0.0, 1.0, None, 0.0, 0.5, None]
    return pathway_spec(nodes, edge_x, edge_y, "Reactome pathway enrichment (stub)")
