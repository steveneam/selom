"""Differential abundance — which clusters change in proportion between conditions.

After clustering, a natural question is "does cell type X expand or shrink in the mutant?"
OSCA tests this on the **cells-per-(cluster x sample)** count table with edgeR/DESeq2 +
TMM normalization — treating each sample (not each cell) as the replicate, and using TMM
to blunt the compositional artefact that one cluster growing makes the others look smaller.
Real engine in ``run_real.py`` (reuses the shipped DESeq2 + TMM machinery); the stub here
is a deterministic set of expanding / shrinking clusters of the same wire shape.
"""

from skills._engine import use_real_engine

UP = "#22d3ee"    # expanding in the treatment
DOWN = "#f43f5e"  # shrinking in the treatment


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy", "pandas"):
        from skills.diff_abundance.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic differential abundance: some clusters expand, some shrink (mutant vs WT)."""
    clusters = ["Rods", "Cones", "Bipolar", "Müller glia", "Microglia", "Amacrine"]
    lfc = [-1.9, -0.4, 0.2, 1.6, 2.3, -0.1]
    return _da_spec(
        clusters, lfc,
        "Differential abundance — mutant vs WT (stub)",
        "pyDESeq2 (Wald, TMM norm) · mutant (n=3) vs WT (n=3) · 6 clusters · proportions are compositional",
    )


def _da_spec(clusters, lfc, title, subtitle) -> dict:
    """Editable horizontal-bar spec (shared by stub + real engine): one bar per cluster,
    log2 fold-change in abundance, cyan = expanding / rose = shrinking. Sorted so the
    strongest change sits at the top."""
    order = sorted(range(len(lfc)), key=lambda i: lfc[i])
    clusters = [str(clusters[i]) for i in order]
    lfc = [round(float(lfc[i]), 4) for i in order]
    return {
        "data": [
            {
                "type": "bar",
                "orientation": "h",
                "x": lfc,
                "y": clusters,
                "marker": {"color": [UP if v >= 0 else DOWN for v in lfc]},
                "name": "log2FC abundance",
                "hovertemplate": "%{y}<br>log2FC %{x:.2f}<extra></extra>",
            }
        ],
        "layout": {
            "title": {"text": f"{title}<br><sub>{subtitle}</sub>"},
            "xaxis": {"title": {"text": "log2 fold-change in abundance"}, "zeroline": True},
            "yaxis": {"title": {"text": "cluster"}},
            "bargap": 0.3,
            "plot_bgcolor": "white",
        },
    }
