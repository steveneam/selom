"""Differential expression — top-gene ranking, scRNA or bulk.

Two real paths (``run_real.py``):
  * scRNA  — scanpy ``rank_genes_groups`` (Wilcoxon by default) per cluster.
  * bulk   — pyDESeq2 on a counts table with a 2-level design inferred from the
             sample-column prefixes.
The figure is a horizontal bar of the top-N genes by signed score, coloured by
direction (up = cyan, down = rose). The stub is a deterministic version of that.
"""

from skills._engine import use_real_engine

UP = "#22d3ee"
DOWN = "#f43f5e"


def run(data_path: str, params: dict) -> dict:
    # scRNA needs scanpy; bulk needs pydeseq2. Either dep present -> real is usable.
    if use_real_engine("scanpy") or use_real_engine("pydeseq2"):
        from skills.deg.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic top-gene bar: 12 genes, signed scores, up/down coloured."""
    # (gene, signed score) ordered ascending so the strongest sits at the top of an
    # horizontal bar; a few negatives exercise the down-regulated colour.
    rows = [
        ("CST3", -3.1), ("FTL", -2.4), ("LYZ", -1.6), ("S100A9", 2.0),
        ("NKG7", 2.4), ("GZMB", 2.9), ("CD3D", 3.3), ("IL7R", 3.8),
        ("MS4A1", 4.2), ("CD79A", 4.7), ("GNLY", 5.1), ("PPBP", 5.8),
    ]
    genes = [g for g, _ in rows]
    scores = [s for _, s in rows]
    colors = [UP if s >= 0 else DOWN for s in scores]
    return {
        "data": [
            {
                "type": "bar",
                "orientation": "h",
                "x": scores,
                "y": genes,
                "marker": {"color": colors},
                "name": "score",
            }
        ],
        "layout": {
            "title": {"text": "Top differential genes (stub)"},
            "xaxis": {"title": {"text": "score (signed)"}},
            "yaxis": {"title": {"text": "gene"}},
            "bargap": 0.3,
        },
    }
