"""Journal-preset figure export (charter B4).

Renders an editable Plotly figure spec to a publication-ready raster/vector via
**Kaleido** (github.com/plotly/Kaleido) driving the *system* Chrome. Pure-Python,
no container at runtime: Kaleido v1 talks to an installed Chrome/Chromium over
CDP, so on a dev box with Chrome this needs neither Docker nor WSL. The Linux
deploy image is the only place a browser must be added (RISKS #2 — a B8 concern,
not a feature one).

Presets bake a journal's column width + DPI into pixel dimensions so a download
lands at the size a journal actually wants. Figures are sized in CSS px (keeping
fonts and line widths proportional) and DPI is pushed through Kaleido's `scale`
multiplier: width_css * scale == width_mm / 25.4 * dpi target px.
"""

from __future__ import annotations

from dataclasses import dataclass

# Reference px-per-inch Plotly uses for layout sizing. DPI rides on `scale`.
CSS_DPI = 96.0
MM_PER_IN = 25.4

VECTOR_FORMATS = frozenset({"svg", "pdf"})
RASTER_FORMATS = frozenset({"png"})
FORMATS = VECTOR_FORMATS | RASTER_FORMATS

# Default canvas when a figure carries no explicit size and no width override.
DEFAULT_WIDTH_PX = 800
DEFAULT_ASPECT = 4 / 3


class ExportUnavailable(RuntimeError):
    """Render could not run — Kaleido or a Chrome/Chromium browser is missing.

    Mapped to HTTP 503 by the API so a core (kaleido-less) install degrades
    honestly instead of 500-ing.
    """


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    width_mm: float
    dpi: int
    note: str = ""


# Journal figure widths are public author-guideline facts (column widths in mm).
# Heights stay figure-driven — aspect is preserved from the on-screen figure.
PRESETS: tuple[Preset, ...] = (
    Preset("nature-single", "Nature — single column", 89, 300, "89 mm @ 300 dpi"),
    Preset("nature-double", "Nature — double column", 183, 300, "183 mm @ 300 dpi"),
    Preset("cell-single", "Cell — single column", 85, 300, "85 mm @ 300 dpi"),
    Preset("cell-double", "Cell — double column", 174, 300, "174 mm @ 300 dpi"),
    Preset("science-single", "Science — single column", 57, 300, "57 mm @ 300 dpi"),
    Preset("science-double", "Science — double column", 121, 300, "121 mm @ 300 dpi"),
    Preset("plos-full", "PLOS — full width", 190, 300, "190 mm @ 300 dpi"),
    Preset("hi-res-square", "High-res square", 150, 600, "150 mm @ 600 dpi"),
)
PRESET_BY_ID = {p.id: p for p in PRESETS}


def list_presets() -> list[dict]:
    """Serializable preset catalog for the FE export menu (single source of truth)."""
    return [
        {"id": p.id, "label": p.label, "width_mm": p.width_mm, "dpi": p.dpi, "note": p.note}
        for p in PRESETS
    ]


def _figure_aspect(figure: dict) -> float:
    layout = figure.get("layout") or {}
    w, h = layout.get("width"), layout.get("height")
    if isinstance(w, (int, float)) and isinstance(h, (int, float)) and h:
        return w / h
    return DEFAULT_ASPECT


def resolve_dimensions(
    figure: dict,
    *,
    fmt: str,
    preset: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> tuple[int, int, float]:
    """Return ``(width_px, height_px, scale)`` for Kaleido.

    Width precedence: explicit override → preset (mm→css-px) → the figure's own
    layout width → a default. Height preserves the figure's aspect unless given.
    DPI rides on ``scale`` for raster output; vectors are resolution-independent
    so ``scale`` stays 1.
    """
    p = PRESET_BY_ID.get(preset) if preset else None
    if preset and p is None:
        raise ValueError(f"unknown preset '{preset}'")

    scale = 1.0
    if width is not None:
        width_px = int(width)
    elif p is not None:
        width_px = round(p.width_mm / MM_PER_IN * CSS_DPI)
        if fmt in RASTER_FORMATS:
            scale = p.dpi / CSS_DPI
    else:
        layout_w = (figure.get("layout") or {}).get("width")
        width_px = int(layout_w) if isinstance(layout_w, (int, float)) else DEFAULT_WIDTH_PX
        if fmt in RASTER_FORMATS:
            scale = 2.0  # retina default when exporting at the figure's own size

    if height is not None:
        height_px = int(height)
    else:
        height_px = round(width_px / _figure_aspect(figure))

    return max(1, width_px), max(1, height_px), scale


def _friendly(err: Exception) -> str:
    msg = str(err).lower()
    if "chrome" in msg or "browser" in msg or "choreographer" in msg:
        return (
            "Figure export needs a Chrome/Chromium browser. Install Chrome (or run "
            "`plotly_get_chrome`) so Kaleido can render the figure."
        )
    return (
        "Figure export needs Kaleido + a Chrome/Chromium browser. Install it with "
        "`uv sync --extra export` and make sure Chrome is available."
    )


def render(
    figure: dict,
    fmt: str,
    *,
    preset: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> bytes:
    """Render a Plotly figure spec to image bytes. Raises :class:`ExportUnavailable`
    when Kaleido / Chrome is missing, :class:`ValueError` for bad inputs."""
    if fmt not in FORMATS:
        raise ValueError(f"unsupported format '{fmt}' (expected one of {sorted(FORMATS)})")

    width_px, height_px, scale = resolve_dimensions(
        figure, fmt=fmt, preset=preset, width=width, height=height
    )

    try:
        import plotly.io as pio
    except Exception as e:  # plotly is a core dep, but be defensive
        raise ExportUnavailable(_friendly(e)) from e

    try:
        # validate=False: editor-edited specs may carry props Plotly's strict
        # validator rejects; the figures are ours and already render in-browser.
        return pio.to_image(
            figure, format=fmt, width=width_px, height=height_px, scale=scale, validate=False
        )
    except Exception as e:  # ImportError(kaleido) or runtime(no Chrome) → 503
        raise ExportUnavailable(_friendly(e)) from e
