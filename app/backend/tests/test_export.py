"""Journal figure export (export.py + the /figures/export API).

The preset math is a pure function and always runs. The real render needs Kaleido
+ a Chrome browser, so it is skipped when either is absent — keeping CI (core-only)
green while the dev box (Chrome present) verifies a true PNG end-to-end.
"""

import pytest
from fastapi.testclient import TestClient

import export
from main import app

client = TestClient(app)

TINY_FIG = {
    "data": [{"type": "scatter", "x": [1, 2, 3], "y": [3, 1, 2], "mode": "lines"}],
    "layout": {"title": {"text": "t"}},
}


def _kaleido_ready() -> bool:
    import importlib.util

    if importlib.util.find_spec("kaleido") is None:
        return False
    try:
        export.render(TINY_FIG, "png", preset="nature-single")
        return True
    except export.ExportUnavailable:
        return False  # kaleido installed but no Chrome (e.g. CI) — skip the real render


# --- preset math (pure, always runs) ---------------------------------------


def test_nature_single_bakes_dpi_into_scale():
    # 89 mm @ 300 dpi: width in CSS px = 89/25.4*96; DPI rides on scale = 300/96.
    w, h, scale = export.resolve_dimensions(TINY_FIG, fmt="png", preset="nature-single")
    assert w == round(89 / 25.4 * 96)            # 336
    assert scale == pytest.approx(300 / 96)      # 3.125
    # final raster px ≈ the journal target (89 mm @ 300 dpi ≈ 1051 px)
    assert round(w * scale) == pytest.approx(round(89 / 25.4 * 300), abs=2)


def test_vector_ignores_dpi_scale():
    # SVG/PDF are resolution-independent — DPI must not inflate scale.
    _, _, scale = export.resolve_dimensions(TINY_FIG, fmt="svg", preset="nature-single")
    assert scale == 1.0


def test_height_preserves_figure_aspect():
    fig = {"data": [], "layout": {"width": 600, "height": 300}}  # 2:1
    w, h, _ = export.resolve_dimensions(fig, fmt="png", width=800)
    assert (w, h) == (800, 400)


def test_fit_to_figure_raster_is_retina():
    # No preset, no width override → export at the figure's own size, 2x for PNG.
    fig = {"data": [], "layout": {"width": 700, "height": 500}}
    w, h, scale = export.resolve_dimensions(fig, fmt="png")
    assert (w, h, scale) == (700, 500, 2.0)
    _, _, vscale = export.resolve_dimensions(fig, fmt="svg")  # vectors never inflate
    assert vscale == 1.0


def test_explicit_overrides_win_over_preset():
    w, h, scale = export.resolve_dimensions(
        TINY_FIG, fmt="png", preset="nature-single", width=500, height=250
    )
    assert (w, h, scale) == (500, 250, 1.0)


def test_unknown_preset_and_format_raise():
    with pytest.raises(ValueError):
        export.resolve_dimensions(TINY_FIG, fmt="png", preset="does-not-exist")
    with pytest.raises(ValueError):
        export.render(TINY_FIG, "gif")


# --- API ---------------------------------------------------------------------


def test_presets_endpoint_lists_journals():
    r = client.get("/figures/export/presets")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()["presets"]}
    assert {"nature-single", "cell-double", "science-single"} <= ids


def test_export_rejects_bad_format_and_figure():
    assert client.post("/figures/export", json={"figure": TINY_FIG, "format": "gif"}).status_code == 400
    assert client.post("/figures/export", json={"figure": {"nope": 1}}).status_code == 400


def test_export_unavailable_maps_to_503(monkeypatch):
    def boom(*a, **k):
        raise export.ExportUnavailable("no chrome")

    monkeypatch.setattr(export, "render", boom)
    r = client.post("/figures/export", json={"figure": TINY_FIG, "format": "png"})
    assert r.status_code == 503
    assert "chrome" in r.json()["detail"].lower()


@pytest.mark.skipif(not _kaleido_ready(), reason="kaleido + Chrome not available")
@pytest.mark.parametrize(
    "fmt,magic", [("png", b"\x89PNG"), ("svg", b"<svg"), ("pdf", b"%PDF")]
)
def test_export_renders_real_image(fmt, magic):
    r = client.post(
        "/figures/export",
        json={"figure": TINY_FIG, "format": fmt, "preset": "nature-single"},
    )
    media = {"png": "image/png", "svg": "image/svg+xml", "pdf": "application/pdf"}
    assert r.status_code == 200
    assert r.headers["content-type"] == media[fmt]
    assert r.content[:4].startswith(magic[:4])
    assert f".{fmt}" in r.headers["content-disposition"]
