"""Durable paper reader — PDF → text / figures intake.

The first, reusable step of the **"extract skills from papers"** pipeline (the v2
Skill-Foundry moat — `docs/command-center/design.md` §6.5): turn a deposited paper PDF
into machine-readable **text** (abstract, methods, figure legends, data-availability /
GEO accessions) plus rasterized **pages / embedded figures** we can view and replicate.
This replaces the throwaway per-session PDF hacks with one tested module the intake
flow, the figure-replication dogfood, and a future ``POST /papers/extract`` endpoint
all share.

LICENSE POSTURE (shipped path = permissive only — memory ``eamos-pdf-extraction-tooling``):
  - text + full-page rasterize : **pypdfium2**   (BSD-3-Clause / Apache-2.0; wraps Google
                                                   PDFium, BSD-3-Clause)
  - metadata + embedded images : **pypdf**       (BSD-3-Clause)
  - PNG encode                 : **Pillow**       (HPND / MIT-BSD-like)
Deliberately AVOIDS PyMuPDF/``fitz`` (AGPL). Install via the optional extra::

    uv sync --extra pdf

TWO engines, each used where it is strongest. PDFium owns **text** because pypdf's
extractor returns *empty* on many real publisher PDFs (e.g. Elsevier's PStill/PDFlib
pipeline — the RPGRIP1 dogfood paper extracted 0 chars via pypdf, 99.6k via PDFium).
pypdf owns **metadata** because it reads custom ``/Info`` keys PDFium drops (the DOI,
the journal ref). Each function lazy-imports only the backend it needs and a missing
dependency raises one clear, actionable error.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable, Sequence

# PNG magic — callers (and the test) assert renders are real PNGs.
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _require(module: str):
    """Import an optional PDF backend or fail with a fix-it message (not an opaque
    ImportError). Mirrors the export-skill's degrade-cleanly posture."""
    try:
        return __import__(module)
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError(
            f"The paper reader needs '{module}', which is in the optional 'pdf' extra. "
            f"Install it with:  uv sync --extra pdf"
        ) from exc


def _normalize_pages(pages: Iterable[int] | None, n: int) -> list[int]:
    """Resolve a 0-based page selection (None → all) and bounds-check it."""
    if pages is None:
        return list(range(n))
    out = [int(p) for p in pages]
    bad = [p for p in out if p < 0 or p >= n]
    if bad:
        raise IndexError(f"page index out of range {bad} (document has {n} pages)")
    return out


def pdf_info(path: str | Path) -> dict:
    """Page count + document metadata (title/author/…), keys de-slashed.

    >>> pdf_info("paper.pdf")["pages"]
    38
    """
    pypdf = _require("pypdf")
    reader = pypdf.PdfReader(str(path))
    meta = dict(reader.metadata or {})
    clean = {(k[1:] if k.startswith("/") else k): str(v) for k, v in meta.items()}
    return {"pages": len(reader.pages), "metadata": clean}


def extract_pages(path: str | Path, pages: Sequence[int] | None = None) -> list[str]:
    """Per-page extracted text (0-based ``pages`` selection; None → every page).

    One string per requested page, in request order — the unit the section/legend
    parsers and the figure-replication dogfood walk over. PDFium-backed (robust on real
    publisher PDFs where pypdf returns empty).
    """
    pdfium = _require("pypdfium2")
    pdf = pdfium.PdfDocument(str(path))
    try:
        idxs = _normalize_pages(pages, len(pdf))
        return [pdf[i].get_textpage().get_text_range() for i in idxs]
    finally:
        pdf.close()


def extract_text(
    path: str | Path,
    pages: Sequence[int] | None = None,
    page_markers: bool = True,
) -> str:
    """All requested page text as one string (PDFium-backed).

    With ``page_markers`` (default) each page is prefixed ``===== PAGE n =====`` so
    grep/section-finders can recover page boundaries (n is the real 1-based page no.).
    """
    pdfium = _require("pypdfium2")
    pdf = pdfium.PdfDocument(str(path))
    try:
        idxs = _normalize_pages(pages, len(pdf))
        chunks: list[str] = []
        for i in idxs:
            body = pdf[i].get_textpage().get_text_range()
            chunks.append(f"===== PAGE {i + 1} =====\n{body}" if page_markers else body)
        return "\n".join(chunks)
    finally:
        pdf.close()


def render_page(path: str | Path, index: int, dpi: int = 150) -> bytes:
    """Rasterize one page (0-based ``index``) to PNG bytes at ``dpi``.

    PDFium renders; Pillow encodes. Used to *see* figures (e.g. replicate Fig 5/6)
    without shelling out to an AGPL renderer.
    """
    pdfium = _require("pypdfium2")
    _require("PIL")  # Pillow — surfaces the same actionable error if absent
    pdf = pdfium.PdfDocument(str(path))
    try:
        n = len(pdf)
        if index < 0 or index >= n:
            raise IndexError(f"page index {index} out of range (document has {n} pages)")
        bitmap = pdf[index].render(scale=dpi / 72.0)
        buf = io.BytesIO()
        bitmap.to_pil().save(buf, format="PNG")
        return buf.getvalue()
    finally:
        pdf.close()


def render_pages(path: str | Path, indices: Sequence[int], dpi: int = 150) -> list[bytes]:
    """Rasterize several pages to PNG (opens the document once)."""
    pdfium = _require("pypdfium2")
    _require("PIL")
    pdf = pdfium.PdfDocument(str(path))
    try:
        n = len(pdf)
        out: list[bytes] = []
        for index in indices:
            if index < 0 or index >= n:
                raise IndexError(f"page index {index} out of range (document has {n} pages)")
            buf = io.BytesIO()
            pdf[index].render(scale=dpi / 72.0).to_pil().save(buf, format="PNG")
            out.append(buf.getvalue())
        return out
    finally:
        pdf.close()


def extract_page_images(path: str | Path, index: int) -> list[bytes]:
    """Raw bytes of every raster image embedded on one page (0-based ``index``).

    pypdf-only (no rasterizer needed) — pulls the actual figure bitmaps the authors
    embedded, distinct from :func:`render_page` which rasterizes the whole page.
    """
    pypdf = _require("pypdf")
    reader = pypdf.PdfReader(str(path))
    n = len(reader.pages)
    if index < 0 or index >= n:
        raise IndexError(f"page index {index} out of range (document has {n} pages)")
    return [img.data for img in reader.pages[index].images]
