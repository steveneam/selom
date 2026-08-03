"""Render Selom's side of the Phase-F parity audit (docs/cnsplots-port/spec.md §1).

Five plot types — box · scatter · heatmap · volcano · dot/enrichment — through Selom's own
skills, on the **real** corpus, rastered at a declared physical size so the result can be laid
next to a matplotlib/seaborn figure of the same data and compared value for value.

**Why a fixed physical size and not a pixel size.** Typography is the biggest single difference
between two plotting stacks, and it is only comparable in *points*. matplotlib sizes fonts in pt
at a chosen dpi; Plotly sizes them in CSS px inside a CSS-px canvas. Rendering both at the same
inches x dpi makes ``13 css px == 9.75 pt`` directly readable against matplotlib's ``10 pt``.
Anything else compares two figures at different scales and calls the difference "style".

The pairing of skill -> corpus file -> params is **not restated here**: it is read from
``skills.smoke.CASES``, the same declared real-data case the smoke matrix gates on, so the audit
can never drift onto data the matrix does not cover.

Rastering goes through ``plotly.io`` directly rather than ``export.render`` on purpose — this is
a measuring instrument, not a product path, and it needs an explicit ``scale`` that the product's
width-override path deliberately pins to 1.

Usage (needs SELOM_DATASETS_DIR + Chrome for Kaleido)::

    uv run python scripts/render_parity.py --out ../../docs/cnsplots-port/audit
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

# The audit canvas: 6.0 x 4.5 in at 200 dpi. Both stacks render to exactly this, so a font,
# a tick length and a line width mean the same thing on both sides.
FIG_W_IN = 6.0
FIG_H_IN = 4.5
DPI = 200
CSS_DPI = 96.0

# plot type -> the skill that draws it. One per styling family named in the spec: categorical,
# continuous/annotated-scatter, matrix, annotated-scatter-with-thresholds, ranked-category.
TARGETS: dict[str, str] = {
    "box": "boxplot",
    "scatter": "pca",
    "heatmap": "heatmap",
    "volcano": "volcano",
    "dotplot": "enrichment",
}


def _raster(figure: dict, out_stem: pathlib.Path) -> dict:
    """Write ``<stem>.png`` and ``<stem>.svg`` at the audit canvas. Returns a size report."""
    import plotly.io as pio

    w_css, h_css = round(FIG_W_IN * CSS_DPI), round(FIG_H_IN * CSS_DPI)
    scale = DPI / CSS_DPI
    written = {}
    for fmt in ("png", "svg"):
        # validate=False: skill specs may carry props Plotly's strict validator rejects; they are
        # ours and already render in the browser (same reasoning as export.render).
        data = pio.to_image(
            figure, format=fmt, width=w_css, height=h_css,
            scale=scale if fmt == "png" else 1, validate=False,
        )
        path = out_stem.with_suffix(f".{fmt}")
        path.write_bytes(data)
        written[fmt] = len(data)
    return written


def _probe(figure: dict) -> dict:
    """The styling values a reader of the audit would otherwise have to squint for."""
    lay = figure.get("layout") or {}
    font = lay.get("font") or {}
    xax = lay.get("xaxis") or {}
    px_to_pt = 72.0 / CSS_DPI
    base = font.get("size")
    return {
        "font_family": font.get("family"),
        "base_size_px": base,
        "base_size_pt": round(base * px_to_pt, 2) if isinstance(base, (int, float)) else None,
        "paper_bgcolor": lay.get("paper_bgcolor"),
        "plot_bgcolor": lay.get("plot_bgcolor"),
        "margin": lay.get("margin"),
        "x_showgrid": xax.get("showgrid"),
        "x_gridcolor": xax.get("gridcolor"),
        "x_ticks": xax.get("ticks"),
        "x_ticklen": xax.get("ticklen"),
        "x_linecolor": xax.get("linecolor"),
        "x_mirror": xax.get("mirror"),
        "colorway": (lay.get("colorway") or [])[:8],
        "n_traces": len(figure.get("data") or []),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="directory for the rendered images + probe json")
    ap.add_argument("--style", default="selom",
                    help="style registry id (non-default styles are re-themed after the run — "
                         "run_skill itself always emits the default style)")
    ap.add_argument("--only", default="", help="comma-separated subset of the plot types")
    args = ap.parse_args(argv)

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
    from skills import smoke, theme
    from skills.contract import run_skill
    from skills.styles import DEFAULT_STYLE

    smoke.pin_process()  # refuse to audit a stub or a cache hit dressed up as a figure

    out = pathlib.Path(args.out).resolve()
    (out / "selom").mkdir(parents=True, exist_ok=True)
    wanted = [t.strip() for t in args.only.split(",") if t.strip()] or list(TARGETS)

    report: dict[str, dict] = {}
    for plot_type in wanted:
        skill_id = TARGETS[plot_type]
        case = smoke.CASES[skill_id]
        corpus = smoke._corpus()
        if corpus is None:
            print("[parity] SELOM_DATASETS_DIR is unset — refusing to audit on absent data",
                  file=sys.stderr)
            return 2
        path = corpus / case.dataset
        if not path.exists():
            print(f"[parity] {plot_type}: corpus file absent: {path}", file=sys.stderr)
            return 2

        start = time.perf_counter()
        figure = run_skill(skill_id, str(path), dict(case.params))
        if args.style != DEFAULT_STYLE:
            # `run_skill` themes centrally with the default style and takes no style argument, so
            # an alternate style is applied over the result. Theming only overwrites layout tokens
            # and marker style, so a second pass in another style lands on the same values a first
            # pass would — it is not additive.
            figure = theme.apply(figure, skill_id, style=args.style)
        elapsed = round(time.perf_counter() - start, 2)
        problem = smoke.check_figure(figure)
        if problem:
            print(f"[parity] {plot_type} ({skill_id}) produced no auditable figure: {problem}",
                  file=sys.stderr)
            return 1

        sizes = _raster(figure, out / "selom" / plot_type)
        report[plot_type] = {
            "skill": skill_id, "dataset": case.dataset, "params": case.params,
            "seconds": elapsed, "bytes": sizes, **_probe(figure),
        }
        print(f"[parity] {plot_type:8s} {skill_id:12s} {elapsed:6.2f}s  "
              f"png={sizes['png']//1024}KB svg={sizes['svg']//1024}KB")

    (out / "selom-probe.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"[parity] wrote {len(report)} figures + selom-probe.json to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
