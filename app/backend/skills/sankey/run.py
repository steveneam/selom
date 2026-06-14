"""Sankey / alluvial flow diagram — quantities flowing between stages or categories.

Reads a long edge table (``source``, ``target``, ``value``) and draws a Plotly Sankey:
nodes are the unique source/target labels, links carry the summed value between each
pair. Good for cell-state transitions, QC-stage attrition, or sample→cell-type
composition flows. The stub is a fixed QC-and-composition example of the same wire shape.
"""

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.sankey.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    labels = ["Raw cells", "Pass QC", "Doublets", "Rods", "Cones", "Bipolar", "Other"]
    source = [0, 0, 1, 1, 1, 1]
    target = [1, 2, 3, 4, 5, 6]
    value = [9200, 800, 5200, 1800, 1400, 800]
    return sankey_spec(labels, source, target, value, "Cell QC & composition flow (stub)")


def sankey_spec(labels, source, target, value, title) -> dict:
    """Shared Sankey spec — used by both the stub and the real engine. ``source`` and
    ``target`` are integer node indices into ``labels``; ``value`` is the flow per link."""
    return {
        "data": [
            {
                "type": "sankey",
                "orientation": "h",
                "node": {
                    "label": [str(x) for x in labels],
                    "pad": 16,
                    "thickness": 16,
                    "line": {"width": 0},
                },
                "link": {
                    "source": [int(s) for s in source],
                    "target": [int(t) for t in target],
                    "value": [round(float(v), 4) for v in value],
                },
            }
        ],
        "layout": {"title": {"text": title}},
    }
