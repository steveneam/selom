"""Chart-extractor intake (X4 wired in) — "drop a figure → editable data".

Synthetic charts with KNOWN ground truth → assert the recovered Statistics table + editable Plotly
figure carry the right numbers, and that the POST /extract/chart endpoint returns the editable bundle.
"""

import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from extract import chart_intake
from extract.chart_to_data import Axis, Calibration
from main import app

client = TestClient(app)

W, H = 240, 200
CAL = Calibration(
    x=Axis(px0=20, val0=0.0, px1=220, val1=10.0),
    y=Axis(px0=180, val0=0.0, px1=20, val1=100.0),
)


def _y_px(v: float) -> float:
    return 180 - 1.6 * v


def _x_px(xd: float) -> float:
    return 20 + 20 * xd


def _bar_chart() -> Image.Image:
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for v, cx in zip([25.0, 50.0, 75.0, 90.0], [50, 100, 150, 200]):
        d.rectangle([cx - 12, _y_px(v), cx + 12, 180], fill=(0, 0, 0))
    return img


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --- the bridge: recovered series -> editable table + figure -------------------


def test_extract_chart_bar_emits_editable_table_and_figure():
    result = chart_intake.extract_chart(np.asarray(_bar_chart()), CAL, "bar", series_name="counts")
    series = result["series"]
    assert series.form == "bar" and len(series.values) == 4
    assert series.confidence == 0.7  # vision-grade, never text-exact

    table = result["table"]
    assert table["columns"] == ["category", "counts"]
    assert [r[0] for r in table["rows"]] == ["Bar 1", "Bar 2", "Bar 3", "Bar 4"]
    for (_, got), want in zip(table["rows"], [25.0, 50.0, 75.0, 90.0]):
        assert got == pytest.approx(want, abs=1.5)
    assert "vision-grade" in table["title"]

    figure = result["figure"]
    assert set(figure) == {"data", "layout"}  # pure Plotly spec (invariant)
    trace = figure["data"][0]
    assert trace["type"] == "bar" and trace["x"] == ["Bar 1", "Bar 2", "Bar 3", "Bar 4"]
    assert "confidence 0.7" in figure["layout"]["title"]["text"]


def test_extract_chart_custom_bar_labels():
    result = chart_intake.extract_chart(
        np.asarray(_bar_chart()), CAL, "bar", labels=["WT", "C3", "PT", "FS"]
    )
    assert [r[0] for r in result["table"]["rows"]] == ["WT", "C3", "PT", "FS"]
    assert result["figure"]["data"][0]["x"] == ["WT", "C3", "PT", "FS"]


def test_extract_chart_scatter_emits_xy_points():
    pts = [(2.0, 20.0), (3.0, 70.0), (5.0, 50.0), (8.0, 80.0)]
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for xd, yd in pts:
        cx, cy = _x_px(xd), _y_px(yd)
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(0, 0, 0))
    result = chart_intake.extract_chart(np.asarray(img), CAL, "scatter", min_size=5)
    assert result["table"]["columns"] == ["x", "y"]
    assert len(result["table"]["rows"]) == 4
    trace = result["figure"]["data"][0]
    assert trace["type"] == "scatter" and trace["mode"] == "markers"


def test_extract_chart_unknown_form_raises():
    with pytest.raises(ValueError, match="unsupported chart form"):
        chart_intake.extract_chart(np.asarray(_bar_chart()), CAL, "pie")


# --- param parsing -------------------------------------------------------------


def test_calibration_from_params_roundtrip_and_missing():
    q = {
        "x_px0": "20", "x_val0": "0", "x_px1": "220", "x_val1": "10",
        "y_px0": "180", "y_val0": "0", "y_px1": "20", "y_val1": "100", "y_log": "true",
    }
    calib = chart_intake.calibration_from_params(q)
    assert calib.x.val1 == 10.0 and calib.y.log is True
    with pytest.raises(ValueError, match="missing calibration param"):
        chart_intake.calibration_from_params({"x_px0": "20"})


def test_color_from_param_forms():
    assert chart_intake.color_from_param("#ff8800") == (255, 136, 0)
    assert chart_intake.color_from_param("12,34,56") == (12, 34, 56)
    assert chart_intake.color_from_param(None) is None
    with pytest.raises(ValueError):
        chart_intake.color_from_param("not-a-color")


# --- the endpoint --------------------------------------------------------------

_CAL_QS = (
    "x_px0=20&x_val0=0&x_px1=220&x_val1=10&y_px0=180&y_val0=0&y_px1=20&y_val1=100"
)


def test_endpoint_recovers_bars_to_editable_bundle():
    files = {"figure": ("panel.png", _png_bytes(_bar_chart()), "image/png")}
    r = client.post(f"/extract/chart?form=bar&{_CAL_QS}&labels=WT,C3,PT,FS", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["series"]["form"] == "bar" and body["confidence"] == 0.7
    assert body["table"]["rows"][0][0] == "WT"
    assert set(body["figure"]) == {"data", "layout"}
    assert body["figure"]["data"][0]["type"] == "bar"


def test_endpoint_bad_form_is_400():
    files = {"figure": ("panel.png", _png_bytes(_bar_chart()), "image/png")}
    r = client.post(f"/extract/chart?form=pie&{_CAL_QS}", files=files)
    assert r.status_code == 400


def test_endpoint_missing_calibration_is_400():
    files = {"figure": ("panel.png", _png_bytes(_bar_chart()), "image/png")}
    r = client.post("/extract/chart?form=bar&x_px0=20", files=files)
    assert r.status_code == 400
