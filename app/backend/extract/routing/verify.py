"""L4 AI-verify + synonym-mining seam (fast-follow #2) — gated, optional, OFF the critical path.

AI **verifies** and **mines**; it never replaces the deterministic router. Mirrors the
``extract.classify.VisionClassifier`` / ``extract.vision.OperatorVisionGateway`` discipline: a typed
:class:`RouteVerifier` Protocol with a degrade-clean :class:`NullVerifier` default and a replayable
:class:`OperatorRouteVerifier` (Claude acting as the AI gateway for dev/dogfood —
``selom-claude-acts-as-ai-gateway``), built and tested WITHOUT a live LLM. The whole deterministic
:class:`~extract.routing.models.FeasibilityMap` is produced by ``route_text``; :func:`verify_map`
is a SEPARATE opt-in post-pass, so the free / offline / inspectable / repeatable core is never on the
AI's critical path. A live service slots in behind the same Protocol later. See
``docs/records/skill-keyword-index/ai-verify-scope.md``.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from .models import (
    FeasibilityMap,
    FigureRoute,
    RouteVerdict,
    SynonymCandidate,
    is_skill,
    oos_reason,
)
from .segment import segment

# a figure goes to the (paid) L4 verifier when it needed the recovery sweep OR routed with a thin
# top-two margin — exactly the cases the deterministic layer is least sure of (and the FE upsell).
_REVIEW_CONFIDENCE = 0.5


@runtime_checkable
class RouteVerifier(Protocol):
    """The L4 verification boundary. Returns a :class:`RouteVerdict` for one already-routed figure
    (or ``None`` to decline) — it only ever refines, never originates, a route."""

    def verify_figure(self, figure: FigureRoute) -> RouteVerdict | None: ...


class NullVerifier:
    """The always-available default — no gateway, no verdicts. :func:`verify_map` with it is a
    no-op, so the deterministic map is returned unchanged (the offline credibility guarantee)."""

    def verify_figure(self, figure: FigureRoute) -> RouteVerdict | None:
        return None


class OperatorRouteVerifier:
    """Claude-as-gateway dev/dogfood stand-in: replays operator-recorded :class:`RouteVerdict`s
    deterministically (CI-safe, like ``OperatorVisionGateway``). A figure with no recorded verdict
    returns ``None`` → the deterministic route is kept; the seam never fabricates a verdict."""

    def __init__(self, verdicts: list[RouteVerdict] | dict[str, RouteVerdict] | None = None):
        items = verdicts.values() if isinstance(verdicts, dict) else (verdicts or [])
        self._verdicts = {v.figure: v for v in items}

    def record(self, verdict: RouteVerdict) -> None:
        """Add/replace a verdict (used as the operator works through a paper's flagged figures)."""
        self._verdicts[verdict.figure] = verdict

    def verify_figure(self, figure: FigureRoute) -> RouteVerdict | None:
        return self._verdicts.get(figure.figure)


def figures_needing_review(fmap: FeasibilityMap, *,
                           confidence_below: float = _REVIEW_CONFIDENCE) -> list[FigureRoute]:
    """The deterministic selector — the figures the paid L4 tier would adjudicate: recovered-tier OR
    low-confidence. Same signal as ``tier_summary``; drives the FE 'M need recovery → Pro AI' upsell."""
    return [fr for fr in fmap.figures
            if fr.tier == "recovered" or fr.confidence < confidence_below]


def verify_map(fmap: FeasibilityMap, verifier: RouteVerifier, *,
               confidence_below: float = _REVIEW_CONFIDENCE) -> FeasibilityMap:
    """Apply ``verifier`` to the FLAGGED figures only; attach each verdict to ``FigureRoute.ai`` and,
    on an ``override``, update that figure's ``top``/``in_scope``/``reason``/``confidence``. Returns a
    NEW map (pure given the verifier). A verifier that returns ``None`` (incl. :class:`NullVerifier`)
    leaves a figure untouched. The paper-level L3 inventory (``skills``/``out_of_scope``) is NOT
    recomputed — it is derived from all hits and robust to per-figure attribution, by design."""
    flagged = {fr.figure for fr in figures_needing_review(fmap, confidence_below=confidence_below)}
    new_figs: list[FigureRoute] = []
    for fr in fmap.figures:
        verdict = verifier.verify_figure(fr) if fr.figure in flagged else None
        if verdict is None:
            new_figs.append(fr)
            continue
        fr2 = fr.model_copy(deep=True)
        fr2.ai = verdict
        if verdict.verdict == "override" and verdict.target:
            fr2.top = verdict.target
            fr2.in_scope = is_skill(verdict.target)
            fr2.reason = "" if is_skill(verdict.target) else oos_reason(verdict.target)
            fr2.confidence = round(verdict.confidence, 3)
        new_figs.append(fr2)
    return fmap.model_copy(update={"figures": new_figs})


def mine_synonym_candidates(text: str, fmap: FeasibilityMap, *, index=None) -> FeasibilityMap:
    """Deterministic synonym-candidate generator: for each unmatched method-noun, the in-scope skills
    co-mentioned in the SAME methods sentence become its ``co_targets`` — a ``term → target`` proposal
    for the curated ``synonyms.json``. **Surfaced for review, never auto-written** (the moat stays
    human-curated). Offline; the L4 AI tier (or the owner) confirms the mapping. Returns a NEW map
    with ``synonym_candidates`` populated."""
    from .index import flatten
    from .route import default_index

    idx = index or default_index()
    seg = segment(text)
    flat = flatten(seg.methods)
    sentences = re.split(r"(?<=[.!?])\s+", flat)
    cands: list[SynonymCandidate] = []
    for term in fmap.unmatched_terms:
        tl = term.lower()
        co: set[str] = set()
        seen = False
        for sent in sentences:
            if tl in sent.lower():
                seen = True
                co.update(target for _, target, _, _ in idx.find_in(sent) if is_skill(target))
        if seen:
            cands.append(SynonymCandidate(
                term=term, section="methods", co_targets=sorted(co),
                note="unmatched method-noun; candidate synonym for a co-mentioned skill (review)"))
    return fmap.model_copy(update={"synonym_candidates": cands})
