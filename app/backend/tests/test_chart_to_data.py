"""Chart → data recovery (X4). Synthetic charts with KNOWN ground truth — draw a bar/line/scatter
panel with PIL at a fixed pixel↔data calibration, recover, and assert the recovered numbers match.
This is the only honest validation: recovery is exact-by-construction on clean marks, vision-grade
(confidence < 1) on real scans.
"""

import numpy as np
import pytest
from PIL import Image, ImageDraw

from extract.chart_to_data import (
    Axis,
    Calibration,
    mask_by_color,
    mask_by_darkness,
    recover_bars,
    recover_line,
    recover_scatter,
)

# Fixed calibration shared by the synthetic fixtures.
W, H = 240, 200
CAL = Calibration(
    x=Axis(px0=20, val0=0.0, px1=220, val1=10.0),     # col 20→0 .. col 220→10
    y=Axis(px0=180, val0=0.0, px1=20, val1=100.0),    # row 180→0 .. row 20→100 (up = larger)
)


def _x_px(xd: float) -> float:
    return 20 + 20 * xd


def _y_px(v: float) -> float:
    return 180 - 1.6 * v


def _blank() -> Image.Image:
    return Image.new("RGB", (W, H), (255, 255, 255))


# --- calibration --------------------------------------------------------------


def test_axis_linear_and_log():
    lin = Axis(px0=0, val0=0, px1=100, val1=10)
    assert lin.to_data(50) == pytest.approx(5.0)
    log = Axis(px0=0, val0=1, px1=100, val1=1000, log=True)
    assert log.to_data(50) == pytest.approx(10 ** 1.5, rel=1e-6)   # halfway in log space


def test_axis_degenerate_reference_raises():
    with pytest.raises(ValueError):
        Axis(px0=10, val0=0, px1=10, val1=5).to_data(10)


# --- masking ------------------------------------------------------------------


def test_mask_by_darkness_and_color():
    arr = np.full((4, 4, 3), 255, dtype=np.uint8)
    arr[1, 1] = (0, 0, 0)
    arr[2, 2] = (200, 10, 10)
    assert mask_by_darkness(arr).sum() == 2          # black + red are both dark-ish
    redmask = mask_by_color(arr, (200, 10, 10), tol=30)
    assert redmask.sum() == 1 and redmask[2, 2]


# --- bars ---------------------------------------------------------------------


def test_recover_bars_matches_known_heights():
    values = [25.0, 50.0, 75.0, 90.0]
    centers = [50, 100, 150, 200]
    img = _blank()
    d = ImageDraw.Draw(img)
    for v, cx in zip(values, centers):
        d.rectangle([cx - 12, _y_px(v), cx + 12, 180], fill=(0, 0, 0))
    out = recover_bars(np.asarray(img), CAL)
    assert out.form == "bar" and len(out.values) == 4
    for got, want in zip(out.values, values):
        assert got == pytest.approx(want, abs=1.5)


# --- line ---------------------------------------------------------------------


def test_recover_line_traces_known_function():
    # data-space line y = 5*x over x in [0,10]
    img = _blank()
    d = ImageDraw.Draw(img)
    d.line([(_x_px(0), _y_px(0)), (_x_px(10), _y_px(50))], fill=(0, 0, 0), width=1)
    out = recover_line(np.asarray(img), CAL, step=4)
    assert out.form == "line" and len(out.points) > 10
    for x, y in out.points:
        assert y == pytest.approx(5 * x, abs=3.0)


# --- scatter ------------------------------------------------------------------


def test_recover_scatter_finds_known_points():
    pts = [(2.0, 20.0), (3.0, 70.0), (5.0, 50.0), (8.0, 80.0)]
    img = _blank()
    d = ImageDraw.Draw(img)
    for xd, yd in pts:
        cx, cy = _x_px(xd), _y_px(yd)
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(0, 0, 0))
    out = recover_scatter(np.asarray(img), CAL, min_size=5)
    assert out.form == "scatter" and len(out.points) == 4
    # every known point has a recovered point within a small data-space tolerance
    for xd, yd in pts:
        nearest = min(out.points, key=lambda p: (p[0] - xd) ** 2 + (p[1] - yd) ** 2)
        assert nearest[0] == pytest.approx(xd, abs=0.5)
        assert nearest[1] == pytest.approx(yd, abs=1.5)


def test_recover_scatter_empty_image():
    out = recover_scatter(np.asarray(_blank()), CAL)
    assert out.form == "scatter" and out.points == []
