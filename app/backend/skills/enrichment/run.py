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
    return _stub_figure()


def _stub_figure() -> dict:
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


def dotplot_spec(pathways, nlp, overlap, title) -> dict:
    """Shared enrichment dotplot — used by both the stub and the real engine.

    ``pathways`` are ordered most- to least-significant; Plotly draws the y-axis
    bottom-up, so reverse to put the top hit at the top.
    """
    return {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "name": "pathways",
                "x": list(reversed(nlp)),
                "y": list(reversed(pathways)),
                "text": [f"{o} genes" for o in reversed(overlap)],
                "marker": {
                    "size": list(reversed(overlap)),
                    "sizemode": "diameter",
                    "color": list(reversed(nlp)),
                    "colorscale": "Viridis",
                    "showscale": True,
                    "colorbar": {"title": {"text": "-log10 padj"}},
                },
            }
        ],
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": "-log10 adjusted p"}},
            "yaxis": {"title": {"text": "pathway"}, "automargin": True},
        },
    }
