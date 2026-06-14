"""GSEA running enrichment-score plot.

The canonical three-panel GSEA figure: the running enrichment-score curve (top),
the leading-edge hit ticks (middle), and the ranked metric (bottom, red/blue by
sign). Real path (``run_real.py``) computes a weighted Kolmogorov-Smirnov ES over a
ranked DE table against a gene set, with a permutation NES + empirical p — all
in-house numpy (no gseapy), consistent with Selom's in-house ORA (DECISIONS #9).
The stub is a deterministic curve. Distinct from the ORA ``enrichment`` skill.
"""

import math

from skills._engine import use_real_engine

ES_LINE = "#2e8b57"   # running ES (sea green)
POS = "#c0392b"       # ranked metric, positive (red)
NEG = "#2f6db0"       # ranked metric, negative (blue)
TICK = "#33404d"      # leading-edge hit ticks


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas", "scipy"):
        from skills.gsea.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    set_name = str(params.get("set_name", "Gene set")) or "Gene set"
    n = 300
    x = list(range(1, n + 1))
    # running ES: rises to a peak near the top of the list, then drifts negative
    peak = 58
    es = 0.62
    y_es = []
    for i in x:
        if i <= peak:
            y_es.append(round(es * math.sin((i / peak) * (math.pi / 2)), 4))
        else:
            y_es.append(round(es * math.cos((i - peak) / (n - peak) * (math.pi / 2)) - 0.12 * ((i - peak) / (n - peak)), 4))
    hit_x = [3, 6, 9, 11, 14, 18, 21, 24, 27, 31, 35, 38, 42, 47, 52, 55, 58, 64, 70, 79, 96, 120, 155, 200, 260]
    y_m = [round(2.6 * (1 - 2 * (i - 1) / (n - 1)), 4) for i in x]  # +2.6 -> -2.6 linear
    return _assemble(x, y_es, peak, es, hit_x, x, y_m, nes=2.04, pval=0.001, set_name=set_name)


def _assemble(x_es, y_es, peak_x, es, hit_x, x_m, y_m, nes, pval, set_name):
    """Build the three-panel GSEA spec (ES curve / hit rug / ranked metric)."""
    y_pos = [v if v > 0 else 0 for v in y_m]
    y_neg = [v if v < 0 else 0 for v in y_m]
    data = [
        {"type": "scatter", "mode": "lines", "name": "enrichment score", "x": x_es, "y": y_es,
         "line": {"color": ES_LINE, "width": 2.5}, "fill": "tozeroy",
         "fillcolor": "rgba(46,139,87,0.12)", "yaxis": "y"},
        {"type": "scatter", "mode": "markers", "name": "peak ES", "x": [peak_x], "y": [es],
         "marker": {"color": ES_LINE, "size": 9, "line": {"color": "#ffffff", "width": 1.4}},
         "yaxis": "y", "showlegend": False, "hoverinfo": "y"},
        {"type": "scatter", "mode": "markers", "name": "hits", "x": hit_x, "y": [0.5] * len(hit_x),
         "marker": {"symbol": "line-ns-open", "color": TICK, "size": 9, "line": {"width": 1}},
         "yaxis": "y3", "hoverinfo": "x", "showlegend": False},
        {"type": "scatter", "mode": "lines", "name": "ranked metric +", "x": x_m, "y": y_pos,
         "line": {"width": 0}, "fill": "tozeroy", "fillcolor": "rgba(192,57,45,0.55)",
         "yaxis": "y2", "showlegend": False, "hoverinfo": "skip"},
        {"type": "scatter", "mode": "lines", "name": "ranked metric -", "x": x_m, "y": y_neg,
         "line": {"width": 0}, "fill": "tozeroy", "fillcolor": "rgba(47,109,176,0.55)",
         "yaxis": "y2", "showlegend": False, "hoverinfo": "skip"},
    ]
    title = f"GSEA — {set_name}   ES={es:.2f}  NES={nes:.2f}  p={_fmt_p(pval)}"
    layout = {
        "title": {"text": title},
        "xaxis": {"title": {"text": "gene rank"}, "anchor": "y2"},
        "yaxis": {"title": {"text": "enrichment score"}, "domain": [0.42, 1.0], "zeroline": True},
        "yaxis3": {"domain": [0.32, 0.39], "showticklabels": False, "showgrid": False,
                   "zeroline": False, "range": [0, 1]},
        "yaxis2": {"title": {"text": "ranked metric"}, "domain": [0.0, 0.26], "zeroline": True},
        "shapes": [{"type": "line", "xref": "x", "x0": peak_x, "x1": peak_x, "yref": "paper",
                    "y0": 0.42, "y1": 1.0, "line": {"color": ES_LINE, "width": 1, "dash": "dot"},
                    "opacity": 0.6}],
    }
    return {"data": data, "layout": layout}


def _fmt_p(p):
    return f"{p:.3g}"
