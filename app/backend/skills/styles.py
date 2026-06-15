"""Journal style registry — named visual style packs for figures (Phase 1).

A *style* is a token pack that parametrizes what ``theme.py`` applies to every Plotly
spec: font family + per-role sizes, ink/grid/axis/paper colours, the qualitative
colourway, the continuous colourscale, volcano semantic colours, and title alignment.
``theme.apply(spec, skill_id, style=...)`` reads these tokens, so a style only changes
how a figure *looks* — never its data — and figures stay editable Plotly specs.

``selom`` reproduces today's hard-coded theme verbatim (golden-pinned default). The
journal styles differ in the things journals actually mandate — legibility,
colourblind-safety, density — not invented brand palettes. Proprietary fonts
(Helvetica/Arial) map to the open, metric-compatible **Arimo**; nothing paid is bundled.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

# Open, metric-compatible stand-ins for the licensed journal fonts (Arimo == Arial metrics).
SANS_OPEN = "Arimo, Arial, Helvetica, sans-serif"

# Canonical colourblind-safe qualitative palette (Okabe–Ito) for the journal styles.
OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]
GRAYS = ["#111827", "#4b5563", "#6b7280", "#9ca3af", "#1f2937", "#374151", "#d1d5db", "#000000"]


@dataclass(frozen=True)
class Style:
    id: str
    label: str
    description: str
    attribution: str
    # typography
    font_family: str
    size_base: int = 13
    size_title: int = 16
    size_axis_title: int = 13
    size_tick: int = 11
    size_legend: int = 11
    size_text: float = 10.5            # in-figure text labels (e.g. volcano gene names)
    # colour
    ink: str = "#33404d"               # body text / ticks
    ink_strong: str = "#1f2a37"        # titles, axis labels
    grid: str = "#eef1f5"
    axis: str = "#c4ccd4"
    paper: str = "#ffffff"
    colorway: list[str] = field(default_factory=lambda: list(OKABE_ITO))
    sequential: str = "Viridis"
    volcano: dict[str, str] = field(
        default_factory=lambda: {"n.s.": "#cdd4dc", "up": "#c0392b", "down": "#2f6db0"}
    )
    # layout
    title_align: str = "left"          # left | center
    force_grid: bool | None = None     # None = let the figure type decide; bool = override

    def public(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "attribution": self.attribution,
        }


# --- the v1 built-in styles ---------------------------------------------------

# selom: TODAY'S theme, verbatim — every default token above already matches the
# constants in theme.py, so theme.apply(..., "selom") is byte-identical (golden-pinned).
_SELOM = Style(
    id="selom",
    label="Selom default",
    description="Selom's house publication look — Inter, blue/amber colourblind-aware palette.",
    attribution="",
    font_family="Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif",
    colorway=["#2f6db0", "#e08a2b", "#3f9b6b", "#c0392b", "#7d5ba6", "#1f9aa6", "#9aa017", "#6b7280"],
)

_NATURE = Style(
    id="nature",
    label="Nature",
    description="Nature house style — open sans-serif, gridless, black axes, colourblind-safe.",
    attribution="Style follows Nature figure guidelines (springernature.com); font: Arimo (Arial-metric).",
    font_family=SANS_OPEN,
    size_title=15,
    ink="#222222",
    ink_strong="#000000",
    grid="#ededed",
    axis="#000000",
    colorway=list(OKABE_ITO),
    volcano={"n.s.": "#bfc6cd", "up": "#D55E00", "down": "#0072B2"},  # CB-safe orange/blue
    force_grid=False,
)

_CELL = Style(
    id="cell",
    label="Cell",
    description="Cell house style — open sans-serif, light grid, colourblind-safe palette.",
    attribution="Style follows Cell Press STAR Methods figure guidelines (cell.com); font: Arimo.",
    font_family=SANS_OPEN,
    size_title=15,
    ink="#1a1a1a",
    ink_strong="#000000",
    grid="#f0f0f0",
    axis="#333333",
    colorway=list(OKABE_ITO),
)

_SCIENCE = Style(
    id="science",
    label="Science",
    description="Science house style — compact open sans-serif, thin lines, single-column friendly.",
    attribution="Style follows Science figure-prep guidelines (science.org); font: Arimo.",
    font_family=SANS_OPEN,
    size_base=12,
    size_title=14,
    size_axis_title=12,
    size_tick=10,
    size_legend=10,
    ink="#1a1a1a",
    ink_strong="#000000",
    grid="#eeeeee",
    axis="#000000",
    colorway=list(OKABE_ITO),
    force_grid=False,
)

_GRAYSCALE = Style(
    id="grayscale",
    label="Grayscale (print-safe)",
    description="Greyscale-only — distinguishes series without colour, for cheap print / accessibility.",
    attribution="Print-safe variant; font: Arimo.",
    font_family=SANS_OPEN,
    ink="#000000",
    ink_strong="#000000",
    grid="#e0e0e0",
    axis="#000000",
    colorway=list(GRAYS),
    sequential="Greys",
    volcano={"n.s.": "#cccccc", "up": "#000000", "down": "#777777"},
)

STYLES: dict[str, Style] = {s.id: s for s in (_SELOM, _NATURE, _CELL, _SCIENCE, _GRAYSCALE)}
DEFAULT_STYLE = "selom"


def get_style(style: str | Style | None) -> Style:
    """Resolve a style id (or pass-through a Style) to a Style; unknown/None → default."""
    if isinstance(style, Style):
        return style
    return STYLES.get(style or DEFAULT_STYLE, STYLES[DEFAULT_STYLE])


def list_styles() -> list[dict]:
    """Catalog for the FE style picker (id/label/description/attribution)."""
    return [s.public() for s in STYLES.values()]


__all__ = ["Style", "STYLES", "DEFAULT_STYLE", "get_style", "list_styles", "replace"]
