"""Staged panel-asset loader for the extract↔Reproduction bridge (★D, Option A).

The bridge shows each paper panel as a thumbnail in the read-only Reproduction view and lets the
reader open the **X3-lifted** panel in the chart-extractor. The lift needs the source PDF + a
per-panel ``(page_index, bbox)`` — neither of which is available at runtime (the PDFs live outside
the repo; ledger panels carry no bbox). So an **offline staging step** (``scripts/stage_panel_assets.py``,
owner machine) records the lift metadata + writes a served thumbnail per panel into
``repro-assets/{slug}/``; this module loads that metadata and attaches it to the served ledger.

FastAPI-free + degrade-safe by design: a paper with no staged assets simply gets no thumbnails (the
view renders exactly as before). The attached ``PanelLift`` is **purely presentational** — it never
carries a golden/computed value, so the Reproducibility Score is byte-identical with or without it
(the load-bearing digitize ≠ reproduce invariant, enforced by ``tests/test_repro_assets.py``).
"""

from __future__ import annotations

import json
import pathlib

import reproduction as R

# repo-relative; the same tree the staging script writes and the FastAPI static mount serves.
ASSETS_ROOT = pathlib.Path(__file__).resolve().parent / "repro-assets"

# Chart forms a reader can actually trace tick-by-tick in the picker. This is exactly the X4
# chart-extractor's recoverable set (bar/line/scatter) — a boxplot or heatmap has no point series to
# read back, so it gets a thumbnail but no "Digitize" button.
DIGITIZABLE_FORMS = {"bar", "line", "scatter"}


def _manifest_path(slug: str, root: pathlib.Path | None = None) -> pathlib.Path:
    return (root or ASSETS_ROOT) / slug / "panels.json"


def load_lifts(slug: str, *, root: pathlib.Path | None = None) -> dict[str, R.PanelLift]:
    """Staged ``{panel_key: PanelLift}`` for ``slug`` — empty (never raises) when nothing is staged.

    A malformed or absent manifest degrades to ``{}`` so a serving request can never break on a
    staging artifact."""
    path = _manifest_path(slug, root)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, R.PanelLift] = {}
    for key, meta in (raw.get("panels") or {}).items():
        try:
            out[key] = R.PanelLift(**meta)
        except (TypeError, ValueError):
            continue  # skip a bad row, keep the rest
    return out


def attach_lifts(ledger: R.Ledger, *, root: pathlib.Path | None = None) -> R.Ledger:
    """Attach staged thumbnails to a driven ledger's panels (in place) and return it.

    Idempotent + presentational only: sets ``panel.lift`` for matching keys, touches nothing the
    scorecard reads. A panel with no staged asset keeps ``lift=None``. The bridge button is gated to
    chart forms (``digitizable``) regardless of what the manifest claims, so a non-chart panel can
    never advertise a tracing entry."""
    lifts = load_lifts(ledger.paper.slug, root=root)
    for panel in ledger.panels:
        lift = lifts.get(panel.key)
        if lift is None:
            continue
        lift.digitizable = lift.digitizable and panel.chart_form in DIGITIZABLE_FORMS
        panel.lift = lift
    return ledger
