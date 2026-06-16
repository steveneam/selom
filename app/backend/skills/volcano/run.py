"""Volcano plot from a differential-expression table.

x = log2 fold-change, y = -log10(adjusted p). Points are split into up / down /
not-significant by the fold-change and FDR thresholds, with dashed threshold lines
and the top-N most-significant genes labelled. Pure plotting (pandas + plotly), so
``run_real`` shares this module's helpers.
"""

import math

from skills._engine import use_real_engine

UP = "#22d3ee"
DOWN = "#f43f5e"
NS = "#5b6b80"
HL = "#f59e0b"  # highlighted gene-set panel (amber, drawn on top)


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.volcano.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    from skills._table import de_table

    fc_t = float(params.get("fc_threshold", 1.0))
    fdr_t = float(params.get("fdr_threshold", 0.05))
    y_cut = -math.log10(fdr_t) if fdr_t > 0 else 0.0

    up, down, ns = ([], []), ([], []), ([], [])
    genes, lfcs, padjs = [], [], []
    for i in range(80):
        lfc = round(3.0 * math.sin(i * 0.7), 3)
        nlp = round(abs(lfc) * 1.15 + 0.5 * (1 + math.cos(i * 0.9)), 3)
        bucket = up if (lfc >= fc_t and nlp >= y_cut) else down if (lfc <= -fc_t and nlp >= y_cut) else ns
        bucket[0].append(lfc)
        bucket[1].append(nlp)
        genes.append(f"GENE{i + 1}")
        lfcs.append(lfc)
        padjs.append(10 ** (-nlp))  # invert the synthetic -log10 padj back to padj

    spec = _assemble(up, down, ns, [], fc_t, y_cut, "Volcano (stub)")
    spec["table"] = de_table(genes, lfcs, padjs, fc_t=fc_t, fdr_t=fdr_t)
    return spec


def _assemble(up, down, ns, labels, fc_t, y_cut, title, highlight=None) -> dict:
    """Build the volcano spec from up/down/ns (x,y) pairs + optional label/highlight points.

    ``highlight`` is an optional list of ``(x, y, gene)`` for a gene-set panel applied
    from the "Gene Sets" surface — drawn on top in amber, with each member labelled.
    Left ``None`` it adds nothing, so the stub/golden output is unchanged.
    """
    data = [
        {"type": "scattergl", "mode": "markers", "name": "n.s.", "x": ns[0], "y": ns[1],
         "marker": {"color": NS, "size": 5, "opacity": 0.6}},
        {"type": "scattergl", "mode": "markers", "name": "up", "x": up[0], "y": up[1],
         "marker": {"color": UP, "size": 6}},
        {"type": "scattergl", "mode": "markers", "name": "down", "x": down[0], "y": down[1],
         "marker": {"color": DOWN, "size": 6}},
    ]
    if labels:
        data.append({
            "type": "scatter", "mode": "text", "name": "labels", "showlegend": False,
            "x": [p[0] for p in labels], "y": [p[1] for p in labels],
            "text": [p[2] for p in labels], "textposition": "top center",
            "textfont": {"size": 10},
        })
    if highlight:
        data.append({
            "type": "scatter", "mode": "markers+text", "name": "highlighted",
            "x": [p[0] for p in highlight], "y": [p[1] for p in highlight],
            "text": [p[2] for p in highlight], "textposition": "top center",
            "textfont": {"size": 10, "color": HL},
            "marker": {"color": HL, "size": 9, "line": {"color": "#ffffff", "width": 1.2}},
        })
    shapes = [
        {"type": "line", "x0": fc_t, "x1": fc_t, "yref": "paper", "y0": 0, "y1": 1,
         "line": {"color": NS, "width": 1, "dash": "dash"}},
        {"type": "line", "x0": -fc_t, "x1": -fc_t, "yref": "paper", "y0": 0, "y1": 1,
         "line": {"color": NS, "width": 1, "dash": "dash"}},
        {"type": "line", "xref": "paper", "x0": 0, "x1": 1, "y0": y_cut, "y1": y_cut,
         "line": {"color": NS, "width": 1, "dash": "dash"}},
    ]
    return {
        "data": data,
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": "log2 fold-change"}},
            "yaxis": {"title": {"text": "-log10 adjusted p"}},
            "shapes": shapes,
        },
    }
