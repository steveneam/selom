"""Reproduction Engine — ledger, verdict, blame, scorecard, and the run+validate loop.

The automation of the manual figure-reproduction SOP (``docs/reproduction-engine/
figure-repro-sop.md``); the design is ``docs/reproduction-engine/spec.md``. This module
is the **deterministic core** (build-plan R0 + R2): the typed Reproduction Ledger, the
verdict logic + tolerances (D4), the **blame decision procedure** (D10 — the R-oracle
pattern that splits engine-delta / upstream-delta / paper-irreproducible / structural-
limit / out-of-scope), the findings-first scorecard (D10), and the headless run+validate
loop over the existing skill runners (``contract.run_skill_with_table``).

v1 is the **internal dogfood/validation tool** (D12): no HTTP surface here yet (that is
build-plan R5); the engine is driven programmatically. The 14 SOP edge-case guards live
in ``reproduction_guards.py`` (R1). Pure-Python, pydantic v2, no heavy deps — the live
skill run is the only thing that touches the scientific stack, and only when invoked.
"""

from __future__ import annotations

import math
import pathlib
from datetime import datetime, timezone

from pydantic import BaseModel, Field

# --- vocabularies (string literals; the ledger is plain JSON) -----------------

# Verdicts (SOP rule 5).
EXACT = "exact"
CLOSE = "close"
FAIL = "fail"

# Blame taxonomy (spec §Validation & Blame Assignment, D10).
SELOM_ENGINE = "selom-engine"          # Selom genuinely computed wrong — a real bug
ENGINE_DELTA = "engine-delta"          # substituted engine differs but isn't wrong (measured)
UPSTREAM_DELTA = "upstream-delta"      # an upstream-step difference propagates
PAPER_IRREPRODUCIBLE = "paper-irreproducible"  # authors' own tool misses the golden too
STRUCTURAL_LIMIT = "structural-limit"  # the deposited data cannot reach the number
OUT_OF_SCOPE = "out-of-scope"          # not derivable from the sequencing data (wet-lab)
DELTA_UNMEASURED = "delta-unmeasured"  # no oracle available to assign blame (honest fallback)

# Golden provenance (a value comes only from the PDF).
SOURCE_FIGURE = "figure"
SOURCE_LEGEND = "legend"
SOURCE_METHODS = "methods"
SOURCE_EXTRACTED = "extracted"

# Panel scope (guard 7).
TRANSCRIPTOMIC = "transcriptomic"
WET_LAB = "wet_lab"

# Where the oracle ran — the hinge of the blame procedure.
DEPOSITED_RAW = "deposited_raw"          # authors' full method on the deposited data
SELOM_INTERMEDIATE = "selom_intermediate"  # the right engine on Selom's upstream output


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- models (Pydantic; one JSON ledger per paper) -----------------------------


class Inconsistency(BaseModel):
    """A place the paper does not self-reconcile (guards 1, 2, 6)."""

    kind: str  # methods_vs_numbers | figures_vs_methods | deposit_vs_figure
    printed_in: list[str] = Field(default_factory=list)
    conflicting_value: list[str] = Field(default_factory=list)
    note: str = ""


class Golden(BaseModel):
    """A printed target value, sourced only from the PDF."""

    metric: str
    value: float | int | str
    unit: str = ""
    source: str = SOURCE_FIGURE
    confidence: float = 1.0
    note: str = ""
    inconsistency_ref: int | None = None
    # Per-metric verdict policy (D4). ints/IDs stay strict-exact; floats default to 1%.
    rel_tol: float = 0.01
    close_tol: float = 0.25
    direction_close: bool = False  # for fold-changes/abundance: sign-agreement counts as close
    # Set by the deterministic-anchor stage (SOP rule 3): a must-be-exact ID-set value.
    deterministic: bool = False
    # Set by the prepare stage / guards: the deposited data structurally can't reach this.
    structural_limit: bool = False


class MethodSub(BaseModel):
    """A recorded R→Python substitution (D5): record + MEASURE the delta, never assume."""

    paper_tool: str
    selom_tool: str
    reason: str = ""
    delta_measured: str | None = None  # None == not yet measured (guard 8 fires)


