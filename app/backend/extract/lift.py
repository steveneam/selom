"""Reconstruction stage (X3, Track A) — vector-faithful panel lift.

Track B (`reconstruct.py`) *redraws* a panel from recovered data — editable, but a fresh figure
that is never pixel-identical to the publisher's (open-Q#3 proved SSIM cannot even gate it against
a scan). **Track A is the only pixel-faithful path**, and it works by *not* redrawing at all: lift
the panel straight out of the source PDF, preserving the authors' own marks.

Two honest tiers (the "honest ceiling" of the sub-spec):

* **Vector crop** — copy the page and clip it to the panel's bounding box (set ``MediaBox`` +
  ``CropBox``, no rasterization). The result renders **pixel-identical** to the same region of the
  original at any resolution, because the content stream is untouched — for the vector content it is
  resolution-independent (``scalable``). This is the differentiator.
* **Raster extract** — when a panel is an embedded bitmap (microscopy, scatter-as-PNG), pull the
  Image XObject bytes exactly (image-identical), but it is **not** vector-scalable (honest ceiling #2).

License posture (E1/E5): built on **pypdf** (BSD-3, already a shipped dep via the ``pdf`` extra) — no
PyMuPDF/``fitz`` (AGPL), no poppler (GPL). The sub-spec named pikepdf/qpdf/svgpathtools as candidates;
pypdf's page-clip + XObject access cover the lift without adding a dependency.

The crop is verified pixel-identical by **render → SSIM(registered)=1.0** against the same region of
the source (the registered regime where SSIM *is* valid — see `reconstruct.self_qa`). That render
needs PDFium and is the owner-machine dogfood; the unit tests assert the lift mechanics renderer-free.
"""

from __future__ import annotations

import io

from pydantic import BaseModel

# Path-painting / path-construction operators — their presence means the page draws vectors
# (rectangles, lines, curves, fills/strokes) rather than only placing images/text.
_VECTOR_OPS = (b" re\n", b" re ", b"\nre\n", b" m\n", b" m ", b" l\n", b" l ",
               b" c\n", b" c ", b"\nf\n", b" f\n", b" f ", b"\nS\n", b" S\n", b" B\n", b" W\n")


def _require(module: str):
    try:
        return __import__(module)
    except ImportError as exc:  # pragma: no cover - only without the extra
        raise RuntimeError(
            f"The figure lifter needs '{module}' (optional 'pdf' extra). Install: uv sync --extra pdf"
        ) from exc


def _reader(pdf):
    """A ``PdfReader`` from a path or in-memory PDF bytes."""
    pypdf = _require("pypdf")
    if isinstance(pdf, (bytes, bytearray)):
        return pypdf.PdfReader(io.BytesIO(bytes(pdf)))
    return pypdf.PdfReader(str(pdf))


class XObjectRef(BaseModel):
    """One external object placed on a page — an embedded ``Image`` (raster) or ``Form`` (a vector
    sub-group). The raw inventory behind the vector/raster routing decision."""

    name: str            # resource key, e.g. "/Im0" / "/Fm1"
    subtype: str         # "Image" | "Form" | ""
    width: int | None = None
    height: int | None = None


class LiftedPanel(BaseModel):
    """The Track-A verdict for one lifted panel. ``faithful`` = pixel-identical to the authors' panel
    at source resolution (true for both tiers — the lift never resamples). ``scalable`` = resolution-
    independent (vector crop only); a raster extract is image-identical but not scalable."""

    panel_key: str = ""
    kind: str            # "vector" | "raster"
    faithful: bool       # pixel-identical to the source at its native resolution
    scalable: bool       # resolution-independent (vector only)
    mimetype: str        # "application/pdf" | "image/png" | ...
    page_index: int = 0
    bbox: tuple[float, float, float, float] | None = None
    note: str = ""


