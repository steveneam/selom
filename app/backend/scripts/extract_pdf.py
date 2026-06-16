"""Dogfood / ops CLI for the paper reader (papers.py).

Turn a deposited paper PDF into text and/or rasterized pages — the manual front door
to the "extract skills from papers" intake until a `POST /papers/extract` endpoint and
the intake UI exist.

Examples
--------
    # page count + metadata
    python scripts/extract_pdf.py paper.pdf --info

    # full text (with ===== PAGE n ===== markers) to stdout or a file
    python scripts/extract_pdf.py paper.pdf --text -o paper.txt

    # rasterize pages 8 and 10 (1-based) to PNGs at 150 dpi
    python scripts/extract_pdf.py paper.pdf --render 8,10 --dpi 150 --outdir figs/

Run with the EDR-safe interpreter (memory selom-backend-python-exec), e.g.:
    PYTHONPATH=.venv/Lib/site-packages <uv-managed-python> scripts/extract_pdf.py ...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # import papers.py

import papers  # noqa: E402


def _parse_pages(s: str) -> list[int]:
    """'8,10-12' (1-based, inclusive) -> [7, 9, 10, 11] (0-based)."""
    out: list[int] = []
    for part in s.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a) - 1, int(b)))
        elif part:
            out.append(int(part) - 1)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract text / pages from a paper PDF.")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--info", action="store_true", help="print page count + metadata")
    ap.add_argument("--text", action="store_true", help="extract text")
    ap.add_argument("--pages", help="restrict --text to these 1-based pages, e.g. '8,10-12'")
    ap.add_argument("--no-markers", action="store_true", help="omit ===== PAGE n ===== markers")
    ap.add_argument("--render", help="rasterize these 1-based pages to PNG, e.g. '8,10'")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--outdir", type=Path, default=Path("."), help="dir for rendered PNGs")
    ap.add_argument("-o", "--out", type=Path, help="write --text here instead of stdout")
    args = ap.parse_args(argv)

    if not args.pdf.exists():
        ap.error(f"no such file: {args.pdf}")
    if not (args.info or args.text or args.render):
        args.info = True  # sensible default

    if args.info:
        info = papers.pdf_info(args.pdf)
        print(f"pages: {info['pages']}")
        for k, v in info["metadata"].items():
            print(f"  {k}: {v}")

    if args.text:
        pages = _parse_pages(args.pages) if args.pages else None
        text = papers.extract_text(args.pdf, pages=pages, page_markers=not args.no_markers)
        if args.out:
            args.out.write_text(text, encoding="utf-8")
            print(f"wrote {len(text)} chars -> {args.out}")
        else:
            print(text)

    if args.render:
        idxs = _parse_pages(args.render)
        args.outdir.mkdir(parents=True, exist_ok=True)
        pngs = papers.render_pages(args.pdf, idxs, dpi=args.dpi)
        for i, png in zip(idxs, pngs):
            fn = args.outdir / f"{args.pdf.stem}_p{i + 1}.png"
            fn.write_bytes(png)
            print(f"rendered page {i + 1} -> {fn} ({len(png)} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