class OracleResult(BaseModel):
    """The blame instrument (dev/validation profile, ADR 0002): the authors' actual tool
    recapitulated to disambiguate engine-delta / upstream-delta / paper-irreproducible."""

    tool: str
    version: str = ""
    ran_on: str = DEPOSITED_RAW  # DEPOSITED_RAW | SELOM_INTERMEDIATE
    agrees_with_paper: bool = False
    agrees_with_selom: bool = False
    note: str = ""


class SweepCell(BaseModel):
    """One evaluated point in the sweep grid (SOP step 9)."""

    setting: dict  # e.g. {"contrast": "MS-VUS", "stat": "padj", "thr": 0.05, ...}
    value: float | int


class Sweep(BaseModel):
    """The threshold/contrast sweep for one count golden (stage 9, guard 1).

    Either pins the authors' *undocumented* setting that reproduces the printed number
    (``reproducing_setting``) or proves no grid point reaches it (``irreproducible``).
    When the printed number is not what the *stated* method yields — reachable only at an
    unstated setting, or not at all — that is the ``methods_vs_numbers`` inconsistency."""

    panel_key: str
    golden_metric: str
    golden_value: float | int
    axes: list[str] = Field(default_factory=list)
    grid: list[SweepCell] = Field(default_factory=list)
    stated_setting: dict | None = None
    stated_value: float | int | None = None
    reproducing_setting: dict | None = None
    irreproducible: bool = False
    inconsistency_ref: int | None = None
    note: str = ""


class MetricValue(BaseModel):
    metric: str
    value: float | int | str | None = None


class Panel(BaseModel):
    paper_id: str
    figure: str
    panel: str
    chart_form: str = ""
    scope: str = TRANSCRIPTOMIC
    data_source: str = ""
    skill_id: str | None = None
    params: dict = Field(default_factory=dict)
    method_subs: list[MethodSub] = Field(default_factory=list)
    golden: list[Golden] = Field(default_factory=list)
    vector_copy_ref: str | None = None
    status: str = "pending"  # pending|extracted|mapped|anchored|run|validated|blocked

    @property
    def key(self) -> str:
        return f"{self.figure}{self.panel}"


class ReproRun(BaseModel):
    id: str
    panel_key: str
    skill_id: str | None = None
    params: dict = Field(default_factory=dict)
    dataset_ref: str = ""
    computed: list[MetricValue] = Field(default_factory=list)
    figure_spec: dict | None = None
    table: dict | None = None
    provenance: dict | None = None
    methods_text: dict | None = None
    ssim: float | None = None
    ts: str = Field(default_factory=_now)


class ValidationResult(BaseModel):
    metric: str
    golden: float | int | str
    computed: float | int | str | None
    oracle: float | int | str | None = None
    delta: float | None = None  # signed relative difference (abs when golden==0)
    verdict: str
    blame: str | None = None
    note: str = ""


class Validation(BaseModel):
    run_id: str
    panel_key: str
    results: list[ValidationResult] = Field(default_factory=list)
    panel_verdict: str = FAIL
    guards_fired: list[str] = Field(default_factory=list)


class Scorecard(BaseModel):
    paper_id: str
    n_panels: int = 0
    n_in_scope: int = 0
    totals_by_verdict: dict = Field(default_factory=dict)
    totals_by_blame: dict = Field(default_factory=dict)
    # Findings-first (D10): the headline "what the engine found", not buried under failures.
    findings: dict = Field(default_factory=dict)
    generated_at: str = Field(default_factory=_now)


class Paper(BaseModel):
    id: str
    slug: str
    title: str = ""
    doi: str = ""
    pdf_path: str = ""
    geo: list[str] = Field(default_factory=list)
    methods_digest: dict = Field(default_factory=dict)
    inconsistencies: list[Inconsistency] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


class Ledger(BaseModel):
    """The per-paper source of truth (D1). The scorecard is derived from it."""

    paper: Paper
    panels: list[Panel] = Field(default_factory=list)
    runs: list[ReproRun] = Field(default_factory=list)
    oracles: list[OracleResult] = Field(default_factory=list)
    sweeps: list[Sweep] = Field(default_factory=list)
    validations: list[Validation] = Field(default_factory=list)
    scorecard: Scorecard | None = None

    def panel(self, key: str) -> Panel | None:
        return next((p for p in self.panels if p.key == key), None)


# --- verdict logic (D4) -------------------------------------------------------


def _is_int_like(v) -> bool:
    return isinstance(v, int) or (isinstance(v, float) and v.is_integer())