def list_page_xobjects(pdf, page_index: int) -> list[XObjectRef]:
    """Inventory of the Image/Form XObjects placed on a page (0-based ``page_index``)."""
    reader = _reader(pdf)
    _bounds(page_index, len(reader.pages))
    res = reader.pages[page_index].get("/Resources")
    xobjs = res.get("/XObject") if res else None
    out: list[XObjectRef] = []
    if xobjs:
        for name, ref in xobjs.get_object().items():
            obj = ref.get_object()
            w, h = obj.get("/Width"), obj.get("/Height")
            out.append(XObjectRef(
                name=name, subtype=str(obj.get("/Subtype", "")).lstrip("/"),
                width=int(w) if w is not None else None,
                height=int(h) if h is not None else None))
    return out


def page_is_vector(pdf, page_index: int) -> bool:
    """Heuristic: does the page's content stream paint vector paths (vs only images/text)?

    Decodes the content stream and looks for path-construction/painting operators. Used to label a
    lifted crop ``vector`` (scalable) vs ``raster`` (image-only)."""
    reader = _reader(pdf)
    _bounds(page_index, len(reader.pages))
    try:
        data = reader.pages[page_index].get_contents().get_data()
    except Exception:  # pragma: no cover - defensive: malformed/empty content
        return False
    return any(op in data for op in _VECTOR_OPS)


def lift_panel_region(pdf, page_index: int, bbox: tuple[float, float, float, float], *,
                      panel_key: str = "") -> tuple[bytes, LiftedPanel]:
    """Vector-faithful lift: clip the page to ``bbox`` and emit a standalone 1-page PDF.

    ``bbox`` is ``(x0, y0, x1, y1)`` in PDF points, origin bottom-left (PDF convention). The content
    stream is untouched — only ``MediaBox``/``CropBox`` change — so the result renders **pixel-identical**
    to the same region of the source at any DPI. Returns the PDF bytes + a :class:`LiftedPanel`."""
    pypdf = _require("pypdf")
    from pypdf.generic import RectangleObject

    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"bbox must have x1>x0 and y1>y0, got {bbox}")
    reader = _reader(pdf)
    _bounds(page_index, len(reader.pages))
    is_vector = page_is_vector(pdf, page_index)

    writer = pypdf.PdfWriter()
    writer.add_page(reader.pages[page_index])
    rect = RectangleObject([x0, y0, x1, y1])
    writer.pages[0].mediabox = rect
    writer.pages[0].cropbox = rect
    buf = io.BytesIO()
    writer.write(buf)

    kind = "vector" if is_vector else "raster"
    return buf.getvalue(), LiftedPanel(
        panel_key=panel_key, kind=kind, faithful=True, scalable=is_vector,
        mimetype="application/pdf", page_index=page_index, bbox=(x0, y0, x1, y1),
        note=("vector-faithful crop (pixel-identical at any DPI; content stream untouched)"
              if is_vector else
              "page crop (pixel-identical at source DPI; raster content — not vector-scalable)"))


def extract_raster_panel(pdf, page_index: int, *, which: int = 0,
                         panel_key: str = "") -> tuple[bytes, LiftedPanel]:
    """Extract one embedded bitmap (Image XObject) from a page, exactly as the authors stored it.

    ``which`` selects among the page's images (0-based). The bytes are image-identical to the source
    (honest ceiling #2) but **not** vector-scalable. Raises ``IndexError`` if the page has no image
    or ``which`` is out of range."""
    reader = _reader(pdf)
    _bounds(page_index, len(reader.pages))
    images = list(reader.pages[page_index].images)
    if not images:
        raise IndexError(f"page {page_index} has no embedded raster images to extract")
    if which < 0 or which >= len(images):
        raise IndexError(f"image index {which} out of range (page has {len(images)} images)")
    img = images[which]
    name = (getattr(img, "name", "") or "").lower()
    mimetype = "image/jpeg" if name.endswith((".jpg", ".jpeg")) else "image/png"
    return img.data, LiftedPanel(
        panel_key=panel_key, kind="raster", faithful=True, scalable=False,
        mimetype=mimetype, page_index=page_index,
        note=f"embedded bitmap '{getattr(img, 'name', '')}' extracted exactly (image-identical; "
             f"not vector-scalable)")


def _bounds(index: int, n: int) -> None:
    if index < 0 or index >= n:
        raise IndexError(f"page index {index} out of range (document has {n} pages)")
