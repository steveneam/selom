"""Cold-drive diagnostic — measure how much of a never-seen paper auto-grades, and why the rest doesn't.

Phase: *Reproduction — dogfood-ready*, **Slice 0** (``docs/reproduction-dogfood/spec.md``). This is
**presentation over the existing drive**, not new engine: it runs ``reproduce()`` (or projects an
already-computed :class:`reproduction_drive.DriveResult`) into a structured **gap report** — per panel
the honest status + the *reason* it didn't grade, plus a rollup and an ``auto_grade_rate``. The point
is to fix the extractor / matcher from what real papers actually do (Slice 1+), not from guesses
([[step-back-build-helpers-when-stuck]] — measure before building).

Honest by construction (it only re-reads what the drive already classified): it never invents a golden,
never turns a gap into a Selom-confidence defect, and never crashes a run (a panel that raised is
already ``run_failed`` — see ``reproduction_drive``'s honest classification). Library-only; no HTTP.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

import reproduction as R
from engine.compat import FileFitReport
from extract.accessions import Accession, AccessionReport, find_accessions
from extract.ingest import ingest_paper
from reproduction_drive import DRIVEN, DriveResult, drive_bundle

# A short, owner-readable "what would close this" per honest-gap status — the diagnostic's whole point
# is to route each gap to the slice that fixes it (``docs/reproduction-dogfood/spec.md``).
_FIX_HINT = {
    "no_golden": "extractor miss, or genuinely no printed number — widen golden extraction (Slice 1)",
    "data_unmatched": "in scope w/ a golden but no file matched — point it at its supplement (Slice 2)",
    "needs_recipe": "ran, but no read-back layer caught the metric — widen readers / L3 (Slice 1)",
    "no_skill": "in-scope figure routed to no skill — routing gap (Slice 1/3)",
    "run_failed": "skill raised on the matched data — data/recipe mismatch (Slice 2) or missing skill (Slice 3)",
    "out_of_scope": "wet-lab / unsupported modality / data not deposited — honest, no action",
}


class DiagnosticPanel(BaseModel):
    """One panel's cold-drive outcome — the drive record joined to its ledger panel."""

    panel_key: str
    figure: str = ""
    status: str
    skill_id: str | None = None
    data_ref: str = ""
    goldens_expected: list[str] = Field(default_factory=list)  # metric names the paper printed
    metrics_read: list[str] = Field(default_factory=list)      # metric names a read-back layer caught
    in_scope: bool = True
    reason: str = ""
    fix_hint: str = ""


class DiagnosticReport(BaseModel):
    """The gap report for one cold drive — a faithful projection of a ``DriveResult`` (D1).

    ``auto_grade_rate`` = driven / (in-scope panels with ≥1 printed golden); ``None`` when there are no
    gradable panels (reported as "n/a", never a divide-by-zero — R2/Error-Behavior in the spec)."""

    paper_id: str = ""
    panels: list[DiagnosticPanel] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)      # status -> count, over every panel
    n_panels: int = 0
    n_in_scope: int = 0
    n_gradable: int = 0                                        # in-scope AND ≥1 golden
    n_driven: int = 0
    auto_grade_rate: float | None = None
    accessions: list[Accession] = Field(default_factory=list)  # datasets the paper CITES (Slice 5)
    data_fits: list[FileFitReport] = Field(default_factory=list)  # dropped-data quality/fit (Slice 2)

    @property
    def data_provenance(self) -> str:
        """One honest line on the data the paper points at — the Slice-5 answer to the meta-finding
        that famous papers deposit accessions, not ingestable tables."""
        return AccessionReport(accessions=self.accessions).summary_line()

    @property
    def auto_grade_label(self) -> str:
        if self.auto_grade_rate is None:
            return "n/a (no gradable panels)"
        return f"{self.auto_grade_rate * 100:.0f}% ({self.n_driven}/{self.n_gradable})"


