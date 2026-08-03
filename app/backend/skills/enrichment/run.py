"""Pathway / gene-set enrichment as a dotplot.

Over-representation analysis (hypergeometric test + Benjamini-Hochberg FDR) of an
input gene list against **GO / Reactome** gene sets — implemented in-house against
a bundled, openly-licensed gene-set sample, NOT gseapy/MSigDB (DECISIONS.md #9,
which avoids the AGPL/MSigDB licence gate in RISKS.md #6).

The figure is a dotplot: x = -log10(adjusted p), y = pathway, marker size = overlap
count, colour = -log10(adjusted p). The stub is a deterministic version.
"""

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scipy", "pandas"):
        from skills.enrichment.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict | None = None) -> dict:
    if str((params or {}).get("direction") or "combined").lower() == "split":
        return _stub_split()
    pathways = [
        "Reactome: Interferon signaling",
        "GO: NK cell mediated cytotoxicity",
        "Reactome: Neutrophil degranulation",
        "GO: T cell receptor signaling",
        "Reactome: Antigen processing",
        "GO: MHC class II protein complex",
        "GO: B cell receptor signaling",
        "Reactome: Platelet activation",
        "GO: Inflammatory response",
        "Reactome: Cell Cycle",
    ]
    nlp = [round(4.8 - i * 0.42, 2) for i in range(len(pathways))]
    overlap = [max(3, 22 - i * 2) for i in range(len(pathways))]
    return dotplot_spec(pathways, nlp, overlap, "Pathway enrichment (stub)")


def _stub_split() -> dict:
    up = [
        {"pathway": "Reactome: Interferon signaling", "nlp": 4.6, "overlap": 18},
        {"pathway": "GO: Inflammatory response", "nlp": 3.9, "overlap": 14},
        {"pathway": "Reactome: Neutrophil degranulation", "nlp": 3.1, "overlap": 11},
    ]
    down = [
        {"pathway": "Reactome: Cell Cycle", "nlp": 4.2, "overlap": 16},
        {"pathway": "GO: DNA replication", "nlp": 3.4, "overlap": 12},
        {"pathway": "Reactome: Mitotic spindle assembly", "nlp": 2.8, "overlap": 9},
    ]
    return dotplot_split_spec(up, down, "Pathway enrichment — up/down split (stub)")


# Dot DIAMETERS in px. Matches the `markers` dotplot's 4..26 band, the in-repo precedent for
# encoding a count in dot size.
_DOT_MIN_PX, _DOT_MAX_PX = 6.0, 26.0


def _dot_sizes(counts, top=None):
    """Map overlap counts to marker diameters in **pixels**.

    The raw count must never reach ``marker.size``: Plotly reads that as a diameter in px, so an
    ORA returning 1-3 overlapping genes drew dots 1-3 PIXELS across and the size channel was
    invisible (parity-audit D1). matplotlib's ``s`` is an area, which is why the same array looks
    fine there and hid the bug in review. Exact counts stay in the hover text and the table.

    ``top`` pins the count that maps to the largest dot. Pass it whenever the dots are split
    across several traces — scaling each trace to its own maximum would draw the same count at two
    different sizes and make the encoding a lie.
    """
    vals = [float(c or 0) for c in counts]
    top = max(vals, default=0.0) if top is None else float(top)
    if top <= 0:
        return [_DOT_MIN_PX] * len(vals)
    span = _DOT_MAX_PX - _DOT_MIN_PX
    return [round(_DOT_MIN_PX + (min(v, top) / top) * span, 2) for v in vals]


