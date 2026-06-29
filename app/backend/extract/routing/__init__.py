"""Skill Keyword Index — deterministic keyword -> skill/modality routing for dropped papers.

Turns a paper's method-nouns / chart-forms / modality signals into a per-figure
feasibility map (the Dorgau-style table, produced by hand today): each figure routes to a
Selom skill or an out-of-scope modality (+reason). No model on the critical path — an
inverted keyword index over a registry-derived + curated-synonym vocabulary, section-weighted
(methods > legends > results > body; references excluded). AI verifies + mines synonyms; it
never replaces the deterministic layer. See docs/records/skill-keyword-index/spec.md.
"""

from .engine import build_auto_ledger, route_to_panels
from .models import (
    FeasibilityMap,
    FigureRoute,
    RouteVerdict,
    RoutingCandidate,
    RoutingHit,
    SynonymCandidate,
    VocabEntry,
)
from .route import route_text
from .verify import (
    NullVerifier,
    OperatorRouteVerifier,
    RouteVerifier,
    figures_needing_review,
    mine_synonym_candidates,
    verify_map,
)
from .vocab import build_vocab

__all__ = [
    "FeasibilityMap",
    "FigureRoute",
    "NullVerifier",
    "OperatorRouteVerifier",
    "RouteVerdict",
    "RouteVerifier",
    "RoutingCandidate",
    "RoutingHit",
    "SynonymCandidate",
    "VocabEntry",
    "build_auto_ledger",
    "build_vocab",
    "figures_needing_review",
    "mine_synonym_candidates",
    "route_to_panels",
    "route_text",
    "verify_map",
]
