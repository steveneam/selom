"""Live-reproduction drive — orchestrate the existing pieces into one ``reproduce()`` (umbrella step c).

Drop a paper + its supplements, get a graded two-axis scorecard. This module is **orchestration, not
new engine** (``docs/reproduction-engine/live-reproduction-spec.md`` §3-4): it composes already-built
parts —

  ingest (``extract.ingest.ingest_paper``)
    → route + extract goldens, MERGED into one drivable ledger (gap #1, ``engine.match.merge_ledger``)
    → match a data file per panel (gap #2, ``engine.match.match_data``)
    → run the matched skill + READ its golden metric back (``extract.readers``, gap #3)
    → grade what reproduced, and **honestly classify the rest**.

The JOIN/MATCH stage (gaps #1–#2) was lifted into the product-agnostic ``engine.match`` (P1 step 5,
``docs/engine-spine/spec.md`` Sec 6) so both products share it; this module keeps the orchestration +
honest classification. ``merge_ledger``/``match_data``/``tabular_paths`` remain importable from here.

The honest classification is the load-bearing part (invariants L2/L4): a panel we could not drive
because of the paper or its data (``out_of_scope`` / ``no_golden`` / ``data_unmatched`` /
``needs_recipe`` / ``run_failed``) is **greyed, excluded from the reproducibility rollup, and
contributes ZERO Selom-confidence defects** — a hard paper never reads as a Selom failure, and no
panel is silently dropped (every one gets a heatmap cell with its reason).

v1 = the deterministic **floor**: default params + single run + read-back. The parameter *sweep*
toward a golden and the AI *recipe proposal* are later increments (the floor never blocks on them).

The skill run is injected (``runner=``) so the orchestration + classification are unit-testable
without the scientific stack; the default runner executes the real skill. Library-only; no HTTP
(that is ``main.py``'s job, build-plan phase 2).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

import reproduction as R
from engine.match import match_data, merge_ledger, tabular_paths
from extract.ingest import PaperBundle, ingest_paper
from extract.readers import panel_extractor, panel_readings

# Back-compat: the JOIN/MATCH stage moved to ``engine.match`` (the spine boundary, P1 step 5).
# These names stay importable from here so existing callers/tests are unaffected.
build_merged_ledger = merge_ledger
__all_match__ = ("match_data", "merge_ledger", "tabular_paths", "build_merged_ledger")

# --- per-panel drive outcomes (honest classification) -------------------------
DRIVEN = "driven"                # ran + read ≥1 golden metric + validated → a real score
NO_GOLDEN = "no_golden"          # in scope, skill matched, but the paper printed no number to score
DATA_UNMATCHED = "data_unmatched"  # in scope, golden present, but no supplement feeds this skill
NEEDS_RECIPE = "needs_recipe"    # ran, but no layer could read the golden metric from the output
NO_SKILL = "no_skill"            # in-scope figure with no routed skill (purely-oos handled below)
RUN_FAILED = "run_failed"        # the skill raised on the matched data (data/recipe issue, not a bug)
OUT_OF_SCOPE = "out_of_scope"    # wet-lab / unsupported modality / data-not-deposited (greyed)

# Outcomes that are *honest gaps*, never a Selom defect — they get a grey, excluded heatmap cell.
_GREY = {NO_GOLDEN, DATA_UNMATCHED, NEEDS_RECIPE, NO_SKILL, RUN_FAILED, OUT_OF_SCOPE}


class PanelDrive(BaseModel):
    """The honest per-panel record of what the drive did (and didn't) — feeds the heatmap + report."""

    panel_key: str
    status: str
    skill_id: str | None = None
    data_ref: str = ""
    metrics_read: list[str] = Field(default_factory=list)
    note: str = ""


class DriveResult(BaseModel):
    """The driven ledger (same shape as ``GET /papers/{slug}``) + the per-panel drive report."""

    ledger: R.Ledger
    panel_drives: list[PanelDrive] = Field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for d in self.panel_drives:
            out[d.status] = out.get(d.status, 0) + 1
        return out


def _default_runner(skill_id: str, data_path: str, params: dict):
    """Run the real skill → (figure, table), loading the matched data through the engine ingest
    front door so reproduce() flows ``ingest -> analyze`` end-to-end like Product A (engine-spine
    spec §9 step 5). Byte-identical to the prior path: ``run_bundle_with_table`` executes from the
    bundle's path, and ``engine.ingest`` already speaks the matcher's tabular vocabulary (xlsx/csv).
    Fail-soft — a path engine.ingest can't recognize (an exotic ``data_map`` override) falls back to
    the path-based runner, so the matcher's data choice always reaches the skill. Lazy import keeps
    the orchestration import-light."""
    from skills.contract import run_bundle_with_table, run_skill_with_table

    try:
        from engine import ingest

        bundle = ingest(data_path)
    except Exception:  # noqa: BLE001 — unrecognized/unloadable here is an honest fall-back, not a bug
        return run_skill_with_table(skill_id, data_path, params)
    return run_bundle_with_table(skill_id, bundle, params)


# Gap #1 (merge routed skeleton + extracted goldens) and gap #2 (match a data file to a panel) now
# live in ``engine.match`` (``merge_ledger`` / ``match_data`` / ``tabular_paths``) — the spine's
# JOIN/MATCH stage. Imported above; this module keeps only the orchestration below.


# --- the per-panel drive ------------------------------------------------------


def drive_panel(ledger: R.Ledger, panel: R.Panel, *, tabular: list[str],
                data_map: dict[str, str] | None, runner, params: dict | None) -> PanelDrive:
    """Drive one panel: classify → (maybe run) → read → (maybe validate). Honest, never a false fail.

    Appends a ``ReproRun`` whenever the skill ran (so the FE can show the computed output even when
    there is nothing to score), and a ``Validation`` only when a golden metric was actually read."""
    key = panel.skill_id
    if panel.scope in R.OUT_OF_SCOPE_SCOPES:
        return PanelDrive(panel_key=panel.key, status=OUT_OF_SCOPE, skill_id=key,
                          note=f"out-of-scope ({panel.scope})")
    if not key:
        return PanelDrive(panel_key=panel.key, status=NO_SKILL,
                          note="in-scope figure with no routed skill")
    data_path, data_note = match_data(panel, tabular, data_map)
    if data_path is None:
        status = DATA_UNMATCHED if panel.golden else NO_GOLDEN
        return PanelDrive(panel_key=panel.key, status=status, skill_id=key, note=data_note)

    try:
        figure, table = runner(key, data_path, {**(params or {}), **panel.params})
    except Exception as exc:  # noqa: BLE001 — a data/recipe mismatch is honest, not a Selom bug
        return PanelDrive(panel_key=panel.key, status=RUN_FAILED, skill_id=key,
                          data_ref=data_path, note=f"skill raised: {exc}")

    computed = panel_extractor(panel, figure, table)
    run = R.ReproRun(id=f"{panel.key}-{len(ledger.runs) + 1}", panel_key=panel.key, skill_id=key,
                     params=panel.params, dataset_ref=data_path, figure_spec=figure, table=table,
                     computed=[R.MetricValue(metric=k, value=v) for k, v in computed.items()])
    ledger.runs.append(run)
    panel.status = "run"

    if not panel.golden:
        return PanelDrive(panel_key=panel.key, status=NO_GOLDEN, skill_id=key, data_ref=data_path,
                          note="computed (no printed number to score against)")
    if not computed:
        readings = panel_readings(panel, figure, table)
        unread = ", ".join(r.metric for r in readings if r.value is None)
        return PanelDrive(panel_key=panel.key, status=NEEDS_RECIPE, skill_id=key, data_ref=data_path,
                          note=f"ran, but no layer could read: {unread}")
    validation = R.validate_panel(panel, computed, run_id=run.id)
    ledger.validations.append(validation)
    panel.status = "validated"
    return PanelDrive(panel_key=panel.key, status=DRIVEN, skill_id=key, data_ref=data_path,
                      metrics_read=list(computed), note=data_note)


# --- honest heatmap completion (L4: no silent caps) ---------------------------


def _append_grey_cells(ledger: R.Ledger, drives: list[PanelDrive]) -> None:
    """Give every panel that was NOT validated a grey, excluded heatmap cell carrying its reason —
    so an unmatched / no-golden / out-of-scope panel is *shown* as that, never silently missing.

    Grey cells have ``reproducibility=None`` → excluded from the rollup and contributing zero to
    both axes (so the scorecard's score/coverage, already built, are unchanged)."""
    sc = ledger.scorecard
    if sc is None:
        return
    scored_keys = {ps.panel_key for ps in sc.panel_scores}
    note_by_key = {d.panel_key: d for d in drives}
    tier, color = R.score_to_tier(None)
    for panel in ledger.panels:
        if panel.key in scored_keys:
            continue
        d = note_by_key.get(panel.key)
        in_scope = panel.scope not in R.OUT_OF_SCOPE_SCOPES
        sc.panel_scores.append(R.PanelScore(
            panel_key=panel.key, reproducibility=None, selom_confidence=None, tier=tier, color=color,
            attribution=R.ATTR_DATA, in_scope=in_scope, weight=panel.weight,
            note=(d.note if d else "not driven"),
        ))


# --- the orchestration entrypoint ---------------------------------------------


def drive_bundle(bundle: PaperBundle, *, paper_id: str = "", paper: R.Paper | None = None,
                 data_map: dict[str, str] | None = None, params: dict | None = None,
                 runner=_default_runner, index=None) -> DriveResult:
    """Drive an already-ingested ``PaperBundle`` → a graded two-axis ``DriveResult``.

    The bundle-level entrypoint (``reproduce`` = ingest + this), split out so the orchestration +
    honest classification are testable with a constructed bundle + an injected ``runner``, no PDF."""
    ledger = merge_ledger(bundle, paper_id, paper=paper, index=index)
    tabular = tabular_paths(bundle)
    drives = [drive_panel(ledger, p, tabular=tabular, data_map=data_map, runner=runner,
                          params=params) for p in ledger.panels]
    ledger.scorecard = R.build_scorecard(ledger)
    _append_grey_cells(ledger, drives)
    return DriveResult(ledger=ledger, panel_drives=drives)


def reproduce(main_path: str, supplement_paths: list | None = None, *, paper_id: str = "",
              paper: R.Paper | None = None, data_map: dict[str, str] | None = None,
              params: dict | None = None, runner=_default_runner, index=None) -> DriveResult:
    """Drop a paper + supplements → a graded two-axis ``DriveResult`` (the live-reproduction floor).

    ``supplement_paths`` items are a path or a ``(path, role)`` pair (``extract.ingest`` contract).
    ``data_map`` (``{panel_key: path}``) is the per-panel data-picker override; ``runner`` is the
    injectable skill executor (defaults to the real one). Pure orchestration over the existing
    engine — see the module docstring for the pipeline."""
    bundle = ingest_paper(main_path, supplement_paths or [], paper_id=paper_id)
    return drive_bundle(bundle, paper_id=paper_id, paper=paper, data_map=data_map, params=params,
                        runner=runner, index=index)
