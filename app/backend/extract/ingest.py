"""Ingest stage (E1) — a thin typed wrapper over ``papers.py`` (PDFium/pypdf, BSD).

The first, reused stage of the extraction pipeline: PDF → page text (exact chars) +
metadata, with lazy page rasters for the deferred vision stage. No new dependency — it
composes the already-tested ``papers`` module (the ``pdf`` extra). License posture E5:
permissive only (never poppler/PyMuPDF on the shipped path).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

import papers


class IngestedPaper(BaseModel):
    """A paper read into memory: full text (page-markered) + per-page text + metadata."""

    path: str
    n_pages: int
    metadata: dict = Field(default_factory=dict)
    text: str = ""               # all pages, with ``===== PAGE n =====`` markers
    pages: list[str] = Field(default_factory=list)  # per-page text, in page order


def ingest_pdf(path: str | Path) -> IngestedPaper:
    """Read a PDF into an :class:`IngestedPaper` (text + metadata). Rasters stay lazy
    (:func:`page_raster`) so ingest is cheap until the vision stage actually needs pixels."""
    info = papers.pdf_info(path)
    return IngestedPaper(
        path=str(path),
        n_pages=info["pages"],
        metadata=info.get("metadata", {}),
        text=papers.extract_text(path, page_markers=True),
        pages=papers.extract_pages(path),
    )


def page_raster(path: str | Path, index: int, dpi: int = 150) -> bytes:
    """Rasterize one page to PNG bytes (0-based) — the lazy feed for the deferred vision
    chart-classifier. Passthrough to ``papers.render_page``."""
    return papers.render_page(path, index, dpi)
