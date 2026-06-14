"""Marker-gene dotplot — the publication workhorse for cluster characterization.

Ranks marker genes per cluster (scanpy ``rank_genes_groups``, Wilcoxon by default) and
draws the top few per group as a *dotplot*: a bubble grid where **colour = mean log1p
expression** in the group and **dot size = fraction of cells in the group expressing the
gene**. This dual encoding is what ``deg`` (a single group's top-gene bar) and ``violin``
(one gene's distribution) don't show. The real engine lives in ``run_real.py``; the stub
here is a deterministic, dependency-free version of the same wire shape.
"""

from skills._engine import use_real_engine

# Sequential colour scale for mean expression (matches the dotplot convention; Reds).
COLORSCALE = "Reds"


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy"):
        from skills.markers.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic dotplot: 3 groups x 4 top markers each (block-diagonal signal).

    Each group's own markers are strongly + widely expressed (high colour, big dot);
    off-group cells barely express them (low colour, small dot) — the canonical
    marker-dotplot look, with zero heavy deps.
    """
    groups = ["0", "1", "2"]
    block = [
        ["CST3", "LYZ", "FTL", "S100A9"],
        ["CD3D", "IL7R", "NKG7", "GZMB"],
        ["MS4A1", "CD79A", "GNLY", "PPBP"],
    ]
    genes = [g for row in block for g in row]

    xs: list[str] = []
    ys: list[str] = []
    means: list[float] = []
    sizes: list[float] = []
    fracs: list[float] = []
    for gi, group in enumerate(groups):
        for j, gene in enumerate(genes):
            own = (j // 4) == gi
            mean = round(2.6 + 0.1 * (j % 4) if own else 0.3 + 0.04 * (j % 4), 4)
            frac = round(0.82 + 0.03 * (j % 4) if own else 0.12 + 0.02 * (j % 4), 4)
            xs.append(gene)
            ys.append(group)
            means.append(mean)
            sizes.append(round(4.0 + frac * 22.0, 4))
            fracs.append(frac)

    return _dotplot_spec(
        xs, ys, means, sizes, fracs, genes, groups,
        title="Marker genes — top 4 per cluster (stub)",
    )


def _dotplot_spec(xs, ys, means, sizes, fracs, gene_order, group_order, title) -> dict:
    """Assemble the editable dotplot Plotly spec (shared by stub + real engine)."""
    return {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "x": xs,
                "y": ys,
                "marker": {
                    "color": means,
                    "colorscale": COLORSCALE,
                    "showscale": True,
                    "colorbar": {"title": {"text": "mean expr (log1p)"}},
                    "size": sizes,
                    "line": {"color": "#334155", "width": 0.5},
                },
                "customdata": fracs,
                "hovertemplate": (
                    "%{x} · group %{y}<br>mean expr %{marker.color:.2f}"
                    "<br>%{customdata:.0%} of cells<extra></extra>"
                ),
                "name": "markers",
            }
        ],
        "layout": {
            "title": {
                "text": title,
                "subtitle": {"text": "colour = mean expression · dot size = % of cells expressing"},
            },
            "xaxis": {
                "title": {"text": "gene"},
                "type": "category",
                "categoryorder": "array",
                "categoryarray": gene_order,
                "tickangle": -45,
            },
            "yaxis": {
                "title": {"text": "cluster"},
                "type": "category",
                "categoryorder": "array",
                "categoryarray": group_order,
            },
            "plot_bgcolor": "white",
        },
    }
