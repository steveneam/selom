"""Routing orchestration — produce the per-figure feasibility map (spec §Design).

Matches the vocabulary over each weighted section (methods 1.0 > legend 0.8 > results 0.6 >
body 0.3; refs excluded), attaches legend hits to their figure and results hits to the nearest
cited ``Fig N``, then rolls up: a per-figure route (top target + in-scope + confidence), a
paper-level target inventory, and the method-nouns that routed to no skill (the Skill Foundry
gap signal, surfaced — not auto-filed — in v1).
"""

from __future__ import annotations

import re

from .index import KeywordIndex, flatten
from .models import (
    FeasibilityMap,
    FigureRoute,
    RoutingCandidate,
    RoutingHit,
    is_skill,
    oos_reason,
)
from .segment import segment
from .vocab import build_vocab

# section -> weight. refs are never matched (the bibliography false-positive guard).
_SECTION_WEIGHT = {"methods": 1.0, "legend": 0.8, "results": 0.6, "body": 0.3}

_FIG_REF = re.compile(r"Fig(?:ure)?\.?\s*(\d+)", re.I)

_index_cache: KeywordIndex | None = None

# known method-nouns whose presence we don't treat as a skill gap (sub-steps of routed
# skills / general frameworks) — keeps the surfaced unmatched list meaningful.
_COVERED_FRAMEWORKS = {
    "seurat", "scanpy", "sctransform", "toptable", "lmfit", "ebayes", "glm-pca",
    "leiden", "louvain", "cellranger",
}


def default_index() -> KeywordIndex:
    """The process-wide index built from the live registry + curated synonyms (built once)."""
    global _index_cache
    if _index_cache is None:
        _index_cache = KeywordIndex(build_vocab())
    return _index_cache


def _figure_in_window(flat: str, start: int) -> str:
    """The nearest ``Fig N`` cited just before a results hit (best-effort per-figure attribution)."""
    refs = list(_FIG_REF.finditer(flat[max(0, start - 160):start]))
    return refs[-1].group(1) if refs else ""


def _aggregate(hits: list[RoutingHit]) -> list[RoutingCandidate]:
    """Group hits by target, sum weights, keep the evidence — ranked high→low."""
    by_target: dict[str, RoutingCandidate] = {}
    for h in hits:
        c = by_target.get(h.target)
        if c is None:
            by_target[h.target] = RoutingCandidate(target=h.target, score=h.weight, evidence=[h])
        else:
            c.score += h.weight
            c.evidence.append(h)
    return sorted(by_target.values(), key=lambda c: c.score, reverse=True)


def _figure_route(figure: str, hits: list[RoutingHit]) -> FigureRoute:
    cands = _aggregate(hits)
    top = cands[0] if cands else None
    second = cands[1].score if len(cands) > 1 else 0.0
    conf = round((top.score - second) / top.score, 3) if top and top.score else 0.0
    return FigureRoute(
        figure=figure,
        candidates=cands,
        top=top.target if top else None,
        in_scope=bool(top and is_skill(top.target)),
        reason=oos_reason(top.target) if top else "",
        confidence=conf,
    )


def _match_section(index: KeywordIndex, text: str, section: str, *, figure: str = "",
                   attribute_figure: bool = False) -> list[RoutingHit]:
    flat = flatten(text)
    weight = _SECTION_WEIGHT[section]
    out: list[RoutingHit] = []
    for term, target, w, start in index.find_in(flat):
        fig = _figure_in_window(flat, start) if attribute_figure else figure
        out.append(RoutingHit(term=term, target=target, section=section,
                              weight=round(weight * w, 4), figure=fig))
    return out


def _unmatched_terms(methods_flat: str, index: KeywordIndex) -> list[str]:
    """Known method-nouns present in the methods but routed to no target — the skill-gap signal.
    Filtered to genuinely-unrouted nouns (covered frameworks/sub-steps excluded)."""
    from extract.golden import _TOOLS  # the established method-noun lexicon

    vocab_terms = set(index._targets)  # normalized terms the index knows
    low = methods_flat.lower()
    gaps: list[str] = []
    for tool in _TOOLS:
        t = tool.lower()
        if t in vocab_terms or t in _COVERED_FRAMEWORKS:
            continue
        if re.search(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", low):
            gaps.append(tool)
    return sorted(set(gaps))


def route_text(text: str, *, paper_id: str = "", index: KeywordIndex | None = None) -> FeasibilityMap:
    """Route a paper's text → its :class:`FeasibilityMap` (the auto-generated feasibility table)."""
    index = index or default_index()
    seg = segment(text)

    hits: list[RoutingHit] = []
    hits += _match_section(index, seg.methods, "methods")
    hits += _match_section(index, seg.body, "body")
    hits += _match_section(index, seg.results, "results", attribute_figure=True)
    for fig, caption in seg.legends.items():
        hits += _match_section(index, caption, "legend", figure=fig)

    paper_targets = _aggregate(hits)

    figs = {h.figure for h in hits if h.figure}
    figures = [_figure_route(f, [h for h in hits if h.figure == f])
               for f in sorted(figs, key=lambda f: (len(f), f))]

    unmatched = _unmatched_terms(flatten(seg.methods), index)
    return FeasibilityMap(paper_id=paper_id, figures=figures,
                          paper_targets=paper_targets, unmatched_terms=unmatched)
