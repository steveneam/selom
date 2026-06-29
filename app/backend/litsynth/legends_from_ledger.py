"""lit-synthesizer — a reproduction Ledger -> one paste-ready figure legend per panel.

The legend twin of ``from_ledger.compose_ledger_methods``: that one collapses the ledger into a
single Methods section; this one keeps the panels separate, emitting one captioned ``FigureLegend``
per in-scope analysis figure (a legend is per-figure, not deduped per method). Each caption is built
by the shared ``legends.build_caption`` primitive, enriched with the panel's *driven* figure + table
when the drive recorded a ``ReproRun`` for it (so a reproduced panel cites its real DE split, etc.),
and labelled "Figure <n><panel>." from the ledger's own figure numbering.

Import direction is litsynth -> reproduction (no cycle); like ``from_ledger`` this is intentionally
NOT re-exported from ``litsynth/__init__`` so ``import litsynth`` stays light — ``main.py`` imports it
explicitly.
"""

from __future__ import annotations

from companions import legends
import reproduction as R
from litsynth.models import FigureLegend
from skills.contract import load_skill


def _loadable(skill_id: str):
    # A ledger may name a chart-form placeholder or an unbuilt skill (e.g. "box"); such a panel
    # has no caption to emit, so skip it rather than crash the whole set (mirrors from_ledger).
    try:
        return load_skill(skill_id)
    except (FileNotFoundError, OSError):
        return None


def compose_ledger_legends(ledger: R.Ledger) -> list[FigureLegend]:
    """One paste-ready ``FigureLegend`` per in-scope analysis panel, in ledger (figure) order.

    Skips out-of-scope panels, form/claim panels with no skill, and panels naming a skill that
    doesn't resolve to a spec. Raises ``ValueError`` when the ledger has no panel to caption.
    """
    runs_by_key = {r.panel_key: r for r in ledger.runs}  # the driven figure/table, when present
    out: list[FigureLegend] = []
    for panel in ledger.panels:
        if panel.skill_id is None or panel.scope in R.OUT_OF_SCOPE_SCOPES:
            continue
        spec = _loadable(panel.skill_id)
        if spec is None:
            continue
        run = runs_by_key.get(panel.key)
        figure = run.figure_spec if run is not None else None
        table = run.table if run is not None else None
        caption = legends.build_caption(spec, panel.params, figure=figure, table=table)
        panel_letter = str(panel.panel or "")
        out.append(FigureLegend(
            figure=str(panel.figure), panel=panel_letter,
            label=f"Figure {panel.figure}{panel_letter}.",
            skill_id=spec.id, text=caption,
        ))
    if not out:
        raise ValueError("ledger has no in-scope analysis panels to caption")
    return out
