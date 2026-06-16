"""Paper reader (papers.py) — durable PDF text/figure intake.

Text + metadata + embedded-image extraction need only pypdf (the 'pdf' extra); the
full-page rasterizer additionally needs pypdfium2 + Pillow, so that one test skips
when they're absent — keeping a text-only install green.

The fixture is a hand-built, spec-valid one-page PDF (correct xref byte offsets) so the
test needs no PDF *writer* dependency — only the readers under test.
"""

import importlib.util

import pytest

import papers


def _tiny_pdf(text: str = "Selom paper reader test") -> bytes:
    """A minimal valid single-page PDF that draws `text`, with a correct xref table."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        None,  # the content stream, filled below (needs `text`)
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = b"BT /F1 18 Tf 20 100 Td (" + text.encode("latin-1") + b") Tj ET"
    objs[3] = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"

    out = b"%PDF-1.4\n"
    offsets: list[int] = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(out)
    n = len(objs) + 1
    out += b"xref\n0 " + str(n).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += b"trailer\n<< /Size " + str(n).encode() + b" /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    return out


def _have(*mods: str) -> bool:
    return all(importlib.util.find_spec(m) is not None for m in mods)


@pytest.fixture
def pdf_path(tmp_path):
    p = tmp_path / "tiny.pdf"
    p.write_bytes(_tiny_pdf())
    return p


@pytest.mark.skipif(not _have("pypdf"), reason="pdf extra (pypdf) not installed")
def test_pdf_info(pdf_path):
    info = papers.pdf_info(pdf_path)
    assert info["pages"] == 1
    assert isinstance(info["metadata"], dict)


@pytest.mark.skipif(not _have("pypdfium2"), reason="text engine (pypdfium2) not installed")
def test_extract_pages_and_text(pdf_path):
    pages = papers.extract_pages(pdf_path)
    assert len(pages) == 1
    assert "Selom paper reader test" in pages[0]

    full = papers.extract_text(pdf_path)
    assert "===== PAGE 1 =====" in full  # page markers on by default
    assert "Selom paper reader test" in full

    assert papers.extract_text(pdf_path, page_markers=False).strip().startswith("Selom")


@pytest.mark.skipif(not _have("pypdfium2"), reason="text engine (pypdfium2) not installed")
def test_page_selection_bounds(pdf_path):
    assert papers.extract_pages(pdf_path, pages=[0]) == papers.extract_pages(pdf_path)
    with pytest.raises(IndexError):
        papers.extract_pages(pdf_path, pages=[5])


@pytest.mark.skipif(
    not _have("pypdfium2", "PIL"), reason="rasterizer (pypdfium2 + Pillow) not installed"
)
def test_render_page_returns_png(pdf_path):
    png = papers.render_page(pdf_path, 0, dpi=72)
    assert png[:8] == papers.PNG_MAGIC
    with pytest.raises(IndexError):
        papers.render_page(pdf_path, 5)


def test_missing_dependency_message():
    """A missing backend raises one actionable error naming the fix, not a bare ImportError."""
    with pytest.raises(RuntimeError) as exc:
        papers._require("definitely_not_a_real_module_xyz123")
    assert "uv sync --extra pdf" in str(exc.value)
