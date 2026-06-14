"""Per-cell QC violin panel (paper Fig S1A).

Three side-by-side violin panels — total counts, genes per cell, and mitochondrial
percentage — each split by sample, the canonical scRNA quality check before any
downstream analysis. Real engine computes the metrics with scanpy; the stub here is a
deterministic two-sample panel of the same wire shape.
"""

import math

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy"):
        from skills.normalization_qc.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


def _stub_figure() -> dict:
    def synth(base, spread, seed, n=40):
        return [round(base + spread * math.sin(i * 0.7 + seed), 2) for i in range(n)]

    panels = [
        {"label": "Total counts", "values_by_group": {"S1": synth(4000, 800, 0), "S2": synth(3500, 700, 1)}},
        {"label": "Genes per cell", "values_by_group": {"S1": synth(1500, 300, 2), "S2": synth(1300, 250, 3)}},
        {"label": "Mito %", "values_by_group": {"S1": synth(6, 2, 4), "S2": synth(8, 2.5, 5)}},
    ]
    return qc_panel_spec(panels, "Per-cell QC (stub)")


def qc_panel_spec(panels, title) -> dict:
    """Shared QC-panel spec — one violin sub-panel per metric, split by group on a
    shared category x. ``panels`` is an ordered list of
    ``{"label": str, "values_by_group": {group: [values]}}``."""
    n = max(1, len(panels))
    gap = 0.07
    width = (1 - gap * (n - 1)) / n

    data = []
    layout = {"title": {"text": title}, "showlegend": False, "violingap": 0.25}
    for i, panel in enumerate(panels):
        suffix = "" if i == 0 else str(i + 1)
        xref, yref = f"x{suffix}", f"y{suffix}"
        x0 = i * (width + gap)

        xs, ys = [], []
        for group, values in panel["values_by_group"].items():
            xs += [str(group)] * len(values)
            ys += [round(float(v), 4) for v in values]
        data.append(
            {
                "type": "violin",
                "x": xs,
                "y": ys,
                "xaxis": xref,
                "yaxis": yref,
                "name": panel["label"],
                "points": False,
                "box": {"visible": True},
                "meanline": {"visible": True},
                "scalemode": "width",
            }
        )
        layout[f"xaxis{suffix}"] = {
            "domain": [round(x0, 4), round(x0 + width, 4)], "anchor": yref,
            "type": "category", "showgrid": False,
        }
        layout[f"yaxis{suffix}"] = {
            "domain": [0, 1], "anchor": xref, "showgrid": False,
            "title": {"text": panel["label"]}, "zeroline": False,
        }
    return {"data": data, "layout": layout}
