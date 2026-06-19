"""Bridge the Skill Keyword Index into the reproduction engine's front-half (fast-follow #1).

Turns a routed :class:`~extract.routing.models.FeasibilityMap` into the engine's
``reproduction.Panel`` / ``reproduction.Ledger`` objects, so a dropped paper auto-produces the
**panel→skill map** the four hand ledgers (``reproduction_{dorgau,hani,jev,rpgrip1}``) encode by hand.

**Figure granularity, by design.** The router resolves to a *figure* with a ranked candidate list;
it cannot know real sub-panel letters (which of 1A/1B/1C is the UMAP vs the dotplot). The engine
keys panels by ``f"{figure}{panel}"`` and takes the first match, so duplicate keys would shadow.
We therefore emit **one panel per figure** (unique key, no fabricated letters): the figure's top
in-scope skill is ``skill_id``; the full ranked in-scope suggestion set rides in ``note``; an
out-of-scope figure carries the mapped ``scope`` and no skill. The complete per-figure candidate
detail still lives on the ``FeasibilityMap`` the caller holds. The auto-map is the *skeleton* a
human (or the paid L4 AI tier) refines into sub-panels — never a claim of exact panel knowledge.
See ``docs/skill-keyword-index/engine-wiring-scope.md``.
"""

from __future__ import annotations

import reproduction as R

from .models import (
    FeasibilityMap,
    FigureRoute,
    is_skill,
    oos_reason,
    scope_of,
    skill_id,
)  # oos_reason: report a co-present out-of-scope readout on an otherwise in-scope figure
from .route import route_text


def _in_scope_skills(fr: FigureRoute) -> list[str]:
    """The figure's in-scope skill ids, ranked by evidence (candidates are pre-aggregated/unique)."""
    return [skill_id(c.target) for c in fr.candidates if is_skill(c.target)]


def _oos_reasons(fr: FigureRoute) -> list[str]:
    """The out-of-scope reasons evidenced anywhere in the figure (sorted, deduped)."""
    return sorted({oos_reason(c.target) for c in fr.candidates if not is_skill(c.target)})


def _panel_for(fr: FigureRoute, paper_id: str) -> R.Panel | None:
    """One engine ``Panel`` for a routed figure — or ``None`` when the figure has no top route.

    A figure with **any** in-scope skill candidate becomes an in-scope panel (its primary = the
    top-ranked in-scope skill), even when an out-of-scope readout out-scored it — a very common
    layout is an analysis figure with an IHC/qPCR validation sub-panel, and routing it whole to
    ``wet_lab`` would wrongly drop the reproducible skills. Such a co-present out-of-scope readout is
    noted (and stays in the paper-level inventory). Only a figure with **no** in-scope skill at all
    (purely spatial/atac/grn/wet-lab) becomes an out-of-scope panel."""
    if not fr.top:
        return None
    prov = f"tier={fr.tier}, attribution={fr.attribution}, confidence={fr.confidence}"
    in_scope = _in_scope_skills(fr)
    if in_scope:
        primary, others = in_scope[0], in_scope[1:]
        note = f"auto-routed via Skill Keyword Index: {primary}"
        if others:
            note += f" (also: {', '.join(others)})"
        oos = _oos_reasons(fr)
        if oos:
            note += f"; out-of-scope readout also present: {', '.join(oos)}"
        return R.Panel(paper_id=paper_id, figure=fr.figure, panel="", skill_id=primary,
                       scope=R.TRANSCRIPTOMIC, note=f"{note}; {prov}", status="mapped")
    # purely out-of-scope figure (no in-scope skill candidate): map the reason to the engine scope.
    note = f"auto-routed via Skill Keyword Index: out-of-scope ({fr.reason}) — no Selom skill"
    return R.Panel(paper_id=paper_id, figure=fr.figure, panel="", skill_id=None,
                   scope=scope_of(fr.top), note=f"{note}; {prov}", status="mapped")


def route_to_panels(fmap: FeasibilityMap) -> list[R.Panel]:
    """Convert a ``FeasibilityMap`` into engine ``Panel``s — the auto-ledger skeleton.

    One ``Panel`` per routed figure (figure order preserved): in-scope figures carry the top skill
    + the suggestion set in ``note``; out-of-scope figures carry the mapped ``scope``. Pure; no
    goldens (number extraction is ``extract.golden``'s job) and no network."""
    panels = [_panel_for(fr, fmap.paper_id) for fr in fmap.figures]
    return [p for p in panels if p is not None]


def build_auto_ledger(text: str, paper_id: str = "", *, paper: R.Paper | None = None,
                      index=None) -> R.Ledger:
    """Route a paper's text and wrap the result in an engine-ready ``Ledger`` skeleton.

    "Drop a paper → a ledger of figure→skill panels" in one call. The auto ``Paper`` records the L3
    inventory (``skills`` / ``out_of_scope``) in its ``methods_digest`` so the paper-level deliverable
    rides with the engine artifact. No validations/scorecard are attached — that is the driver's job
    (``build_scorecard`` runs cleanly on the skeleton; out-of-scope figures are greyed/excluded)."""
    fmap = route_text(text, paper_id=paper_id, index=index)
    pid = paper_id or "auto"
    paper = paper or R.Paper(
        id=pid, slug=pid, title="(auto-routed ledger skeleton — Skill Keyword Index)",
        methods_digest={"skills": fmap.skills, "out_of_scope": fmap.out_of_scope},
    )
    return R.Ledger(paper=paper, panels=route_to_panels(fmap))
