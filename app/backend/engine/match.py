"""Engine spine — JOIN / MATCH (the stage between INGEST and ANALYZE).

This is the spine's *table joining* stage (``docs/pillars/plan.md`` P2; ``docs/engine-spine/spec.md``
Sec 6). It does two product-agnostic jobs:

* **merge** — compose the auto-routed figure->skill skeleton with the extracted printed-number
  goldens into one drivable :class:`reproduction.Ledger` (gap #1), and
* **match** — resolve which ingested data file feeds a given panel's skill (gap #2).

It was born *inside* ``reproduction_drive.py`` as private plumbing; lifting it here makes it a named
engine stage that both products call — Product B (reproduction) drives it then grades, and Product A
(own-data) will reuse the same matcher once its data-picker lands. ``reproduction_drive`` now imports
these and keeps only the orchestration (run + read-back + grade). Behaviour is unchanged — the 4
hand ledgers + the drive tests are the regression guard (P5c).

The supplements this matcher treats as analysis *data* are exactly the kinds the engine ingest
registry can load (``.xlsx``/``.xls``/``.xlsm`` and ``.csv``) — PDFs are methods text, not data — so
the JOIN stage and ``engine.ingest`` speak one vocabulary (E5: both products call the same spine).
"""

from __future__ import annotations

import reproduction as R
from extract.golden import build_extracted_spec, to_engine_panels
from extract.ingest import SUPP_CSV, SUPP_XLSX, PaperBundle
from extract.routing.engine import route_to_panels
from extract.routing.route import route_text


# --- merge: routing skill_ids + extracted goldens -> one ledger (gap #1) ------


def _fig_sort_key(panel: R.Panel):
    """Figure order: numeric figures first (1,2,…), then any non-numeric, then panel letter."""
    fig = panel.figure
    num = int(fig) if str(fig).isdigit() else 10**6
    return (num, str(fig), panel.panel)


# A golden metric implies its skill class — and the schema inventory says DE counts read cleanly
# only from `volcano`'s de_table (not `deg`), PC variance only from `pca`, and the analyzed cell
# count only from `umap_scrna`'s plotted points. So a golden figure whose per-figure route didn't
# assign a skill is backfilled from the metric it printed.
_METRIC_SKILL = {
    "de_total": "volcano", "de_up": "volcano", "de_down": "volcano",
    "pc1_var": "pca", "pc2_var": "pca",
    "n_cells": "umap_scrna",
}


def _backfill_skill(panel: R.Panel) -> None:
    """Set a golden panel's skill from its metric when the metric has an *authoritative* source.

    This OVERRIDES the per-figure route, not just fills a blank one: DE counts read cleanly only
    from ``volcano``'s de_table (never ``deg``/``cluster`` — no direction column), and PC variance
    only from ``pca``. Real-PDF routing mis-attributes figures (the live JEV smoke routed the DE
    figures to ``cluster``), so for these specific metrics the golden's data need is a more reliable
    skill signal than the noisy route. Skills for non-mapped metrics are left to the route."""
    if not panel.golden:
        return
    for gold in panel.golden:
        sid = _METRIC_SKILL.get(gold.metric)
        if sid and panel.skill_id != sid:
            prev = panel.skill_id
            panel.skill_id = sid
            was = f" (route said {prev})" if prev else ""
            panel.note = (panel.note + "; " if panel.note else "") + \
                f"skill set to {sid} — authoritative source for golden '{gold.metric}'{was}"
            return


def merge_ledger(bundle: PaperBundle, paper_id: str, *, paper: R.Paper | None = None,
                 index=None) -> R.Ledger:
    """Compose the auto-routed figure->skill skeleton with the extracted printed-number goldens.

    Both producers exist; this is the missing composition. Figures the paper printed an extractable
    number for become **drivable golden panels** (skill_id from the route + the ``Golden``); figures
    with a matched skill but no number stay as **no-golden** skill panels; purely out-of-scope
    figures stay out-of-scope. A figure with goldens drops its bare skeleton panel so it is not
    double-counted."""
    fmap = route_text(bundle.text, paper_id=paper_id, index=index)
    spec = build_extracted_spec(bundle, paper_id)
    golden_panels = to_engine_panels(spec, feasibility=fmap)
    for p in golden_panels:
        _backfill_skill(p)
    golden_figs = {p.figure for p in golden_panels}
    skeleton = [p for p in route_to_panels(fmap) if p.figure not in golden_figs]
    panels = sorted(golden_panels + skeleton, key=_fig_sort_key)
    pid = paper_id or "auto"
    paper = paper or R.Paper(
        id=pid, slug=pid, title="(live reproduction drive)",
        methods_digest={"skills": fmap.skills, "out_of_scope": fmap.out_of_scope},
    )
    return R.Ledger(paper=paper, panels=panels)


# --- match: which data file feeds a panel (gap #2) ----------------------------


def tabular_paths(bundle: PaperBundle) -> list[str]:
    """Supplement paths that could BE the analysis data — the engine-ingestable tabular kinds
    (xlsx/csv); PDFs are methods, not data."""
    return [s.path for s in bundle.supplements if s.kind in (SUPP_XLSX, SUPP_CSV)]


def match_data(panel: R.Panel, tabular: list[str],
               data_map: dict[str, str] | None) -> tuple[str | None, str]:
    """Resolve the data file feeding this panel's skill → ``(path | None, note)``.

    v1: an explicit per-panel ``data_map`` override (the data-picker fast-follow) wins; else the
    single most-likely tabular supplement, honestly noting ambiguity when there is more than one;
    else ``None`` (the caller marks ``data_unmatched``). Deliberately conservative — better an honest
    "data not matched" than a wrong run."""
    if data_map and panel.key in data_map:
        return data_map[panel.key], "explicit data-map override"
    if not tabular:
        return None, "no tabular supplement attached"
    if len(tabular) == 1:
        return tabular[0], "single tabular supplement"
    return tabular[0], f"first of {len(tabular)} tabular supplements (ambiguous — pick per panel)"
