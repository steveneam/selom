"""Ingest stage (E1) — a thin typed wrapper over ``papers.py`` (PDFium/pypdf, BSD).

The first, reused stage of the extraction pipeline: PDF → page text (exact chars) +
metadata, with lazy page rasters for the deferred vision stage. No new dependency — it
composes the already-tested ``papers`` module (the ``pdf`` extra). License posture E5:
permissive only (never poppler/PyMuPDF on the shipped path).

E7 — **two-input intake.** A paper is rarely one file: the MAIN PDF carries the figures and
their printed counts; SEPARATE supplements (PDF *or* xlsx *or* csv, human-designated) carry the
golden tables (ST2/ST6…) and the extended methods. Some papers combine both in one file (the
RPGRIP1 ``mmc1.pdf``), in which case the bundle is just a main with no supplements. So ingest is
**format-plural**: :func:`ingest_paper` reads a main + N supplements into a :class:`PaperBundle`
whose ``.text`` is the corpus the methods digest runs over and whose ``.tables`` inventories the
supplementary sheets. JEV ships xlsx supplements; Hani ships csv — the contract handles both.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

import papers

# supplement kinds (human-designated input; kind inferred from the file suffix) -------------
SUPP_PDF = "pdf"
SUPP_XLSX = "xlsx"
SUPP_CSV = "csv"
SUPP_UNKNOWN = "unknown"
_SUFFIX_KIND = {
    ".pdf": SUPP_PDF, ".xlsx": SUPP_XLSX, ".xls": SUPP_XLSX, ".xlsm": SUPP_XLSX, ".csv": SUPP_CSV,
}


class IngestedPaper(BaseModel):
    """A paper read into memory: full text (page-markered) + per-page text + metadata."""

    path: str
    n_pages: int
    metadata: dict = Field(default_factory=dict)
    text: str = ""               # all pages, with ``===== PAGE n =====`` markers
    pages: list[str] = Field(default_factory=list)  # per-page text, in page order


class IngestedSupplement(BaseModel):
    """One supplementary file alongside the main paper (E7). ``role`` is human-designated
    (``methods`` / ``tables`` / ``mixed`` / ``unknown``); ``kind`` is inferred from the suffix.

    PDF supplements expose ``text`` (extended methods); tabular supplements (xlsx/csv) expose
    ``sheets`` = ``{sheet_name: [column hints]}`` — enough to *find* a golden table (ST2/ST6) by
    name without loading the whole workbook (the full read stays in the live-recount drivers)."""

    path: str
    kind: str = SUPP_UNKNOWN
    role: str = "unknown"
    n_pages: int = 0
    text: str = ""
    sheets: dict[str, list[str]] = Field(default_factory=dict)
    note: str = ""


class PaperBundle(BaseModel):
    """A paper as it actually arrives (E7): a main PDF + N human-designated supplements.

    ``.text`` is the corpus the methods digest reads (main + every PDF supplement); DE-count
    extraction reads ``.main`` only (the figures live there). ``.tables`` inventories the
    supplementary sheets so a downstream reader can locate ST2/ST6 by name."""

    paper_id: str = ""
    main: IngestedPaper
    supplements: list[IngestedSupplement] = Field(default_factory=list)

    @property
    def text(self) -> str:
        """Main text + every PDF supplement's text — the methods-digest corpus (extended methods
        often live in a supplement). With no supplements this is just ``main.text``."""
        parts = [self.main.text]
        parts += [s.text for s in self.supplements if s.kind == SUPP_PDF and s.text]
        return "\n".join(p for p in parts if p)

    @property
    def tables(self) -> dict[str, dict[str, list[str]]]:
        """Supplementary tables keyed by filename → ``{sheet: [columns]}`` (xlsx/csv supplements)."""
        return {Path(s.path).name: s.sheets for s in self.supplements if s.sheets}

    def find_table(self, name: str) -> tuple[str, str] | None:
        """Locate a golden table by (case-insensitive) sheet name across all supplements →
        ``(supplement_filename, sheet_name)`` or ``None``. Finds ST2/ST6 without a full read."""
        low = name.lower()
        for fname, sheets in self.tables.items():
            for sheet in sheets:
                if sheet.lower() == low:
                    return fname, sheet
        return None


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


# --- E7: two-input intake (main + N supplements, format-plural) ---------------


def _kind_for(path: str | Path) -> str:
    return _SUFFIX_KIND.get(Path(path).suffix.lower(), SUPP_UNKNOWN)


def _table_columns(path: str | Path, kind: str) -> dict[str, list[str]]:
    """Cheap sheet inventory for a tabular supplement: ``{sheet: [first-row cell labels]}``.

    Reads ONE row per sheet (``nrows=1``, header-agnostic) so even a large Cepo matrix is cheap —
    the goal is to *find* a table by name, not to load it (the live-recount drivers own the full
    read). Degrades to ``{}`` + a note if pandas/openpyxl isn't installed."""
    try:
        import pandas as pd
    except ImportError:  # pragma: no cover - exercised only without pandas
        return {}
    if kind == SUPP_CSV:
        name = Path(path).stem
        try:
            row = pd.read_csv(path, header=None, nrows=1, dtype=str)
            return {name: [str(c) for c in row.iloc[0].tolist()]}
        except Exception:  # malformed/odd-delimited csv — record the table exists, columns unknown
            return {name: []}
    # xlsx family
    cols: dict[str, list[str]] = {}
    xls = pd.ExcelFile(path)
    for sheet in xls.sheet_names:
        try:
            row = pd.read_excel(xls, sheet_name=sheet, header=None, nrows=1, dtype=str)
            cols[sheet] = [str(c) for c in row.iloc[0].tolist()] if len(row) else []
        except Exception:
            cols[sheet] = []
    return cols


def ingest_supplement(path: str | Path, *, role: str = "unknown") -> IngestedSupplement:
    """Ingest one supplement by its file type (E7). PDF → text (extended methods); xlsx/csv →
    a sheet inventory (find ST2/ST6 by name); anything else → recorded as ``unknown``."""
    kind = _kind_for(path)
    if kind == SUPP_PDF:
        ip = ingest_pdf(path)
        return IngestedSupplement(path=str(path), kind=kind, role=role,
                                  n_pages=ip.n_pages, text=ip.text)
    if kind in (SUPP_XLSX, SUPP_CSV):
        sheets = _table_columns(path, kind)
        note = "" if sheets else "install the 'pdf' extra deps (pandas/openpyxl) to inventory tables"
        return IngestedSupplement(path=str(path), kind=kind, role=role, sheets=sheets, note=note)
    return IngestedSupplement(path=str(path), kind=SUPP_UNKNOWN, role=role,
                              note=f"unrecognised supplement type '{Path(path).suffix}'")


def ingest_paper(main: str | Path,
                 supplements: list = (),
                 *, paper_id: str = "") -> PaperBundle:
    """E7 entrypoint: read a MAIN paper PDF + N human-designated supplements into a
    :class:`PaperBundle`.

    ``supplements`` items may be a path (role inferred ``unknown``) or a ``(path, role)`` pair —
    the human designates which file is methods vs tables until auto-detection improves. When a
    paper combines main + supplement in one file (e.g. RPGRIP1 ``mmc1.pdf``), pass it as ``main``
    with no supplements."""
    supps: list[IngestedSupplement] = []
    for item in supplements:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            supps.append(ingest_supplement(item[0], role=str(item[1])))
        else:
            supps.append(ingest_supplement(item))
    return PaperBundle(paper_id=paper_id, main=ingest_pdf(main), supplements=supps)