def _size_legend(counts, color="#7c8794"):
    """Legend proxies that make the dot-size channel readable.

    A size encoding with no key is undecodable — the reader sees big and small dots and cannot
    recover the counts. Plotly builds no size legend of its own, so emit up to three point-free
    traces (``x=[None]``) at representative counts; they render in the legend and nowhere else.
    """
    distinct = sorted({int(c) for c in counts if c})
    if not distinct:
        return []
    picks = sorted({distinct[0], distinct[len(distinct) // 2], distinct[-1]})
    sizes = _dot_sizes(picks)
    return [
        {
            "type": "scatter", "mode": "markers", "x": [None], "y": [None],
            "name": f"{c} gene{'s' if c != 1 else ''}", "hoverinfo": "skip",
            "legendgroup": "dotsize",
            "marker": {"size": s, "color": color},
        }
        for c, s in zip(picks, sizes)
    ]


def dotplot_spec(pathways, nlp, overlap, title) -> dict:
    """Shared enrichment dotplot — used by both the stub and the real engine.

    ``pathways`` are ordered most- to least-significant; Plotly draws the y-axis
    bottom-up, so reverse to put the top hit at the top.
    """
    from skills._table import table

    spec = {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "name": "pathways",
                "x": list(reversed(nlp)),
                "y": list(reversed(pathways)),
                "text": [f"{o} genes" for o in reversed(overlap)],
                "showlegend": False,  # the legend carries the size key, not this trace
                "marker": {
                    "size": _dot_sizes(reversed(overlap)),
                    "sizemode": "diameter",
                    "color": list(reversed(nlp)),
                    "colorscale": "Viridis",
                    "showscale": True,
                    "colorbar": {"title": {"text": "-log10 padj"}},
                },
            },
            *_size_legend(overlap),
        ],
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": "-log10 adjusted p"}},
            "yaxis": {"title": {"text": "pathway"}, "automargin": True},
            # Size key inside the axes at the bottom-right. The colourbar owns the right margin,
            # so a default legend lands on top of it; and the bottom-right of THIS figure type is
            # structurally empty — terms are sorted by significance down the y axis, so the bottom
            # row always carries the smallest x. `itemsizing: "trace"` keeps the key dots at the
            # sizes they encode, which is the whole point of the key.
            "legend": {
                "title": {"text": "overlap", "font": {"size": 10}},
                "x": 0.97, "xanchor": "right", "y": 0.03, "yanchor": "bottom",
                "itemsizing": "trace", "font": {"size": 10},
            },
        },
    }
    # Statistics node (Pillar 1) — the enriched terms, most significant first.
    spec["table"] = table(
        ["pathway", "-log10 padj", "overlap genes"],
        [[p, n, o] for p, n, o in zip(pathways, nlp, overlap)],
        "Enrichment results",
    )
    return spec


def dotplot_split_spec(up_rows, down_rows, title) -> dict:
    """Diverging enrichment dotplot — ORA run separately on the up- and down-regulated
    significant genes (Suppl Fig 6 / 5C). Up terms sit on the right (positive x), down on
    the left (negative x); x is the direction-signed -log10(adjusted p), marker size = the
    overlap count, colour encodes direction. ``up_rows``/``down_rows`` are lists of
    ``{pathway, nlp, overlap}``. The shared y-axis lists every term once, most-significant
    (either direction) at the top."""
    best: dict[str, float] = {}
    for r in up_rows + down_rows:
        best[r["pathway"]] = max(best.get(r["pathway"], 0.0), r["nlp"])
    # plotly draws y categories bottom-up, so ascending significance puts the top hit on top
    ordered = sorted(best, key=lambda p: best[p])
    # ONE dot scale across both directions, so an overlap of n is the same dot up or down
    size_top = max((r["overlap"] for r in up_rows + down_rows), default=0)

    def _trace(rows, sign, name, color):
        return {
            "type": "scatter",
            "mode": "markers",
            "name": name,
            "x": [round(sign * r["nlp"], 3) for r in rows],
            "y": [r["pathway"] for r in rows],
            "text": [f"{r['overlap']} genes" for r in rows],
            "marker": {"size": _dot_sizes([r["overlap"] for r in rows], top=size_top),
                       "sizemode": "diameter", "color": color},
        }

    from skills._table import table

    spec = {
        "data": [
            _trace(down_rows, -1, "Down-regulated", "#1f77b4"),
            _trace(up_rows, +1, "Up-regulated", "#d62728"),
        ],
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": "← down    direction-signed -log10 adjusted p    up →"}},
            "yaxis": {
                "title": {"text": "pathway"},
                "automargin": True,
                "categoryorder": "array",
                "categoryarray": ordered,
            },
        },
    }
    rows = sorted(
        [[r["pathway"], "up", r["nlp"], r["overlap"]] for r in up_rows]
        + [[r["pathway"], "down", r["nlp"], r["overlap"]] for r in down_rows],
        key=lambda x: x[2],
        reverse=True,
    )
    spec["table"] = table(["pathway", "direction", "-log10 padj", "overlap genes"], rows, "Enrichment (up / down)")
    return spec
