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
    (drives the section weighting) and, for legend/results hits, the figure it belongs to.
    ``relaxed`` marks a token-canonical (L3) match rather than an exact (L1) one."""

    term: str
    target: str
    section: str           # methods | legend | results | body  (refs are excluded, never emitted)
    weight: float
    figure: str = ""
    relaxed: bool = False


class RoutingCandidate(BaseModel):
    """A target with its summed score and the hits that support it (the evidence trail —
    no black-box routing)."""

    target: str
    score: float
    evidence: list[RoutingHit] = Field(default_factory=list)

    @property
    def in_scope(self) -> bool:
        return is_skill(self.target)


class RouteVerdict(BaseModel):
    """The optional L4 AI adjudication of one figure (fast-follow #2). The AI VERIFIES — it never
    runs on the critical path: a verdict only ever annotates/refines a figure the deterministic
    layer already routed. ``verdict`` is ``confirm`` (keep the deterministic top), ``override``
    (the AI picked ``target`` instead), or ``uncertain`` (flagged, left as-is)."""

    figure: str
    verdict: str = "confirm"   # confirm | override | uncertain
    target: str = ""           # the confirmed/overridden skill:/oos: target
    confidence: float = 0.0
    note: str = ""


class SynonymCandidate(BaseModel):
    """A mined synonym proposal (fast-follow #2): a method-noun that routed to NO target but
    co-occurs (same section) with routed skills — a candidate ``term -> target`` for ``synonyms.json``.
    SURFACED FOR REVIEW only; the curated moat is never auto-written (spec resolved-decision #3)."""

    term: str
    section: str = ""
    co_targets: list[str] = Field(default_factory=list)  # routed targets co-present in the section
    note: str = ""


class FigureRoute(BaseModel):
    """The routing verdict for one figure: ranked candidates + the top target + whether it is
    in Selom's scope + a confidence + the evidence provenance.

    ``attribution`` records WHERE the routing evidence came from — ``legend`` (anchored to the
    figure's own caption, the strongest signal), ``results`` (best-effort proximity to an in-text
    ``Fig N`` reference, inherently weaker), or ``none``. ``confidence`` is the top-two margin scaled
    by that provenance, so a results-only route never reads as falsely certain. A low-confidence /
    results-attributed figure is exactly where the optional, gated AI-verify tier (paid) adds
    accuracy on tricky journal layouts — it is never required for the deterministic map to render."""

    figure: str
    candidates: list[RoutingCandidate] = Field(default_factory=list)
    top: str | None = None
    in_scope: bool = True
    reason: str = ""        # the oos reason when out-of-scope (atac/spatial/grn/wet_lab)
    confidence: float = 0.0
    attribution: str = "none"   # legend | results | none  — WHERE the evidence came from
    tier: str = "structured"    # structured (L1) | recovered (L2/relaxed) — HOW reliably
    ai: RouteVerdict | None = None  # optional L4 AI adjudication (fast-follow #2); None = deterministic only


class FeasibilityMap(BaseModel):
    """The Skill Keyword Index's output for a paper — the auto-generated Dorgau-style table.

    ``skills`` + ``out_of_scope`` are the **L3 paper-level inventory** (the core deliverable: every
    skill the paper needs + the out-of-scope modalities it touches), derived from ``paper_targets``
    and robust to per-figure attribution error. ``figures`` is the per-figure attribution (L1/L2 —
    the premium gravy, each carrying a ``tier``/``confidence``). ``tier_summary`` rolls up how many
    figures routed cleanly vs needed recovery — the signal a surface uses to offer the L4 AI upsell.
    ``unmatched_terms`` are method-nouns that routed to NO skill (the Skill Foundry gap signal)."""

    paper_id: str = ""
    skills: list[str] = Field(default_factory=list)         # in-scope skill ids (L3 inventory)
    out_of_scope: list[str] = Field(default_factory=list)   # oos reasons present (atac/spatial/…)
    figures: list[FigureRoute] = Field(default_factory=list)
    paper_targets: list[RoutingCandidate] = Field(default_factory=list)
    tier_summary: dict[str, int] = Field(default_factory=dict)
    unmatched_terms: list[str] = Field(default_factory=list)
    # mined synonym proposals (fast-follow #2) — surfaced for review, never auto-written to the moat.
    synonym_candidates: list[SynonymCandidate] = Field(default_factory=list)
