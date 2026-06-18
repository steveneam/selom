"""lit-synthesizer Phase D — a reproduction Ledger -> one paper-level Methods section.

The headline tie-in of lit-synth to the reproduction engine: a driven ``reproduction.Ledger``
already records, per figure panel, the exact ``skill_id`` + resolved ``params`` Selom used. This
adapter walks those panels in figure order, drops the ones a Methods section shouldn't describe
(out-of-scope panels — wet-lab readouts, never-deposited demos — and panels with no skill),
collapses identical ``(skill_id, params)`` runs so a method stated once isn't repeated per panel,
and hands the ordered sequence to the Phase A ``compose_methods`` core. No new prose, no network.

Import direction is litsynth -> reproduction (reproduction never imports litsynth, so no cycle);
this module is intentionally NOT re-exported from ``litsynth/__init__`` so ``import litsynth`` stays
free of the heavier reproduction graph — ``main.py`` imports it explicitly.
"""

from __future__ import annotations

import json

import reproduction as R
from litsynth.models import MethodsSection, SkillRunRef
from litsynth.synth import compose_methods
from skills.contract import load_skill


def _loadable(skill_id: str) -> bool:
    # A hand-encoded ledger may name a skill that isn't an installed spec — a chart-form
    # placeholder or a not-yet-built skill (e.g. an unported "pvca" panel). Such a panel
    # has no method prose to emit, so skip it rather than crash the whole section.
    try:
        load_skill(skill_id)
        return True
    except (FileNotFoundError, OSError):
        return False


def ledger_skill_runs(ledger: R.Ledger) -> list[SkillRunRef]:
    """The ordered, deduped skill runs a Methods section should describe for this ledger.

    In figure/panel order; skips out-of-scope panels (the readout isn't in the data, or the
    study's data was never deposited so the run is only a demo), form/claim panels with no skill,
    and panels naming a skill that doesn't resolve to a spec; collapses repeats of the same
    ``(skill_id, params)`` to one entry (first-seen order).
    """
    runs: list[SkillRunRef] = []
    seen: set[str] = set()
    for panel in ledger.panels:
        if panel.skill_id is None or panel.scope in R.OUT_OF_SCOPE_SCOPES:
            continue
        if not _loadable(panel.skill_id):
            continue
        fingerprint = f"{panel.skill_id}:{json.dumps(panel.params, sort_keys=True, default=str)}"
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        runs.append(SkillRunRef(skill_id=panel.skill_id, params=panel.params))
    return runs


def dataset_descriptor(paper: R.Paper) -> str | None:
    """A one-clause dataset lead for the intro: GEO accessions if any, else the paper title."""
    if paper.geo:
        return f"Data deposited under {', '.join(paper.geo)} were analyzed"
    title = (paper.title or "").strip()
    return title or None


def compose_ledger_methods(
    ledger: R.Ledger, *, modality: str | None = None, dataset: str | None = None
) -> MethodsSection:
    """Compose ONE paper-level Methods section from a driven reproduction ledger.

    ``modality`` (an explicit override) wins over the ledger's ``paper.modality``; both empty ->
    a neutral lead (the per-skill paragraphs still carry the data-type detail). ``dataset`` likewise
    overrides the auto-derived descriptor. Raises ``ValueError`` when the ledger has no in-scope
    analysis panels (nothing to describe).
    """
    runs = ledger_skill_runs(ledger)
    if not runs:
        raise ValueError("ledger has no in-scope analysis panels to describe")
    return compose_methods(
        runs,
        modality=(modality if modality is not None else ledger.paper.modality),
        dataset=(dataset if dataset is not None else dataset_descriptor(ledger.paper)),
    )