def _rel(golden: float, computed: float) -> float:
    """Signed relative difference; absolute difference when the golden is zero."""
    diff = computed - golden
    return diff / abs(golden) if golden != 0 else diff


def classify_metric(
    golden,
    computed,
    *,
    rel_tol: float = 0.01,
    close_tol: float = 0.25,
    ints_exact: bool = True,
    direction_close: bool = False,
) -> tuple[str, float | None]:
    """Numeric verdict for one metric → ``(verdict, signed_rel_delta)``.

    ints/IDs are strict-exact (D4); floats are exact within ``rel_tol`` (default 1%).
    A miss is ``close`` when the magnitude is within ``close_tol`` *or* (for fold-changes
    / abundances) the direction agrees; otherwise ``fail``. String goldens compare for
    equality only. Blame is assigned separately (:func:`assign_blame`).
    """
    # Non-numeric (gene name, label) — equality only.
    if isinstance(golden, str) or isinstance(computed, str):
        return (EXACT, 0.0) if golden == computed else (FAIL, None)
    if computed is None or (isinstance(computed, float) and math.isnan(computed)):
        return FAIL, None

    g, c = float(golden), float(computed)
    rel = _rel(g, c)
    mag = abs(rel)

    if ints_exact and _is_int_like(golden):
        if round(c) == round(g):
            return EXACT, 0.0
    elif mag <= rel_tol:
        return EXACT, rel

    if direction_close and g != 0 and (c > 0) == (g > 0):
        return CLOSE, rel
    if mag <= close_tol:
        return CLOSE, rel
    return FAIL, rel


# --- blame decision procedure (D10 — the R-oracle pattern) --------------------


def assign_blame(
    verdict: str,
    *,
    scope: str = TRANSCRIPTOMIC,
    structural: bool = False,
    oracle: OracleResult | None = None,
    substituted: bool = False,
) -> str | None:
    """Why a metric didn't match — the engine's differentiating output.

    Order matters: scope and structural limits are decided before the oracle (they make
    a match impossible regardless of engine). The oracle then splits the rest:

    * oracle on the **deposited raw** data that *misses the golden too* → the paper itself
      is irreproducible (the headline finding). If it *reproduces* the paper but Selom
      doesn't: a measured **engine-delta** (a substitution was applied) or a genuine
      **selom-engine** bug (same method, still wrong).
    * oracle on **Selom's intermediate** (the right engine on our upstream output) that
      still misses → the difference is **upstream**; if it hits but Selom's engine didn't
      → **engine-delta**.
    * no oracle → **delta-unmeasured** (honest; v1 internal-first always has one, D12).
    """
    if verdict == EXACT:
        return None
    if scope == WET_LAB:
        return OUT_OF_SCOPE
    if structural:
        return STRUCTURAL_LIMIT
    if oracle is None:
        return DELTA_UNMEASURED
    if oracle.ran_on == DEPOSITED_RAW:
        if not oracle.agrees_with_paper:
            return PAPER_IRREPRODUCIBLE
        return ENGINE_DELTA if substituted else SELOM_ENGINE
    # SELOM_INTERMEDIATE
    if not oracle.agrees_with_paper:
        return UPSTREAM_DELTA
    return ENGINE_DELTA if not oracle.agrees_with_selom else SELOM_ENGINE


def oracle_agreement(
    oracle_value,
    golden,
    computed,
    *,
    rel_tol: float = 0.01,
    close_tol: float = 0.25,
    ints_exact: bool = True,
    direction_close: bool = False,
) -> tuple[bool, bool]:
    """Turn an oracle's recomputed value into the two booleans :func:`assign_blame` needs.

    The oracle *agrees* with a target when re-running the authors' actual tool lands
    within that target's verdict band (``exact`` or ``close``) — reusing
    :func:`classify_metric`, not a second heuristic. ``close_tol`` is the metric's
    declared band (D4): engine-sensitive counts (GSEA term counts, RISKS #10) declare a
    wide band on their ``Golden`` so "recovers comparable counts" reads as agreement,
    while an exact count or ID-set stays strict. Returns
    ``(agrees_with_paper, agrees_with_selom)``."""

    def _agrees(target) -> bool:
        if target is None:
            return False
        verdict, _ = classify_metric(
            target,
            oracle_value,
            rel_tol=rel_tol,
            close_tol=close_tol,
            ints_exact=ints_exact,
            direction_close=direction_close,
        )
        return verdict in (EXACT, CLOSE)

    return _agrees(golden), _agrees(computed)


