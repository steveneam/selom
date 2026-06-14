"""scorecard ``invert_metrics`` — lower-is-better metrics flip so higher always = better.

Real engine (pandas) on a synthetic conditions × metrics CSV: a metric where the best
condition has the LOWEST raw value must, after inversion, get the HIGHEST normalized
score. Guards the publish-confidence trap surfaced dogfooding the real Hani benchmark —
a high "off-target" must not render as good as high accuracy. Skipped without pandas.
"""

import os
import tempfile

import pytest

from skills.contract import run_skill

pytest.importorskip("pandas")


@pytest.fixture(autouse=True)
def _real(monkeypatch):
    monkeypatch.setenv("SELOM_SKILLS_ENGINE", "real")


def _csv(path: str) -> None:
    import pandas as pd

    pd.DataFrame(
        {
            "model": ["M1", "M2", "M3"],
            "accuracy": [0.9, 0.6, 0.3],   # higher is better -> M1 best
            "coverage": [0.8, 0.7, 0.5],
            "off_target": [0.5, 0.3, 0.1],  # lower is better -> M3 best
        }
    ).to_csv(path, index=False)


def _row(fig: dict, metric: str):
    tr = fig["data"][0]
    return tr["z"][tr["y"].index(metric)], tr["x"]


def test_invert_flips_lower_is_better():
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    try:
        _csv(path)
        base = run_skill("scorecard", path, {"layout": "heatmap"})
        inv = run_skill("scorecard", path, {"layout": "heatmap", "invert_metrics": "off_target"})
    finally:
        os.unlink(path)

    z_base, xs = _row(base, "off_target")
    z_inv, _ = _row(inv, "off_target")

    # Without inversion the WORST off-target (M1, highest raw) normalizes to the brightest 1.0
    # and the BEST (M3, lowest raw) to 0.0 — backwards.
    assert z_base[xs.index("M1")] == 1.0 and z_base[xs.index("M3")] == 0.0
    # With inversion the best condition (M3) is now brightest and the worst (M1) darkest.
    assert z_inv[xs.index("M3")] == 1.0 and z_inv[xs.index("M1")] == 0.0

    # A normal (higher-is-better) metric is untouched by inverting a different column.
    acc_base, _ = _row(base, "accuracy")
    acc_inv, _ = _row(inv, "accuracy")
    assert acc_base == acc_inv
