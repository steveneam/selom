"""Track-A vector-faithful lift (X3). Renderer-free unit tests on synthetic PDFs:

* a hand-built **vector** PDF (a filled rectangle in the content stream, correct xref) — the
  vector-crop path;
* a **raster** PDF (a PIL image saved as PDF → one Image XObject) — the bitmap-extract path.

The pixel-identity guarantee (render the cropped PDF → SSIM(registered)=1.0 vs the source region)
needs PDFium and is the owner-machine dogfood, exercised separately.
"""

import io

import numpy as np
import pytest
from PIL import Image

from extract.lift import (
    LiftedPanel,
    XObjectRef,
    extract_raster_panel,
    lift_panel_region,
    list_page_xobjects,
    page_is_vector,
)


def _make_vector_pdf(w: int = 200, h: int = 200) -> bytes:
    """A minimal valid PDF whose single page draws a filled rectangle (vector content)."""
    content = b"1 0 0 rg\n50 50 100 100 re\nf\n"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] "
         f"/Contents 4 0 R /Resources << >> >>").encode(),
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_pos = len(out)
    n = len(objs) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % n
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (n, xref_pos)
    return bytes(out)


def _make_raster_pdf(w: int = 60, h: int = 40) -> bytes:
    arr = np.random.default_rng(0).integers(0, 255, (h, w, 3)).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PDF")
    return buf.getvalue()


# --- vector crop --------------------------------------------------------------


def test_lift_panel_region_crops_to_bbox_vector():
    pdf = _make_vector_pdf(200, 200)
    data, panel = lift_panel_region(pdf, 0, (50, 50, 150, 150), panel_key="Fig1A")
    assert isinstance(panel, LiftedPanel)
    assert panel.kind == "vector" and panel.faithful is True and panel.scalable is True
    assert panel.mimetype == "application/pdf" and panel.bbox == (50, 50, 150, 150)
    # re-read the lifted PDF: a single page clipped to the requested box
    import pypdf
    reread = pypdf.PdfReader(io.BytesIO(data))
    assert len(reread.pages) == 1
    assert [float(v) for v in reread.pages[0].mediabox] == [50, 50, 150, 150]
    assert [float(v) for v in reread.pages[0].cropbox] == [50, 50, 150, 150]


def test_lift_panel_region_rejects_degenerate_bbox():
    pdf = _make_vector_pdf()
    with pytest.raises(ValueError):
        lift_panel_region(pdf, 0, (150, 50, 50, 150))   # x1 < x0


def test_lift_panel_region_page_out_of_range():
    pdf = _make_vector_pdf()
    with pytest.raises(IndexError):
        lift_panel_region(pdf, 5, (0, 0, 10, 10))


# --- vector/raster classification ---------------------------------------------


def test_page_is_vector_true_for_drawn_paths():
    assert page_is_vector(_make_vector_pdf(), 0) is True


def test_page_is_vector_false_for_image_only_page():
    assert page_is_vector(_make_raster_pdf(), 0) is False


def test_list_xobjects_finds_embedded_image():
    refs = list_page_xobjects(_make_raster_pdf(60, 40), 0)
    assert len(refs) == 1
    assert isinstance(refs[0], XObjectRef) and refs[0].subtype == "Image"
    assert refs[0].width == 60 and refs[0].height == 40


def test_list_xobjects_empty_for_plain_vector_page():
    assert list_page_xobjects(_make_vector_pdf(), 0) == []


# --- raster extract -----------------------------------------------------------


def test_extract_raster_panel_returns_image_bytes():
    data, panel = extract_raster_panel(_make_raster_pdf(), 0, panel_key="Fig2A")
    assert isinstance(data, (bytes, bytearray)) and len(data) > 0
    assert panel.kind == "raster" and panel.faithful is True and panel.scalable is False


def test_extract_raster_panel_no_image_raises():
    with pytest.raises(IndexError):
        extract_raster_panel(_make_vector_pdf(), 0)
