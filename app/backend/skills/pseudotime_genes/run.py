"""Genes along pseudotime — which genes change over an inferred trajectory.

After ``trajectory`` orders cells along diffusion pseudotime, this is the test that makes
the trajectory *useful* (OSCA ``testPseudotime``): each gene's expression is correlated
with pseudotime (Spearman), Benjamini-Hochberg corrected, and the top trending genes are
drawn as smooth expression curves binned along pseudotime. Real engine in ``run_real.py``
(scanpy DPT + scipy ranks); the stub here is a deterministic set of up / down / transient
trends of the same wire shape.
"""

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy", "scipy"):
        from skills.pseudotime_genes.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic trends over 20 pseudotime bins: a riser, a faller, a transient peak."""
    n = 20
    x = [round(i / (n - 1), 4) for i in range(n)]
    rise = [round(0.3 + 2.4 * t, 4) for t in x]                       # monotone up
    fall = [round(2.7 - 2.3 * t, 4) for t in x]                       # monotone down
    peak = [round(0.4 + 2.2 * (1.0 - (2 * t - 1) ** 2), 4) for t in x]  # transient peak
    series = [
        {"name": "GENE_UP", "y": rise, "rho": 0.98},
        {"name": "GENE_DOWN", "y": fall, "rho": -0.97},
        {"name": "GENE_TRANSIENT", "y": peak, "rho": 0.05},
    ]
    return _pseudotime_spec(
        x, series,
        "Genes along pseudotime (stub)",
        "auto root (DC1 extreme) · Spearman gene-vs-pseudotime · 3 genes",
    )


def _pseudotime_spec(x, series, title, subtitle) -> dict:
    """Editable line-plot spec (shared by stub + real engine): one smoothed expression
    curve per gene across binned pseudotime."""
    data = [
        {
            "type": "scatter",
            "mode": "lines",
            "x": list(x),
            "y": [round(float(v), 4) for v in s["y"]],
            "name": str(s["name"]),
            "line": {"shape": "spline", "smoothing": 0.6},
            "hovertemplate": f"{s['name']}<br>pseudotime %{{x:.2f}}<br>mean expr %{{y:.2f}}<extra></extra>",
        }
        for s in series
    ]
    return {
        "data": data,
        "layout": {
            "title": {"text": f"{title}<br><sub>{subtitle}</sub>"},
            "xaxis": {"title": {"text": "pseudotime"}},
            "yaxis": {"title": {"text": "mean log1p expression"}},
            "plot_bgcolor": "white",
            "legend": {"title": {"text": "gene"}},
        },
    }
