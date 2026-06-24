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

# Per-point hover + the gene-labelling substrate (generalization-spec §H): every plotted point
# carries its gene SYMBOL (+ adj p) as ``customdata`` so the editor can label a clicked point and
# the Statistics-table Label toggle can find a gene's coordinates. Render-inert beyond the hover.
HOVER = "<b>%{customdata[0]}</b><br>log2FC %{x:.3g} · adj p %{customdata[1]:.2g}<extra></extra>"


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

    up, down, ns = ([], [], []), ([], [], []), ([], [], [])
    genes, lfcs, padjs = [], [], []
    for i in range(80):
        lfc = round(3.0 * math.sin(i * 0.7), 3)
        nlp = round(abs(lfc) * 1.15 + 0.5 * (1 + math.cos(i * 0.9)), 3)
        padj = 10 ** (-nlp)  # invert the synthetic -log10 padj back to padj
        gene = f"GENE{i + 1}"
        bucket = up if (lfc >= fc_t and nlp >= y_cut) else down if (lfc <= -fc_t and nlp >= y_cut) else ns
        bucket[0].append(lfc)
        bucket[1].append(nlp)
        bucket[2].append([gene, padj])
        genes.append(gene)
        lfcs.append(lfc)
        padjs.append(padj)

    spec = _assemble(up, down, ns, [], fc_t, y_cut, "Volcano (stub)")
    spec["table"] = de_table(genes, lfcs, padjs, fc_t=fc_t, fdr_t=fdr_t)
    return spec


def _assemble(up, down, ns, labels, fc_t, y_cut, title, highlight=None) -> dict:
    """Build the volcano spec from up/down/ns ``(x, y, customdata)`` triples + optional
    label/highlight points.

    Each bucket is ``([x…], [y…], [[gene, padj]…])`` — the per-point ``customdata`` carries the
    gene SYMBOL (+ adj p) so the editor's gene-labelling (generalization-spec §H) can label a
    clicked point and the Statistics-table toggle can locate a gene's coordinates. ``highlight`` is
    an optional list of ``(x, y, gene)`` for a gene-set panel applied from the "Gene Sets" surface —
    drawn on top in amber, with each member labelled. Left ``None`` it adds nothing.
    """
    # Per-point customdata ([gene, padj]) is optional: the volcano passes ``(x, y, customdata)``
    # triples, but ``proteomics_de`` reuses this assembler with bare ``(x, y)`` pairs — so a bucket
    # without a 3rd element simply omits the labelling keys (its figure/golden stays unchanged).
    ns_cd = ns[2] if len(ns) > 2 else None
    up_cd = up[2] if len(up) > 2 else None
    down_cd = down[2] if len(down) > 2 else None
    data = [
        {"type": "scattergl", "mode": "markers", "name": "n.s.", "x": ns[0], "y": ns[1],
         "customdata": ns_cd, "hovertemplate": HOVER,
         "marker": {"color": NS, "size": 5, "opacity": 0.6}},
        {"type": "scattergl", "mode": "markers", "name": "up", "x": up[0], "y": up[1],
         "customdata": up_cd, "hovertemplate": HOVER,
         "marker": {"color": UP, "size": 6}},
        {"type": "scattergl", "mode": "markers", "name": "down", "x": down[0], "y": down[1],
         "customdata": down_cd, "hovertemplate": HOVER,
         "marker": {"color": DOWN, "size": 6}},
    ]
    for tr in data:
        if tr.get("customdata") is None:
            tr.pop("customdata", None)
            tr.pop("hovertemplate", None)
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
