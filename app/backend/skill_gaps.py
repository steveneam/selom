"""Skill-gap signal (Slice 3, P3 3c) — turn each dogfooded paper's honest gaps into a durable,
ranked "Selom can't do X yet" backlog at ``docs/records/skill-gaps.md``.

Phase: *Reproduction — dogfood-ready* (``docs/records/reproduction-dogfood/spec.md`` R5 / Slice 3). The
cold-drive diagnostic already classifies every panel honestly; this module reads those classifications
and accumulates the *buildable capability gaps* across papers into a committed doc — the Ratchet
([[the-ratchet-durable-artifacts]]): the backlog must outlive the session and rank across papers, so
it lives in a file, not chat memory (D4).

**What counts as a buildable gap (vs a data gap we don't put here).** A non-driven panel is honest in
several ways, and only some are "Selom can't do X yet":

* ``needs_recipe``  → the skill ran but **no read-back layer caught the printed metric** — a real
  read-back/synthesis gap (kind ``read_back``; closes by widening ``extract/readers`` or L3).
* ``no_skill``      → an in-scope figure routed to **no skill at all** — a routing/coverage gap
  (kind ``routing``).
* ``out_of_scope`` with scope ``modality_unsupported`` → the figure's **modality is outside Selom's
  skill set** — a true capability gap (kind ``modality``).

Deliberately **not** counted as skill gaps (they are honest, but not "add a skill" signals): ``driven``
(success); ``no_golden`` (the paper printed no number, OR printed one in a metric family with no skill
— too ambiguous to auto-classify, so the high-value cases go in the *curated* section by hand);
``data_unmatched`` / ``run_failed`` (data-availability / data-recipe mismatches → Slice 2/5, the data
side, not the skill side); and ``out_of_scope`` that is ``wet_lab`` / ``data_not_deposited`` (a
microscopy or CRISPRi panel has no sequencing-skill that could ever close it — a dead-end, not a gap).

**Two regions in the doc.** The updater owns only the region between the auto markers (machine state +
a ranked table, regenerated idempotently). Everything above the start marker — the header and a
**curated** capability-gap section authored by hand from the findings notes (e.g. integration
mixing-metrics LISI/kBET, which surface as ambiguous ``no_golden`` and no heuristic can name) — is
preserved untouched.

**Idempotent (D4 / the testing strategy).** Re-running the same paper does not double-count: a gap's
``papers`` is a de-duplicated set and its examples are bounded + de-duplicated, and ``papers_seen``
accumulates across invocations. Same papers in → same doc out. Library-only; no HTTP, no network.
"""

from __future__ import annotations

import json
import pathlib
import re

from pydantic import BaseModel, Field

from reproduction import MODALITY_UNSUPPORTED
from reproduction_drive import NEEDS_RECIPE, NO_SKILL, OUT_OF_SCOPE

# --- gap kinds (the buildable axis) -------------------------------------------
READ_BACK = "read_back"    # ran, but no layer read the metric back → widen readers / L3
ROUTING = "routing"        # in-scope figure with no routed skill → routing/coverage gap
MODALITY = "modality"      # an unsupported modality/analysis → a new skill is needed

_MAX_EXAMPLES = 6          # keep the per-gap evidence bounded (and the doc readable)
_AUTO_START = "<!-- skill-gaps:auto:start -->"
_AUTO_END = "<!-- skill-gaps:auto:end -->"


class _RawGap(BaseModel):
    """One panel's contribution to the backlog (before merge/dedup)."""

    key: str            # stable, aggregatable-across-papers capability key
    kind: str           # read_back | routing | modality
    analysis: str       # human label for the missing capability
    closes_with: str    # one-line "what skill / change would close this"
    paper_id: str
    example: str        # "paper:panel — why", bounded sample


class SkillGap(BaseModel):
    """An accumulated capability gap — ranked by how many dogfooded papers hit it."""

    key: str
    kind: str
    analysis: str
    closes_with: str
    papers: list[str] = Field(default_factory=list)    # de-duplicated → idempotent
    examples: list[str] = Field(default_factory=list)  # bounded, de-duplicated

    @property
    def n_papers(self) -> int:
        return len(self.papers)


def _classify(panel, paper_id: str) -> _RawGap | None:
    """Map one diagnostic panel → a buildable gap, or ``None`` if it isn't a skill gap (see module
    docstring for which honest statuses are *not* counted here)."""
    fig = panel.figure or panel.panel_key or "?"
    if panel.status == NEEDS_RECIPE and panel.skill_id:
        return _RawGap(
            key=f"read-back:{panel.skill_id}", kind=READ_BACK, analysis=panel.skill_id,
            closes_with=f"widen extract/readers (or L3 synthesis) so `{panel.skill_id}` reads its printed metric back",
            paper_id=paper_id, example=f"{paper_id}:{panel.panel_key} — {panel.reason or 'metric unread'}")
    if panel.status == NO_SKILL:
        return _RawGap(
            key="routing:unrouted-figure", kind=ROUTING, analysis="in-scope figure routed to no skill",
            closes_with="add routing + a skill for this figure type",
            paper_id=paper_id, example=f"{paper_id}:{panel.panel_key} (fig {fig})")
    if panel.status == OUT_OF_SCOPE and panel.scope == MODALITY_UNSUPPORTED:
        return _RawGap(
            key="modality:unsupported", kind=MODALITY,
            analysis="an analysis modality Selom doesn't support",
            closes_with="add a skill for the unsupported modality",
            paper_id=paper_id, example=f"{paper_id}:{panel.panel_key} (fig {fig})")
    return None


