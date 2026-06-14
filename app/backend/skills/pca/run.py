"""PCA of samples from a feature × sample table (bulk RNA / proteomics).

Computes principal components over samples (rows = features, columns = samples; e.g. a
log2 protein-abundance or count matrix) and plots PC1 vs PC2, coloured by group inferred
from the sample names (trailing replicate index stripped, like ``deg``). The workhorse QC
figure for "do my conditions separate?". Real engine in ``run_real.py``; the stub here is
a deterministic two-group separation of the same wire shape.
"""

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("sklearn", "pandas"):
        from skills.pca.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic PCA: two groups (DR, PD) of 5 samples, cleanly separated on PC1."""
    groups = {
        "DR": [(-2.3, 0.5), (-2.0, -0.4), (-2.6, 0.1), (-1.8, 0.6), (-2.1, -0.6)],
        "PD": [(2.1, 0.4), (2.5, -0.3), (1.9, 0.7), (2.4, -0.5), (2.2, 0.2)],
    }
    traces = []
    for gi, (name, pts) in enumerate(groups.items()):
        traces.append(
            {
                "type": "scatter",
                "mode": "markers+text",
                "name": name,
                "x": [round(x, 4) for x, _ in pts],
                "y": [round(y, 4) for _, y in pts],
                "text": [f"{name}{i+1}" for i in range(len(pts))],
                "textposition": "top center",
                "marker": {"size": 11},
            }
        )
    return _pca_spec(traces, 61.2, 12.7, "PCA (stub)")


def _pca_spec(traces, var_pc1, var_pc2, title) -> dict:
    """Editable PCA scatter spec (shared by stub + real engine)."""
    return {
        "data": traces,
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": f"PC1 ({var_pc1:.1f}%)"}, "zeroline": True},
            "yaxis": {"title": {"text": f"PC2 ({var_pc2:.1f}%)"}, "zeroline": True},
            "legend": {"title": {"text": "group"}},
            "plot_bgcolor": "white",
        },
    }
