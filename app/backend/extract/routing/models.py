"""Typed artifacts the Skill Keyword Index produces.

A ``RouteTarget`` is a string — ``"skill:<id>"`` (a live Selom skill) or ``"oos:<reason>"``
(an out-of-scope modality). The ``oos`` reasons map onto the reproduction engine's existing
scope constants (``MODALITY_UNSUPPORTED`` / ``WET_LAB`` / ``DATA_NOT_DEPOSITED``) so the
feasibility map speaks the same out-of-scope vocabulary as the ledger — no new scope words.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

import reproduction as R

# RouteTarget string prefixes.
SKILL_PREFIX = "skill:"
OOS_PREFIX = "oos:"

# out-of-scope reason -> the engine scope constant it maps to. atac/spatial/grn are
# MODALITY_UNSUPPORTED (data is deposited, Selom just has no skill); wet_lab is staining/
# qPCR/imaging (not sequencing at all); not_deposited is the DATA_NOT_DEPOSITED case.
OOS_SCOPE = {
    "atac": R.MODALITY_UNSUPPORTED,
    "spatial": R.MODALITY_UNSUPPORTED,
    "grn": R.MODALITY_UNSUPPORTED,
    "wet_lab": R.WET_LAB,
    "not_deposited": R.DATA_NOT_DEPOSITED,
}


def is_skill(target: str) -> bool:
    return target.startswith(SKILL_PREFIX)


def skill_id(target: str) -> str:
    """The skill id of a ``skill:<id>`` target (``""`` for an oos target)."""
    return target[len(SKILL_PREFIX):] if is_skill(target) else ""


def oos_reason(target: str) -> str:
    """The reason of an ``oos:<reason>`` target (``""`` for a skill target)."""
    return target[len(OOS_PREFIX):] if target.startswith(OOS_PREFIX) else ""


def scope_of(target: str) -> str:
    """The engine scope constant for a target — ``transcriptomic`` for a skill, else the
    mapped out-of-scope scope (``modality_unsupported`` / ``wet_lab`` / ...)."""
    if is_skill(target):
        return R.TRANSCRIPTOMIC
    return OOS_SCOPE.get(oos_reason(target), R.MODALITY_UNSUPPORTED)


class VocabEntry(BaseModel):
    """One vocabulary row: the surface terms that route to a target. ``kind`` is ``registry``
    (auto-derived from a skill's own self-description — extends free per new skill) or
    ``curated`` (the hand-authored synonym layer = the domain-knowledge moat). ``weight``
    scales a hit's score; curated terms outweigh the noisier registry-derived ones."""

    terms: list[str]
    target: str
    kind: str = "curated"
    weight: float = 1.0
    note: str = ""


class RoutingHit(BaseModel):
    """One matched term in the paper → its target, tagged with the section it was found in
    (drives the section weighting) and, for legend/results hits, the figure it belongs to."""

    term: str
    target: str
    section: str           # methods | legend | results | body  (refs are excluded, never emitted)
    weight: float
    figure: str = ""


class RoutingCandidate(BaseModel):
    """A target with its summed score and the hits that support it (the evidence trail —
    no black-box routing)."""

    target: str
    score: float
    evidence: list[RoutingHit] = Field(default_factory=list)

    @property
    def in_scope(self) -> bool:
        return is_skill(self.target)


class FigureRoute(BaseModel):
    """The routing verdict for one figure: ranked candidates + the top target + whether it is
    in Selom's scope + a confidence (the margin between the top two candidates)."""

    figure: str
    candidates: list[RoutingCandidate] = Field(default_factory=list)
    top: str | None = None
    in_scope: bool = True
    reason: str = ""        # the oos reason when out-of-scope (atac/spatial/grn/wet_lab)
    confidence: float = 0.0


class FeasibilityMap(BaseModel):
    """The Skill Keyword Index's output for a paper — the auto-generated Dorgau-style table:
    a per-figure route + a paper-level target rollup + the method-nouns that routed to NO skill
    (``unmatched_terms`` = the Skill Foundry gap signal, surfaced not auto-filed in v1)."""

    paper_id: str = ""
    figures: list[FigureRoute] = Field(default_factory=list)
    paper_targets: list[RoutingCandidate] = Field(default_factory=list)
    unmatched_terms: list[str] = Field(default_factory=list)
