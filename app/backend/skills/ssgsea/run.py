"""Single-sample GSEA (ssGSEA) — per-sample pathway-enrichment heatmap.

Scores every sample independently against a gene-set library (default GO), so each
sample gets one enrichment score per pathway — a sample x pathway matrix drawn as a
heatmap (the GSVA / ssGSEA presentation). Distinct from the ``gsea`` skill, which runs a
single pre-ranked enrichment over one DE contrast: ssGSEA needs no differential test,
only an expression matrix, and answers "how active is each pathway in each sample?".
Real path (``run_real.py``) = gseapy.ssgsea (BSD-3) over Selom's license-clean GO
library; the stub is a deterministic score matrix in the same shape.
"""

import math

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas", "gseapy"):
        from skills.ssgsea.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    n_sets, n_samples = 8, 6
    pathways = [f"pathway {i + 1}" for i in range(n_sets)]
    samples = [f"S{j + 1}" for j in range(n_samples)]
    z = [[round(math.sin(i * 0.7 + j * 0.9), 4) for j in range(n_samples)] for i in range(n_sets)]
    title = "ssGSEA — single-sample pathway enrichment (stub)"
    return ssgsea_spec(z, samples, pathways, title, "enrichment (z)")


def ssgsea_spec(z, samples, pathways, title, score_label, table=None) -> dict:
    """Shared sample x pathway heatmap — used by both the stub and the real engine.

    Pathways in rows, samples in columns, on a diverging RdBu scale centred at zero.
    ``table`` (a Statistics StatsTable) is attached when given; it defaults off so the
    dependency-free stub renders byte-identically to its committed golden.
    """
    heat = {
        "type": "heatmap",
        "z": z,
        "x": samples,
        "y": pathways,
        "colorscale": "RdBu",
        "reversescale": True,
        "zmid": 0,
        "colorbar": {"title": {"text": score_label}},
    }
    spec = {
        "data": [heat],
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": "sample"}, "automargin": True},
            "yaxis": {"title": {"text": "gene set"}, "automargin": True},
        },
    }
    if table is not None:
        spec["table"] = table
    return spec