_VERDICT_RANK = {EXACT: 0, CLOSE: 1, FAIL: 2}


def _panel_verdict(results: list[ValidationResult]) -> str:
    """A panel is as good as its worst in-scope metric (the honest aggregate)."""
    if not results:
        return FAIL
    return max((r.verdict for r in results), key=lambda v: _VERDICT_RANK.get(v, 2))


def validate_panel(
    panel: Panel,
    computed: dict[str, float | int | str | None],
    *,
    run_id: str,
    oracles: dict[str, OracleResult] | None = None,
    guards_fired: list[str] | None = None,
) -> Validation:
    """Compare computed vs every golden on the panel → verdicts + blame.

    ``computed`` maps metric → value. Per-metric oracles disambiguate blame. Structural
    limits and scope are read from the panel/golden (set upstream by the prepare guards).
    """
    oracles = oracles or {}
    substituted = bool(panel.method_subs)
    results: list[ValidationResult] = []
    for gold in panel.golden:
        got = computed.get(gold.metric)
        verdict, delta = classify_metric(
            gold.value,
            got,
            rel_tol=gold.rel_tol,
            close_tol=gold.close_tol,
            direction_close=gold.direction_close,
        )
        oracle = oracles.get(gold.metric)
        blame = assign_blame(
            verdict,
            scope=panel.scope,
            structural=gold.structural_limit,
            oracle=oracle,
            substituted=substituted,
        )
        results.append(
            ValidationResult(
                metric=gold.metric,
                golden=gold.value,
                computed=got,
                delta=delta,
                verdict=verdict,
                blame=blame,
                note=gold.note,
            )
        )
    return Validation(
        run_id=run_id,
        panel_key=panel.key,
        results=results,
        panel_verdict=_panel_verdict(results),
        guards_fired=list(guards_fired or []),
    )


# --- scorecard (findings-first, D10) ------------------------------------------


def build_scorecard(ledger: Ledger) -> Scorecard:
    by_verdict: dict[str, int] = {EXACT: 0, CLOSE: 0, FAIL: 0}
    by_blame: dict[str, int] = {}
    in_scope = sum(1 for p in ledger.panels if p.scope != WET_LAB)
    for val in ledger.validations:
        for r in val.results:
            by_verdict[r.verdict] = by_verdict.get(r.verdict, 0) + 1
            if r.blame:
                by_blame[r.blame] = by_blame.get(r.blame, 0) + 1
    # Findings-first headline: discoveries, not failures.
    findings = {
        "paper_irreproducible": by_blame.get(PAPER_IRREPRODUCIBLE, 0),
        "structural_limit": by_blame.get(STRUCTURAL_LIMIT, 0),
        "engine_delta": by_blame.get(ENGINE_DELTA, 0),
        "upstream_delta": by_blame.get(UPSTREAM_DELTA, 0),
        "selom_engine_bugs": by_blame.get(SELOM_ENGINE, 0),
    }
    return Scorecard(
        paper_id=ledger.paper.id,
        n_panels=len(ledger.panels),
        n_in_scope=in_scope,
        totals_by_verdict=by_verdict,
        totals_by_blame=by_blame,
        findings=findings,
    )


# --- metric extraction from a skill's output ----------------------------------


def table_extractor(metric_map: dict[str, dict]):
    """Build an extractor that reads metrics out of a StatsTable (``skills/_table.py``).

    ``metric_map[metric]`` = ``{"key_col", "key", "value_col"}``: find the row whose
    ``key_col`` cell equals ``key`` and return its ``value_col`` cell. Decouples the
    panel's golden metrics from however the skill happened to lay out its table.
    """

    def extract(panel: Panel, figure: dict | None, table: dict | None) -> dict:
        out: dict = {}
        if not table:
            return out
        cols = table.get("columns", [])
        rows = table.get("rows", [])
        for metric, spec in metric_map.items():
            try:
                ki, vi = cols.index(spec["key_col"]), cols.index(spec["value_col"])
            except (ValueError, KeyError):
                continue
            for row in rows:
                if ki < len(row) and row[ki] == spec.get("key"):
                    out[metric] = row[vi] if vi < len(row) else None
                    break
        return out

    return extract


# --- the run+validate loop (R2: stages 4–6, 8) --------------------------------


