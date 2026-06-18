"""Principal Variance Component Analysis (PVCA) — batch-effect apportionment.

Quantifies how much of the total expression variance each known sample factor
(batch, cell type, dataset, ...) explains — the standard "is there a batch effect,
and did integration remove it?" readout (Kim et al. 2023 Fig 2B). Real engine in
``run_real.py`` decomposes the variance over the leading principal components; the
stub here is a deterministic apportionment of the same wire shape (a factor bar).
"""

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("numpy", "pandas"):
        from skills.pvca.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    """Deterministic PVCA: cell type dominates, batch is small (a well-integrated atlas)."""
    components = [
        ("cell type", 0.62), ("dataset", 0.16), ("batch", 0.07), ("residual", 0.15),
    ]
    return pvca_spec(components, "Variance apportionment (stub)")


def pvca_spec(components: list, title: str) -> dict:
    """Editable Plotly bar of the weighted variance fraction per factor (shared by stub +
    real engine). ``components`` = [(factor, fraction)], drawn descending with ``residual``
    pinned last so the explained factors read left-to-right by magnitude."""
    ordered = sorted(
        components, key=lambda c: (c[0] == "residual", -float(c[1]))
    )
    labels = [str(name) for name, _ in ordered]
    fracs = [round(float(frac), 4) for _, frac in ordered]
    return {
        "data": [{
            "type": "bar", "x": labels, "y": fracs,
            "text": [f"{f * 100:.1f}%" for f in fracs], "textposition": "outside",
            "marker": {"color": ["#b0413e" if n == "batch" else "#3a6ea5" if n != "residual"
                                 else "#9aa5b1" for n in labels]},
            "name": "variance fraction",
        }],
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": "factor"}, "type": "category"},
            "yaxis": {"title": {"text": "weighted variance fraction"}, "rangemode": "tozero"},
            "showlegend": False,
            "bargap": 0.4,
            "plot_bgcolor": "white",
        },
    }
