"""Stage X3 panel thumbnails for the extract↔Reproduction bridge (★D, Option A) — DEV/OWNER ONLY.

This is the offline step the bridge depends on (it is **never** in the shipped runtime — ADR-0002
spirit, like the R oracle). The paper PDFs live outside the repo on the owner machine; this script
reads a per-paper bbox table, lifts each panel with the shipped X3 lifter (``extract.lift``), renders
a thumbnail with PDFium, and writes both the PNGs and a ``panels.json`` manifest into
``repro-assets/{slug}/``. ``repro_assets.attach_lifts`` then serves them read-only; nothing here runs
at request time.

Input — ``repro-assets/{slug}/bboxes.json`` (hand/segmenter authored)::

    {
      "pdf": "C:/.../1-s2.0-S2213671122005914-main.pdf",
      "panels": {
        "2B": {"page_index": 3, "bbox": [60, 470, 300, 700], "chart_form": "bar"},
        "3B": {"page_index": 4, "bbox": [40, 120, 560, 560], "chart_form": "upset"}
      }
    }

``bbox`` is ``(x0, y0, x1, y1)`` in PDF points, origin bottom-left (PDF convention — matches
``lift_panel_region``). Run::

    python scripts/stage_panel_assets.py hani
    python scripts/stage_panel_assets.py hani --bboxes /abs/path/bboxes.json --scale 2.5
"""

from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from extract import lift as X3  # noqa: E402
from repro_assets import ASSETS_ROOT, DIGITIZABLE_FORMS  # noqa: E402

MAX_THUMB_PX = 900  # cap the long edge so a committed thumbnail stays small


def _render_pdf_to_png(pdf_bytes: bytes, scale: float) -> bytes:
    """Render a single-page (cropped) PDF to a PNG thumbnail with PDFium."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        page = doc[0]
        # cap the scale so the long edge stays <= MAX_THUMB_PX
        w_pt, h_pt = page.get_size()
        scale = min(scale, MAX_THUMB_PX / max(w_pt, h_pt))
        pil = page.render(scale=scale).to_pil()
        buf = io.BytesIO()
        pil.convert("RGB").save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    finally:
        doc.close()


def stage(slug: str, *, bboxes_path: pathlib.Path | None = None, scale: float = 2.0) -> dict:
    """Lift + render every panel in the slug's bbox table → PNGs + panels.json. Returns the manifest."""
    out_dir = ASSETS_ROOT / slug
    bboxes_path = bboxes_path or (out_dir / "bboxes.json")
    if not bboxes_path.exists():
        raise SystemExit(f"no bbox table at {bboxes_path} — author it first (see the module docstring)")

    table = json.loads(bboxes_path.read_text(encoding="utf-8"))
    pdf_path = pathlib.Path(table["pdf"])
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")
    pdf_bytes = pdf_path.read_bytes()
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, dict] = {}
    for key, spec in table["panels"].items():
        page_index = int(spec["page_index"])
        bbox = tuple(float(v) for v in spec["bbox"])
        chart_form = str(spec.get("chart_form", ""))
        pdf_crop, lifted = X3.lift_panel_region(pdf_bytes, page_index, bbox, panel_key=key)
        png = _render_pdf_to_png(pdf_crop, scale)
        (out_dir / f"{key}.png").write_bytes(png)
        manifest[key] = {
            "page_index": page_index,
            "bbox": list(bbox),
            "kind": lifted.kind,
            "thumbnail_url": f"/repro-assets/{slug}/{key}.png",
            "digitizable": chart_form in DIGITIZABLE_FORMS,
        }
        print(f"  {key}: {lifted.kind} crop -> {key}.png ({len(png) // 1024} KB), "
              f"digitizable={manifest[key]['digitizable']}")

    (out_dir / "panels.json").write_text(json.dumps({"panels": manifest}, indent=2), encoding="utf-8")
    print(f"wrote {out_dir / 'panels.json'} ({len(manifest)} panels)")
    return manifest


if __name__ == "__main__":  # pragma: no cover — dev/owner harness
    ap = argparse.ArgumentParser(description="Stage X3 panel thumbnails for the Reproduction bridge")
    ap.add_argument("slug", help="paper slug (e.g. hani)")
    ap.add_argument("--bboxes", type=pathlib.Path, default=None, help="override bbox table path")
    ap.add_argument("--scale", type=float, default=2.0, help="PDFium render scale (capped by MAX_THUMB_PX)")
    args = ap.parse_args()
    stage(args.slug, bboxes_path=args.bboxes, scale=args.scale)