def run_panel(
    ledger: Ledger,
    panel: Panel,
    data_path: str,
    *,
    filename: str | None = None,
    extractor=None,
    oracles: dict[str, OracleResult] | None = None,
    guards_fired: list[str] | None = None,
) -> tuple[ReproRun, Validation]:
    """Drive one mapped panel through run → validate → blame, appending to the ledger.

    Stages: **run** (``run_skill_with_table`` + provenance + methods) → **compute**
    (``extractor`` reads the panel's metrics from the figure/table) → **validate**
    (verdict + blame per golden). The scorecard is rebuilt. Anchor/prepare guards (the
    deterministic ID-sets and the structural checks) are run by the caller and flow in
    via ``panel.golden[*].deterministic/structural_limit`` and ``guards_fired``.
    """
    if not panel.skill_id:
        raise ValueError(f"panel {panel.key} is not mapped to a skill")

    from skills.contract import load_skill, resolved_params
    from skills.contract import run_skill_with_table

    spec = load_skill(panel.skill_id)
    figure, table = run_skill_with_table(panel.skill_id, data_path, panel.params)

    provenance_bundle = None
    methods_text = None
    try:  # best-effort; the figure is the load-bearing output
        import methods
        import provenance

        provenance_bundle = provenance.build(spec, data_path, filename, panel.params)
        methods_text = methods.build(spec, panel.params)
    except Exception:  # noqa: BLE001 — never fail a run over the prose half
        pass

    extract = extractor or (lambda p, f, t: {})
    computed = extract(panel, figure, table)

    run_id = f"{panel.key}-{len(ledger.runs) + 1}"
    run = ReproRun(
        id=run_id,
        panel_key=panel.key,
        skill_id=panel.skill_id,
        params=resolved_params(spec, panel.params),
        dataset_ref=filename or data_path,
        computed=[MetricValue(metric=k, value=v) for k, v in computed.items()],
        figure_spec=figure,
        table=table,
        provenance=provenance_bundle,
        methods_text=methods_text,
    )
    validation = validate_panel(
        panel, computed, run_id=run_id, oracles=oracles, guards_fired=guards_fired
    )

    panel.status = "validated"
    ledger.runs.append(run)
    ledger.validations.append(validation)
    ledger.scorecard = build_scorecard(ledger)
    return run, validation


def revalidate_panel(
    ledger: Ledger,
    panel: Panel,
    *,
    oracles: dict[str, OracleResult] | None = None,
    guards_fired: list[str] | None = None,
) -> Validation:
    """Re-run validate+blame for a panel after a sweep/oracle lands (stages 7/9).

    Pulls the panel's latest run's computed values, replaces the panel's prior
    ``Validation`` in place, and rebuilds the scorecard — so blame upgrades from
    ``delta-unmeasured`` to the oracle-assigned class once the instrument has run.
    ``guards_fired`` defaults to the prior validation's (pass the union to add the
    oracle/sweep-stage guards, e.g. ``authors_tool_misses``)."""
    run = next((r for r in reversed(ledger.runs) if r.panel_key == panel.key), None)
    if run is None:
        raise ValueError(f"panel {panel.key} has no run to revalidate")
    computed = {mv.metric: mv.value for mv in run.computed}
    prior = next((v for v in ledger.validations if v.panel_key == panel.key), None)
    fired = list(guards_fired) if guards_fired is not None else (prior.guards_fired if prior else [])
    new_val = validate_panel(panel, computed, run_id=run.id, oracles=oracles, guards_fired=fired)
    ledger.validations = [v for v in ledger.validations if v.panel_key != panel.key]
    ledger.validations.append(new_val)
    ledger.scorecard = build_scorecard(ledger)
    return new_val


# --- persistence (D1/D2: typed JSON per paper) --------------------------------


def _default_root() -> pathlib.Path:
    from config import settings

    return settings.data_dir / "repro"


def save_ledger(ledger: Ledger, root: pathlib.Path | str | None = None) -> pathlib.Path:
    base = pathlib.Path(root) if root is not None else _default_root()
    paper_dir = base / ledger.paper.slug
    paper_dir.mkdir(parents=True, exist_ok=True)
    path = paper_dir / "ledger.json"
    path.write_text(ledger.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_ledger(slug: str, root: pathlib.Path | str | None = None) -> Ledger:
    base = pathlib.Path(root) if root is not None else _default_root()
    path = base / slug / "ledger.json"
    return Ledger.model_validate_json(path.read_text(encoding="utf-8"))
