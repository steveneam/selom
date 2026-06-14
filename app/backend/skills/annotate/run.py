"""Cell-type annotation (Mode A — marker-set scoring).

Scores curated marker sets per cell against a chosen panel (scanpy ``score_genes``),
aggregates to clusters, assigns each cluster its top-scoring cell type, and recolours the
embedding by the assigned type — the canonical annotation figure. Deterministic and
dependency-light (no reference model, no new dep); custom panels and reference-based
automation (CellTypist) can layer on later. Real engine in ``run_real.py``; the stub here
is a deterministic UMAP-by-cell-type of the same wire shape.
"""

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy"):
        from skills.annotate.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic embedding coloured by assigned cell type — 4 retinal types,
    ~10 cells each, one trace per type (Plotly auto-colours; legend toggles types)."""
    import math

    centers = [(0.0, 0.0), (5.0, 1.0), (2.5, 4.5), (-3.0, 3.0)]
    names = ["Rod photoreceptors", "Müller glia", "Retinal ganglion cells", "Bipolar cells"]
    per = 10
    data = []
    for ci, (cx, cy) in enumerate(centers):
        xs, ys = [], []
        for j in range(per):
            angle = ci * 2.39996 + j * 0.7
            radius = 0.6 + 0.4 * ((j % 5) / 4.0)
            xs.append(round(cx + radius * math.cos(angle), 4))
            ys.append(round(cy + radius * math.sin(angle), 4))
        data.append({"type": "scatter", "mode": "markers", "name": names[ci], "x": xs, "y": ys})

    return _umap_by_type_spec(data, "Cell-type annotation (stub · retinal panel)", "4 types · 4 clusters")


def _umap_by_type_spec(traces, title, subtitle) -> dict:
    """Editable UMAP-coloured-by-cell-type spec (shared by stub + real engine)."""
    return {
        "data": traces,
        "layout": {
            "title": {"text": title, "subtitle": {"text": subtitle}},
            "xaxis": {"title": {"text": "UMAP 1"}, "zeroline": False},
            "yaxis": {"title": {"text": "UMAP 2"}, "zeroline": False},
            "legend": {"title": {"text": "cell type"}},
        },
    }
