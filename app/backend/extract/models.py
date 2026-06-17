"""Typed artifacts the Figure-Extraction Subsystem (R4/X1) produces from a paper PDF.

The structured form of the hand-written ``<slug>_target_spec.md`` — what
``reproduction_{rpgrip1,jev}.build_ledger()`` encode by hand and X1 auto-generates. Pure
pydantic; the conversion into the engine's ``Panel``/``Golden`` lives in ``extract.golden``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from reproduction import Inconsistency  # one-directional: extract → reproduction

# Golden provenance (mirrors reproduction.SOURCE_*; literals keep this module light).
SOURCE_FIGURE = "figure"
SOURCE_LEGEND = "legend"
SOURCE_METHODS = "methods"
SOURCE_EXTRACTED = "extracted"


class GoldenTarget(BaseModel):
    """One printed value recovered from the PDF (a row of the golden-target table).

    ``confidence`` is 1.0 for a text-layer-exact integer (E2) and lower for a vision-only
    read. ``source`` records where in the paper it was printed (figure/legend/methods)."""

    paper_id: str
    figure: str = ""
    panel: str = ""
    metric: str
    value: float | int | str
    unit: str = ""
    source: str = SOURCE_EXTRACTED
    confidence: float = 1.0
    note: str = ""
    inconsistency_ref: int | None = None

    @property
    def panel_key(self) -> str:
        return f"{self.figure}{self.panel}"


class MethodsDigest(BaseModel):
    """The STAR-Methods recipe parsed to the tool/threshold/contrast/filter/normalization
    that define how a number was produced (the inputs to the ``map`` + ``validate`` stages)."""

    panel_key: str = ""
    tools: list[str] = Field(default_factory=list)
    normalizations: list[str] = Field(default_factory=list)
    thresholds: list[str] = Field(default_factory=list)
    filters: list[str] = Field(default_factory=list)
    raw: str = ""


class PanelDraft(BaseModel):
    """A figure split into a labelled panel + its chart form + scope (guard 7). Slice-1 is
    coarse (panel-segment automation is deferred); ``chart_form`` fills in once vision lands."""

    paper_id: str
    figure: str
    panel: str = ""
    chart_form: str = ""
    scope: str = "transcriptomic"
    caption: str = ""
    confidence: float = 1.0

    @property
    def key(self) -> str:
        return f"{self.figure}{self.panel}"


class ExtractedSpec(BaseModel):
    """The bundle X1 emits per paper — the auto-generated target spec the engine consumes."""

    paper_id: str
    panels: list[PanelDraft] = Field(default_factory=list)
    goldens: list[GoldenTarget] = Field(default_factory=list)
    methods: list[MethodsDigest] = Field(default_factory=list)
    inconsistencies: list[Inconsistency] = Field(default_factory=list)
