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


class Citation(BaseModel):
    """A structured bibliographic record (Phase B citation lookup).

    Bibliographic fields only — these are not copyrightable (PubMed metadata is US-gov).
    ``metadata_license`` is reserved for bioRxiv's per-record license tag (Phase C);
    it stays None for PubMed. ``source`` is the index the record came from.
    """

    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None          # journal / source
    doi: str | None = None
    pmid: str | None = None
    url: str | None = None
    source: str = "pubmed"            # pubmed | biorxiv | canonical
    metadata_license: str | None = None  # bioRxiv per-record license (Phase C); None for PubMed