def diagnose(result: DriveResult, *, paper_id: str = "",
             accessions: list[Accession] | None = None,
             data_fits: list[FileFitReport] | None = None) -> DiagnosticReport:
    """Project a driven ``DriveResult`` → a :class:`DiagnosticReport` (pure, PDF-free, unit-testable).

    Iterates the authoritative per-panel drive records (1:1 with ledger panels, in the drive's sorted
    order) and joins each to its ledger panel for the printed goldens + scope. Every panel yields one
    row — no silent caps, mirroring the heatmap invariant. ``accessions`` (Slice 5) carries the
    datasets the paper *cites*; ``data_fits`` (Slice 2) carries how good/compatible each dropped
    supplement is for the run's analyses — surfaced so a ``data_unmatched`` paper shows both honest
    provenance and an honest verdict on the data the user actually attached."""
    panel_by_key = {p.key: p for p in result.ledger.panels}
    rows: list[DiagnosticPanel] = []
    for d in result.panel_drives:
        panel = panel_by_key.get(d.panel_key)
        goldens = [g.metric for g in panel.golden] if (panel and panel.golden) else []
        in_scope = bool(panel) and panel.scope not in R.OUT_OF_SCOPE_SCOPES
        rows.append(DiagnosticPanel(
            panel_key=d.panel_key,
            figure=panel.figure if panel else "",
            status=d.status,
            skill_id=d.skill_id,
            data_ref=d.data_ref,
            goldens_expected=goldens,
            metrics_read=list(d.metrics_read),
            in_scope=in_scope,
            reason=d.note,
            fix_hint=_FIX_HINT.get(d.status, ""),
        ))

    n_gradable = sum(1 for r in rows if r.in_scope and r.goldens_expected)
    n_driven = sum(1 for r in rows if r.status == DRIVEN)
    return DiagnosticReport(
        paper_id=paper_id or result.ledger.paper.id,
        panels=rows,
        summary=result.summary,
        n_panels=len(rows),
        n_in_scope=sum(1 for r in rows if r.in_scope),
        n_gradable=n_gradable,
        n_driven=n_driven,
        auto_grade_rate=(n_driven / n_gradable) if n_gradable else None,
        accessions=accessions or [],
        data_fits=(result.data_fits if data_fits is None else data_fits),
    )


def diagnose_paper(main_path: str, supplement_paths: list | None = None, *, paper_id: str = "",
                   **kw) -> DiagnosticReport:
    """Run a cold drive on a paper (no hand ledger) and return its gap report. Heavy path: it drives
    the real scientific stack. ``kw`` forwards ``data_map`` / ``runner`` / ``index`` to the drive.

    Ingests once and reuses the bundle for the drive + the accession scan (Slice 5). The dropped-data
    fit ranking (Slice 2) rides on the ``DriveResult`` (the drive already classified each supplement),
    so the gap report carries cited-dataset provenance AND an honest score on the data the user
    attached, alongside the per-panel statuses."""
    bundle = ingest_paper(main_path, supplement_paths or [], paper_id=paper_id)
    result = drive_bundle(bundle, paper_id=paper_id, **kw)
    return diagnose(result, paper_id=paper_id, accessions=find_accessions(bundle.text))


def to_markdown(report: DiagnosticReport) -> str:
    """Render the gap report as an owner-readable markdown table + rollup (the human half of D1; the
    machine half is ``report.model_dump_json()``)."""
    head = (
        f"# Cold-drive gap report — {report.paper_id or '(unnamed)'}\n\n"
        f"- **auto-grade rate:** {report.auto_grade_label}\n"
        f"- **panels:** {report.n_panels}  ·  in-scope {report.n_in_scope}  ·  "
        f"gradable (in-scope + golden) {report.n_gradable}  ·  driven {report.n_driven}\n"
        f"- **status rollup:** "
        + ", ".join(f"{k} {v}" for k, v in sorted(report.summary.items()))
        + f"\n- **cited data (Slice 5):** {report.data_provenance}\n\n"
    )
    if report.accessions:
        head += "## Cited datasets\n\n"
        acols = ["repo", "accession", "access", "fetchable", "where", "note"]
        head += "| " + " | ".join(acols) + " |\n|" + "|".join(["---"] * len(acols)) + "|\n"
        for a in report.accessions:
            head += "| " + " | ".join([
                a.label or a.repo, f"[{a.id}]({a.url})", a.access,
                "yes" if a.ingestable else "no", a.section, a.note or "—",
            ]) + " |\n"
        head += "\n"
    if report.data_fits:
        head += "## Dropped data — fit (Slice 2)\n\n"
        fcols = ["file", "kind", "quality", "best fit", "score", "confidence", "why"]
        head += "| " + " | ".join(fcols) + " |\n|" + "|".join(["---"] * len(fcols)) + "|\n"
        for ff in report.data_fits:
            best = ff.fits[0] if ff.fits else None
            head += "| " + " | ".join([
                ff.filename or "—", ff.kind, f"{ff.quality}/100",
                ff.best_skill or "—", f"{ff.score}/100", ff.confidence,
                ((best.reason if best else ff.note) or "—").replace("|", "\\|"),
            ]) + " |\n"
        head += "\n"
    cols = ["panel", "fig", "status", "skill", "data", "goldens(exp)", "read", "reason"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in report.panels:
        lines.append("| " + " | ".join([
            r.panel_key or "—",
            r.figure or "—",
            r.status + ("" if r.in_scope else " (oos)"),
            r.skill_id or "—",
            (r.data_ref.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if r.data_ref else "—"),
            ", ".join(r.goldens_expected) or "—",
            ", ".join(r.metrics_read) or "—",
            (r.reason or "").replace("|", "\\|") or "—",
        ]) + " |")
    return head + "\n".join(lines) + "\n"