def gaps_in_report(report) -> list[_RawGap]:
    """The buildable skill gaps a single cold-drive surfaced (the run's own gaps — duck-typed over any
    object with ``.paper_id`` + ``.panels`` of diagnostic panels)."""
    paper_id = getattr(report, "paper_id", "") or "(unnamed)"
    return [g for p in report.panels if (g := _classify(p, paper_id)) is not None]


def _merge(existing: dict[str, SkillGap], raws: list[_RawGap]) -> None:
    """Fold this run's raw gaps into the accumulated set (idempotent — paper ids + examples dedup)."""
    for r in raws:
        gap = existing.get(r.key)
        if gap is None:
            gap = SkillGap(key=r.key, kind=r.kind, analysis=r.analysis, closes_with=r.closes_with)
            existing[r.key] = gap
        else:  # keep the classification fresh (deterministic, but harmless if copy changes)
            gap.analysis, gap.closes_with = r.analysis, r.closes_with
        if r.paper_id not in gap.papers:
            gap.papers.append(r.paper_id)
        if r.example not in gap.examples and len(gap.examples) < _MAX_EXAMPLES:
            gap.examples.append(r.example)


def _parse_existing(text: str) -> tuple[dict[str, SkillGap], list[str]]:
    """Read the machine state out of the doc's auto region (gaps + papers_seen). Tolerant: a missing
    or malformed block starts fresh, never raises."""
    m = re.search(re.escape(_AUTO_START) + r"(.*?)" + re.escape(_AUTO_END), text, re.S)
    if not m:
        return {}, []
    jm = re.search(r"```json\s*(.*?)```", m.group(1), re.S)
    if not jm:
        return {}, []
    try:
        data = json.loads(jm.group(1))
    except (ValueError, TypeError):
        return {}, []
    gaps = {g.key: g for g in (SkillGap(**d) for d in data.get("gaps", []))}
    return gaps, list(data.get("papers_seen", []))


def _render_auto(gaps: dict[str, SkillGap], papers_seen: list[str]) -> str:
    """Render the auto region: a narration line, a ranked table, and the machine JSON (round-trips)."""
    ranked = sorted(gaps.values(), key=lambda g: (-g.n_papers, g.key))
    seen = ", ".join(papers_seen) or "—"
    out = [
        _AUTO_START, "",
        "## Auto-derived gaps", "",
        f"_Maintained by `skill_gaps.update_skill_gaps_doc` from the cold-drive diagnostic — don't "
        f"hand-edit between the markers. Dogfooded papers: {len(papers_seen)} ({seen}). Ranked by "
        f"how many papers hit each gap._", "",
    ]
    if not ranked:
        out += [
            "_No buildable skill gaps surfaced yet. The dogfooded papers' non-graded panels were "
            "**data-availability** gaps (data cited-not-attached, or no printed number) rather than "
            "missing analyses — see the curated section above for the qualitative gaps the statuses "
            "can't name._", "",
        ]
    else:
        cols = ["gap", "kind", "papers", "what would close it", "examples"]
        out.append("| " + " | ".join(cols) + " |")
        out.append("|" + "|".join(["---"] * len(cols)) + "|")
        for g in ranked:
            out.append("| " + " | ".join([
                g.analysis, g.kind, str(g.n_papers), g.closes_with,
                ("; ".join(g.examples) or "—").replace("|", "\\|"),
            ]) + " |")
        out.append("")
    payload = {"papers_seen": papers_seen, "gaps": [g.model_dump() for g in ranked]}
    out += ["```json", json.dumps(payload, indent=2, sort_keys=True), "```", "", _AUTO_END]
    return "\n".join(out)


_SCAFFOLD = """# Selom skill-gap backlog

> The durable "Selom can't do X yet" backlog, fed by the cold-drive reproduction diagnostic
> (`docs/records/reproduction-dogfood/spec.md`, Slice 3 / R5). Each dogfooded paper's honest non-graded
> panels accumulate here so dogfooding is a feedback engine, not just a score — the Ratchet.

## Curated capability gaps (hand-authored — the updater preserves this section)

_High-value gaps the panel statuses can't name on their own (e.g. a metric family with no skill to
compute it, which shows up only as an ambiguous `no_golden`). Add these from the findings notes._

"""


def _splice(text: str, auto_block: str) -> str:
    """Replace the auto region in ``text`` (or scaffold a fresh doc with the header + curated stub)."""
    if _AUTO_START in text and _AUTO_END in text:
        return re.sub(re.escape(_AUTO_START) + r".*?" + re.escape(_AUTO_END),
                      lambda _m: auto_block, text, count=1, flags=re.S)
    base = text if text.strip() else _SCAFFOLD
    return base.rstrip() + "\n\n" + auto_block + "\n"


def update_skill_gaps_doc(reports, path: str | pathlib.Path) -> str:
    """Accumulate the buildable skill gaps from one or more cold-drive reports into ``path``,
    idempotently. Returns the new doc text (also written to disk). ``reports`` is one report or a list.

    Re-running the same paper is a no-op on the counts (paper ids + examples de-dup); a new paper adds
    its gaps and re-ranks. The curated section above the markers is never touched."""
    reports = list(reports) if isinstance(reports, (list, tuple)) else [reports]
    p = pathlib.Path(path)
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    existing, papers_seen = _parse_existing(text)
    for rep in reports:
        pid = getattr(rep, "paper_id", "") or "(unnamed)"
        if pid not in papers_seen:
            papers_seen.append(pid)
        _merge(existing, gaps_in_report(rep))
    new_text = _splice(text, _render_auto(existing, papers_seen))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(new_text, encoding="utf-8")
    return new_text
