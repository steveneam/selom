"""Proteomics differential abundance — intensity matrix to volcano.

Real path (``run_real.py``): log2 + median-normalize an intensity matrix, filter
sparse proteins, fill residual dropouts (``missing``: mean | mindet | minprob), run a
per-protein Welch or empirical-Bayes moderated t-test between two sample groups, and
Benjamini-Hochberg adjust. Proteomics-native stats on log-intensities — distinct from
the count-based ``deg`` skill. The stub is a deterministic volcano. Both reuse the
``volcano`` skill's ``_assemble``, so the figure is identical in shape and picks up the
same publication theme.
"""

import math

from skills._engine import use_real_engine
from skills.volcano.run import _assemble


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas", "scipy"):
        from skills.proteomics_de.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    fc_t = float(params.get("fc_threshold", 1.0))
    fdr_t = float(params.get("fdr_threshold", 0.05))
    top_n = int(params.get("top_n", 10))
    y_cut = -math.log10(fdr_t) if fdr_t > 0 else 0.0

    # deterministic proteins: (log2FC, -log10 adj-p, name)
    pts = [
        (2.9, 6.8, "B2m"), (2.1, 4.4, "Flna"), (1.7, 5.0, "Tgm1"), (1.4, 4.2, "Spcs2"),
        (2.4, 3.6, "Mvp"), (1.2, 2.3, "Nceh1"), (1.9, 2.0, "Gbp2"),
        (-2.7, 5.6, "Hk2"), (-2.2, 5.3, "Taok3"), (-1.6, 4.1, "Nt5e"), (-1.9, 3.7, "Fmn2"),
        (-1.3, 2.6, "Aqp1"), (-2.0, 2.1, "Plpp3"), (-1.4, 1.8, "Gnaz"),
    ]
    ns_pts = [(round(0.8 * math.sin(i * 0.9), 3), round(0.6 * (1 + math.cos(i * 0.7)), 3))
              for i in range(24)]

    up = ([x for x, _, _ in pts if x > 0], [y for x, y, _ in pts if x > 0])
    down = ([x for x, _, _ in pts if x < 0], [y for x, y, _ in pts if x < 0])
    ns = ([x for x, _ in ns_pts], [y for _, y in ns_pts])
    labels = [(x, y, n) for x, y, n in pts if y >= 3.5][:top_n]
    return _assemble(up, down, ns, labels, fc_t, y_cut, "Proteomics differential abundance (stub)")
