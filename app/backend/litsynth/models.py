"""Typed inputs/outputs for the methods synthesizer (mirror ``extract/models.py``)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillRunRef(BaseModel):
    """One skill run in an analysis story: a skill id + the params it ran with.

    Matches what ``ReproRun.params`` already records — the synthesizer *consumes* a
    sequence of these and re-derives the Methods section. ``order`` pins the narrative
    sequence; when omitted it falls back to the run's position in the input list.
    """

    skill_id: str
    params: dict = Field(default_factory=dict)
    order: int | None = None


class MethodsSection(BaseModel):
    """A publication-ready Methods section composed from a sequence of skill runs."""

    intro: str                  # one modality-aware lead sentence (+ optional dataset descriptor)
    paragraphs: list[str]       # per-skill prose, in run order (no per-paragraph attribution)
    text: str                   # intro + paragraphs + one Selom attribution, space-joined
    citations: list[str]        # deduped, first-seen order across every skill in the story
    modality: str               # the dataset modality the story was framed for
    skill_ids: list[str]        # skills covered, in run order
    degraded: bool = False      # reserved for Phase B (a citation lookup failed); always False offline


class FigureLegend(BaseModel):
    """One paste-ready figure caption for a reproduction panel (the legend half of the layer).

    The per-skill caption text comes from ``legends.build_caption``; this record adds the figure
    numbering the ledger knows (which a bare own-data run does not), so a Reproduction view can
    list one captioned legend per figure panel."""

    figure: str                 # the figure id/number this panel belongs to (e.g. "4", "S1")
    panel: str = ""             # the panel letter within the figure, if any (e.g. "e")
    label: str                  # paste-ready label, e.g. "Figure 4e."
    skill_id: str               # the skill that produced the panel
    text: str                   # the caption sentence


class Citation(BaseModel):
    """A structured bibliographic record (Phase B citation lookup).

    Bibliographic fields only — these are not copyrightable (PubMed metadata is US-gov).
    ``metadata_license`` carries bioRxiv/medRxiv's per-record license tag (Phase C, e.g.
    ``cc_by`` / ``cc_by_nc_nd`` / ``cc_no``); it stays None for PubMed (US-gov, no per-record
    license). ``source`` is the index the record came from (``pubmed`` | ``biorxiv`` | ``medrxiv``).
    """

    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None          # journal / source
    doi: str | None = None
    pmid: str | None = None
    url: str | None = None
    source: str = "pubmed"            # pubmed | biorxiv | medrxiv | canonical
    metadata_license: str | None = None  # bioRxiv/medRxiv per-record license (Phase C); None for PubMed
