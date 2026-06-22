"""Skill-gap signal (skill_gaps.py, Slice 3 / R5) — the idempotent docs/skill-gaps.md updater.

Pure projection over constructed DiagnosticReports (no PDF / no stack), so these are fast and
deterministic. The load-bearing properties (D4 + the testing strategy): only *buildable* gaps are
counted (not data-availability gaps), re-running a paper never double-counts, gaps accumulate +
rank across separate invocations, and the hand-authored curated region is never clobbered.
"""

from __future__ import annotations

import skill_gaps
from reproduction import MODALITY_UNSUPPORTED, WET_LAB
from reproduction_diagnose import DiagnosticPanel, DiagnosticReport
from reproduction_drive import (
    DATA_UNMATCHED,
    DRIVEN,
    NEEDS_RECIPE,
    NO_GOLDEN,
    NO_SKILL,
    OUT_OF_SCOPE,
    RUN_FAILED,
)


def _p(key, status, **kw):
    return DiagnosticPanel(panel_key=key, status=status, **kw)


def _report(paper_id, panels):
    return DiagnosticReport(paper_id=paper_id, panels=panels)


# --- the classifier: only buildable gaps count -------------------------------


def test_extracts_only_buildable_gaps():
    rep = _report("paperA", [
        _p("1", DRIVEN, skill_id="volcano"),                       # success → no gap
        _p("2", NO_GOLDEN, skill_id="umap_scrna"),                 # no printed number → not a skill gap
        _p("3", DATA_UNMATCHED, skill_id="integration"),           # data side (Slice 2/5) → not here
        _p("4", RUN_FAILED, skill_id="trajectory"),                # data/recipe mismatch → not here
        _p("5", OUT_OF_SCOPE, scope=WET_LAB),                      # wet-lab dead-end → not a skill gap
        _p("6", NEEDS_RECIPE, skill_id="gsea", reason="no layer read: nes"),  # read_back gap ✓
        _p("7", NO_SKILL, figure="7"),                             # routing gap ✓
        _p("8", OUT_OF_SCOPE, scope=MODALITY_UNSUPPORTED, figure="8"),        # modality gap ✓
    ])
    kinds = {g.kind for g in skill_gaps.gaps_in_report(rep)}
    assert kinds == {skill_gaps.READ_BACK, skill_gaps.ROUTING, skill_gaps.MODALITY}
    keys = {g.key for g in skill_gaps.gaps_in_report(rep)}
    assert keys == {"read-back:gsea", "routing:unrouted-figure", "modality:unsupported"}


# --- the doc: scaffold, rank, machine round-trip -----------------------------


def test_scaffolds_doc_and_ranks_by_paper_count(tmp_path):
    doc = tmp_path / "skill-gaps.md"
    a = _report("paperA", [_p("1", NEEDS_RECIPE, skill_id="gsea", reason="no layer read: nes"),
                           _p("2", NO_SKILL, figure="2")])
    b = _report("paperB", [_p("1", NEEDS_RECIPE, skill_id="gsea", reason="no layer read: nes")])
    text = skill_gaps.update_skill_gaps_doc([a, b], doc)

    assert skill_gaps._AUTO_START in text and skill_gaps._AUTO_END in text
    assert "Curated capability gaps" in text                       # the scaffolded curated section
    # gsea read-back hit by BOTH papers → ranked first (2 papers) above the routing gap (1 paper).
    assert text.index("gsea") < text.index("routed to no skill")
    assert "(paperA, paperB)" in text and "Dogfooded papers: 2" in text


def test_rerunning_same_paper_does_not_double_count(tmp_path):
    doc = tmp_path / "skill-gaps.md"
    a = _report("paperA", [_p("1", NEEDS_RECIPE, skill_id="gsea", reason="no layer read: nes")])
    first = skill_gaps.update_skill_gaps_doc(a, doc)
    second = skill_gaps.update_skill_gaps_doc(a, doc)            # same paper, again
    assert first == second                                       # byte-identical → idempotent
    gaps, seen = skill_gaps._parse_existing(second)
    assert seen == ["paperA"]                                    # not [paperA, paperA]
    assert gaps["read-back:gsea"].n_papers == 1
    assert len(gaps["read-back:gsea"].examples) == 1             # example not duplicated


def test_accumulates_across_separate_invocations(tmp_path):
    doc = tmp_path / "skill-gaps.md"
    skill_gaps.update_skill_gaps_doc(
        _report("paperA", [_p("1", NEEDS_RECIPE, skill_id="gsea", reason="r")]), doc)
    # a later session dogfoods a second paper hitting the SAME gap → count rises to 2.
    text = skill_gaps.update_skill_gaps_doc(
        _report("paperB", [_p("1", NEEDS_RECIPE, skill_id="gsea", reason="r")]), doc)
    gaps, seen = skill_gaps._parse_existing(text)
    assert sorted(seen) == ["paperA", "paperB"]
    assert gaps["read-back:gsea"].n_papers == 2


def test_curated_region_is_preserved(tmp_path):
    doc = tmp_path / "skill-gaps.md"
    skill_gaps.update_skill_gaps_doc(
        _report("paperA", [_p("1", NEEDS_RECIPE, skill_id="gsea", reason="r")]), doc)
    # a hand-authored curated note above the markers must survive a re-run.
    raw = doc.read_text(encoding="utf-8")
    raw = raw.replace(skill_gaps._AUTO_START,
                      "- **Mixing metrics (LISI/kBET)** — Harmony.\n\n" + skill_gaps._AUTO_START, 1)
    doc.write_text(raw, encoding="utf-8")
    text = skill_gaps.update_skill_gaps_doc(
        _report("paperB", [_p("1", NEEDS_RECIPE, skill_id="gsea", reason="r")]), doc)
    assert "Mixing metrics (LISI/kBET)" in text                  # curated content untouched
    assert skill_gaps._parse_existing(text)[0]["read-back:gsea"].n_papers == 2


def test_no_buildable_gaps_reports_data_availability(tmp_path):
    # A paper whose only misses are data-availability still counts as dogfooded, with an honest
    # "no skill gaps, the constraint was data" message (the Harmony/Yoshimura reality).
    doc = tmp_path / "skill-gaps.md"
    rep = _report("paperA", [_p("1", DATA_UNMATCHED, skill_id="umap_scrna"),
                             _p("2", NO_GOLDEN, skill_id="integration")])
    text = skill_gaps.update_skill_gaps_doc(rep, doc)
    assert "No buildable skill gaps surfaced yet" in text and "data-availability" in text
    _, seen = skill_gaps._parse_existing(text)
    assert seen == ["paperA"]                                    # the paper is still recorded
