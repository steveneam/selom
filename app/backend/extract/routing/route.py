"""Routing orchestration — the 4-layer feasibility map (spec §Design + legend-hardening).

Matches the vocabulary over each weighted section (methods 1.0 > legend 0.8 > results 0.6 >
body 0.3; refs excluded) in two passes — **exact** (L1, structured) + **relaxed** token-canonical
(L3 recall, a damped gap-filler) — then produces two outputs with two different guarantees:

- **L3 — the paper-level skill inventory** (``skills`` / ``out_of_scope``): every skill the paper
  needs, aggregated from ALL non-reference hits. The core deliverable; robust to attribution error
  because it never depends on figure boundaries.
- **L1/L2 — per-figure attribution** (``figures``): legend-anchored where possible, results-proximity
  otherwise, each carrying a ``tier`` (structured/recovered) + a provenance-scaled ``confidence``.
  The premium gravy; the low-confidence/recovered figures are where the paid L4 AI tier adds accuracy.
"""

from __future__ import annotations

import re

from .index import KeywordIndex, canon, flatten
from .models import (
    FeasibilityMap,
    FigureRoute,
    RoutingCandidate,
    RoutingHit,
    is_skill,
    oos_reason,
    skill_id,
)
from .segment import segment
from .vocab import build_vocab

# section -> weight. refs are never matched (the bibliography false-positive guard).
_SECTION_WEIGHT = {"methods": 1.0, "legend": 0.8, "results": 0.6, "body": 0.3}
# a relaxed (token-canonical) gap-fill hit contributes less than an exact one, so it never outranks a
# structured match — it surfaces a candidate without distorting the ranking.
_RELAXED_FACTOR = 0.6

_FIG_REF = re.compile(r"(?<![A-Za-z])Fig(?:ure|\.)?\s*(\d+)", re.I)
_SENT_END = re.compile(r"[.!?]\s")

# provenance → confidence scale: a legend-anchored route is trustworthy; a results-proximity route is
# best-effort and must not read as certain (this is where the paid L4 AI tier helps).
_PROV_SCALE = {"legend": 1.0, "results": 0.6, "none": 0.3}

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


def _attribute_figure(flat: str, start: int, end: int) -> str:
    """Best-effort per-figure attribution for a results hit. Scientific prose cites the figure
    *after* the claim ("…volcano plot (Figure 4e)"), so prefer the nearest ``Fig N`` that FOLLOWS the
    term within the same sentence; fall back to the nearest preceding reference in the same sentence.
    Sentence-bounded so the neighbouring sentence's figure can't leak in (legend-hardening Fix C)."""
    fwd = flat[end:end + 200]
    msent = _SENT_END.search(fwd)
    fm = _FIG_REF.search(fwd[:msent.start()] if msent else fwd)
    if fm:
        return fm.group(1)
    back = flat[max(0, start - 200):start]
    back = _SENT_END.split(back)[-1]  # current sentence only
    refs = list(_FIG_REF.finditer(back))
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


def _figure_route(figure: str, hits: list[RoutingHit], legend_tiers: dict[str, str]) -> FigureRoute:
    cands = _aggregate(hits)
    top = cands[0] if cands else None
    second = cands[1].score if len(cands) > 1 else 0.0
    margin = (top.score - second) / top.score if top and top.score else 0.0
    # WHERE the evidence came from: a legend hit anywhere is the strongest anchor.
    sections = {h.section for h in hits}
    attribution = "legend" if "legend" in sections else ("results" if sections else "none")
    # HOW reliably: structured only if anchored to a clean numbered caption (the L1 path). A garbled
    # caption (ordinal recovery) or a results-proximity attribution is recovered. Tier reflects
    # segmentation/attribution provenance — whether the figure needed the recovery sweep — not term
    # morphology, so an inflected (relaxed) match on a clean caption stays structured.
    structured = attribution == "legend" and legend_tiers.get(figure) == "structured"
    tier = "structured" if structured else "recovered"
    conf = round(margin * _PROV_SCALE[attribution] * (1.0 if structured else 0.85), 3)
    return FigureRoute(
        figure=figure,
        candidates=cands,
        top=top.target if top else None,
        in_scope=bool(top and is_skill(top.target)),
        reason=oos_reason(top.target) if top else "",
        confidence=conf,
        attribution=attribution,
        tier=tier,
    )


def _match_section(index: KeywordIndex, text: str, section: str, *, figure: str = "",
                   attribute_figure: bool = False) -> list[RoutingHit]:
    """Match one section in two passes: exact (L1) + relaxed token-canonical (L3 recall) as a
    gap-filler that skips spans an exact hit already claimed and contributes at a damped weight."""
    flat = flatten(text)
    weight = _SECTION_WEIGHT[section]
    out: list[RoutingHit] = []
    exact_spans: list[tuple[int, int]] = []
    for term, target, w, start in index.find_in(flat):
        end = start + len(term)
        exact_spans.append((start, end))
        fig = _attribute_figure(flat, start, end) if attribute_figure else figure
        out.append(RoutingHit(term=term, target=target, section=section,
                              weight=round(weight * w, 4), figure=fig))
    for surface, target, w, start, end in index.find_relaxed(flat):
        if any(s < end and start < e for s, e in exact_spans):  # already covered by an exact hit
            continue
        fig = _attribute_figure(flat, start, end) if attribute_figure else figure
        out.append(RoutingHit(term=surface, target=target, section=section,
                              weight=round(weight * w * _RELAXED_FACTOR, 4), figure=fig, relaxed=True))
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

    # Dedupe repetition: the same skill evidenced by the same term-FORM within one (figure, section)
    # counts once — so a sub-panel term repeated in a caption can't dominate the ranking — while
    # distinct synonyms (edgeR + DESeq2 → deg) and cross-section mentions still reinforce. Keyed on the
    # canonical term so "heat map" / "Heat maps" / "heatmap" collapse to one (owner: dedupes/repetition).
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[RoutingHit] = []
    for h in hits:
        key = (h.figure, h.section, h.target, canon(h.term))
        if key not in seen:
            seen.add(key)
            deduped.append(h)
    hits = deduped

    # L3 — the paper-level skill inventory (the core deliverable): every distinct target across all
    # non-reference hits, ranked by evidence. Robust to per-figure attribution error.
    paper_targets = _aggregate(hits)
    skills = [skill_id(c.target) for c in paper_targets if is_skill(c.target)]
    out_of_scope = sorted({oos_reason(c.target) for c in paper_targets if not is_skill(c.target)})

    # L1/L2 — per-figure attribution (the gravy), each tier-tagged.
    figs = {h.figure for h in hits if h.figure}
    figures = [_figure_route(f, [h for h in hits if h.figure == f], seg.legend_tiers)
               for f in sorted(figs, key=lambda f: (len(f), f))]
    tier_summary = {
        "structured": sum(1 for fr in figures if fr.tier == "structured"),
        "recovered": sum(1 for fr in figures if fr.tier == "recovered"),
    }

    unmatched = _unmatched_terms(flatten(seg.methods), index)
    return FeasibilityMap(
        paper_id=paper_id, skills=skills, out_of_scope=out_of_scope, figures=figures,
        paper_targets=paper_targets, tier_summary=tier_summary, unmatched_terms=unmatched,
    )
