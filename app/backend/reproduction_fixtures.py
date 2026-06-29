"""Auto-drive regression fixtures (Slice 4) — freeze a cold drive's HONEST classification shape so
engine growth can never silently regress a real paper's win.

Phase: *Reproduction — dogfood-ready*, **Slice 4** (``docs/records/reproduction-dogfood/spec.md``, D5). The
4 hand ledgers (``test_reproduction_{rpgrip1,jev,hani,dorgau}.py``) lock the *hand-authored* target
spec; this locks the **cold ``reproduce()``** — what a never-seen paper auto-produces with no hand
ledger. The two are complementary: the hand ledger says "this is what the paper should grade to";
this says "the auto-drive keeps classifying this paper the same honest way."

**What a dogfood paper actually locks (measured, s55).** Cold-driving JEV / Hani / Dorgau drives
*zero* panels — every panel is ``no_golden`` / ``data_unmatched`` / ``run_failed`` (the binding
constraint is data-availability + extractor recall, not the engine — the Slice-0/1 strategic
insight, confirmed on the hand-ledger papers). So the "win" a fixture freezes is the **honest
classification** (every panel accounted for, 0 Selom defects, an honest status each), *plus* any
driven metric values — which are empty today but populate automatically as recall rises, with no
fixture-code change (DoD: each future paper is a copy-paste). A future engine change that silently
regressed an earlier win — a matcher that force-fed a QC table back into a misleading ``run_failed``
(undoing Slice 2's honesty), a router that dropped a panel, a reader that misread a driven metric —
flips the fixture red.

The regression contract (``diff``): same panel set · same status per panel · honesty holds
(0 Selom defects) · every metric that drove in the snapshot still drives within its golden's
**resolved tolerance band** (s46 ``resolve_tolerances`` — a measured engine delta stays green, an
out-of-band value flips red). Pure projection over a ``DriveResult`` + the s46 grader; no new engine,
no network, library-only.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

import reproduction as R
from reproduction_drive import (
    DATA_UNMATCHED,
    DRIVEN,
    NEEDS_RECIPE,
    NO_GOLDEN,
    NO_SKILL,
    OUT_OF_SCOPE,
    RUN_FAILED,
    DriveResult,
)

# The honest per-panel statuses (mirrors ``reproduction_drive``). Any status outside this set in a
# committed snapshot means the snapshot is corrupt — the characterization test guards it.
HONEST_STATUSES = frozenset({
    DRIVEN, NO_GOLDEN, DATA_UNMATCHED, NEEDS_RECIPE, NO_SKILL, RUN_FAILED, OUT_OF_SCOPE,
})


class PanelSnapshot(BaseModel):
    """One panel's frozen cold-drive outcome — the status it classified to, and the metric values it
    read back (only populated for a ``driven`` panel; empty for an honest gap)."""

    panel_key: str
    status: str
    skill_id: str | None = None
    metrics: dict[str, float | int | str] = Field(default_factory=dict)


class DriveSnapshot(BaseModel):
    """The frozen graded output of one cold ``reproduce()`` — the regression anchor for a paper.

    Committed as JSON under ``tests/fixtures/reproduction/<paper>.json``. Tiny + text-free (panel
    keys + statuses + skill ids + any driven numbers — no copyrighted paper text), so it is safe and
    cheap to commit and review."""

    paper_id: str
    panels: list[PanelSnapshot] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)       # status -> count (display + characterization)
    n_panels: int = 0
    n_driven: int = 0
    selom_defects: int = 0                                       # scorecard findings['selom_engine_bugs']; must stay 0
    n_accessions: int = 0                                        # datasets the paper cites (Slice 5), for context

    @property
    def statuses(self) -> dict[str, str]:
        return {p.panel_key: p.status for p in self.panels}


def snapshot(result: DriveResult, *, paper_id: str = "") -> DriveSnapshot:
    """Project a driven ``DriveResult`` → a :class:`DriveSnapshot` (pure, deterministic).

    A ``driven`` panel's metric values are read from its ``ReproRun.computed`` (the read-back goldens
    the grader scored); every other panel carries an empty ``metrics`` (an honest gap has nothing to
    reproduce numerically — only its status)."""
    runs_by_panel = {run.panel_key: run for run in result.ledger.runs}
    panels: list[PanelSnapshot] = []
    for d in result.panel_drives:
        metrics: dict[str, float | int | str] = {}
        if d.status == DRIVEN:
            run = runs_by_panel.get(d.panel_key)
            if run is not None:
                metrics = {mv.metric: mv.value for mv in run.computed if mv.value is not None}
        panels.append(PanelSnapshot(panel_key=d.panel_key, status=d.status, skill_id=d.skill_id,
                                    metrics=metrics))
    sc = result.ledger.scorecard
    defects = int(sc.findings.get("selom_engine_bugs", 0)) if sc is not None else 0
    return DriveSnapshot(
        paper_id=paper_id or result.ledger.paper.id,
        panels=panels,
        summary=dict(result.summary),
        n_panels=len(panels),
        n_driven=sum(1 for p in panels if p.status == DRIVEN),
        selom_defects=defects,
        n_accessions=len(result.accessions),
    )


def diff(expected: DriveSnapshot, actual: DriveResult) -> list[str]:
    """Human-readable reasons ``actual`` no longer reproduces ``expected`` (``[]`` == reproduces).

    The regression contract (D5): (1) the same set of panels, (2) the same status per panel,
    (3) honesty holds (0 Selom defects), and (4) every metric that drove in the snapshot still drives
    to a value within its golden's **resolved tolerance band** — graded with the exact s46 grader the
    drive uses (``classify_metric`` + ``resolve_tolerances``), so a measured engine delta inside the
    metric-type band reads as reproduced while a broken reader's out-of-band value flips red."""
    problems: list[str] = []
    got = snapshot(actual, paper_id=expected.paper_id)

    exp_keys = {p.panel_key for p in expected.panels}
    got_keys = {p.panel_key for p in got.panels}
    if exp_keys != got_keys:
        missing = sorted(exp_keys - got_keys)
        added = sorted(got_keys - exp_keys)
        problems.append(f"panel set changed: missing={missing} new={added}")

    exp_status, got_status = expected.statuses, got.statuses
    for key in sorted(exp_keys & got_keys):
        if exp_status[key] != got_status[key]:
            problems.append(f"{key}: status {exp_status[key]} -> {got_status[key]}")

    if got.selom_defects != 0:
        problems.append(f"honesty regressed: selom_defects={got.selom_defects} (must be 0)")

    # Driven metric values must still land within the band that metric is graded at.
    golden_by = {(p.key, g.metric): g for p in actual.ledger.panels for g in p.golden}
    exp_metrics = {p.panel_key: p.metrics for p in expected.panels}
    got_metrics = {p.panel_key: p.metrics for p in got.panels}
    for key in sorted(exp_keys & got_keys):
        for metric, exp_val in exp_metrics.get(key, {}).items():
            got_val = got_metrics.get(key, {}).get(metric)
            gold = golden_by.get((key, metric))
            tol = R.resolve_tolerances(gold) if gold is not None else {}
            verdict, _ = R.classify_metric(exp_val, got_val, **tol)
            if verdict == R.FAIL:
                problems.append(f"{key}.{metric}: {exp_val!r} -> {got_val!r} (out of tolerance band)")
    return problems


def assert_reproduces(expected: DriveSnapshot, actual: DriveResult) -> None:
    """Assert a fresh cold drive (``actual``) reproduces a blessed snapshot (``expected``)."""
    problems = diff(expected, actual)
    assert not problems, (
        f"cold drive of {expected.paper_id!r} no longer reproduces its blessed snapshot:\n  "
        + "\n  ".join(problems)
    )


def save_snapshot(snap: DriveSnapshot, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(snap.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return p


def load_snapshot(path: str | Path) -> DriveSnapshot:
    return DriveSnapshot.model_validate_json(Path(path).read_text(encoding="utf-8"))
