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

# A discrepancy that means the metric did NOT reproduce (the headline failure modes). A miss
# blamed only on DELTA_UNMEASURED (or no blame at all) still counts as a faithful reproduction —
# the value landed in band; the residual is just unattributed.
FAILURE_BLAMES = frozenset(
    {SELOM_ENGINE, ENGINE_DELTA, UPSTREAM_DELTA, PAPER_IRREPRODUCIBLE, STRUCTURAL_LIMIT, OUT_OF_SCOPE}
)

# Golden provenance (a value comes only from the PDF).
SOURCE_FIGURE = "figure"
SOURCE_LEGEND = "legend"
SOURCE_METHODS = "methods"
SOURCE_EXTRACTED = "extracted"

# Panel scope (guard 7). Some panels can't be numerically reproduced against the paper —
# either the readout isn't in the sequencing data (wet-lab) or the study's own data was never
# deposited, so a run is only a pipeline DEMO on a reference dataset (no exact data match).
TRANSCRIPTOMIC = "transcriptomic"
WET_LAB = "wet_lab"
DATA_NOT_DEPOSITED = "data_not_deposited"
# Scopes a numeric reproduction can't apply to: excluded from the denominator, blame OUT_OF_SCOPE.
OUT_OF_SCOPE_SCOPES = frozenset({WET_LAB, DATA_NOT_DEPOSITED})

# Where the oracle ran — the hinge of the blame procedure.
DEPOSITED_RAW = "deposited_raw"          # authors' full method on the deposited data
SELOM_INTERMEDIATE = "selom_intermediate"  # the right engine on Selom's upstream output

# --- Reproducibility Score (the graded 0–100 layer over verdict/blame/provenance) -------------
# Selom-unique: turns the engine's verdict + blame + provenance into one number per
# panel→figure→paper. Two axes, kept SEPARATE so a paper-irreproducible figure (a WIN to detect)
# never reads as a Selom failure: ``reproducibility`` = "can the figure be regenerated?" (a
# paper+data property, the heatmap headline); ``selom_confidence`` = "is Selom's reconstruction
# trustworthy?" (an our-tool property). They diverge exactly when the story is interesting
# (JEV 4e: reproducibility 58 — the figure differs from its deposit — but selom_confidence 100).
VERIFIED = "verified"                  # 95–100  exact from deposited data + stated method
REPRODUCED = "reproduced"              # 80–94   within tolerance / reproduces the backing table
RECOVERABLE = "recoverable"            # 65–79   matches only at an engine-recovered setting/engine
DEPOSIT_FAITHFUL = "deposit-faithful"  # 50–64   reproduces the deposit; the figure diverges (D14)
IRREPRODUCIBLE = "irreproducible"      # 30–49   authors' own data/tool can't reach it / structural
DISCREPANT = "discrepant"              # 1–29    a Selom-side defect
OUT_OF_SCOPE_TIER = "out-of-scope"     # N/A     wet-lab / data-not-deposited (grey, excluded)

# Red→green heatmap colors (Tailwind-ish hex; FE-ready for the deferred Reproduction view).
TIER_COLORS = {
    VERIFIED: "#15803d", REPRODUCED: "#22c55e", RECOVERABLE: "#84cc16",
    DEPOSIT_FAITHFUL: "#f59e0b", IRREPRODUCIBLE: "#f97316", DISCREPANT: "#ef4444",
    OUT_OF_SCOPE_TIER: "#9ca3af",
}

# Attribution chip — WHO a residual is on, so the color is never accusatory by default.
ATTR_SELOM = "selom"    # ✓ Selom-correct / ✗ Selom-side defect
ATTR_ENGINE = "engine"  # ⚙ a measured engine substitution
ATTR_PAPER = "paper"    # 📄 paper-side (irreproducible / a different replicate)
ATTR_DATA = "data"      # 🗄 data-side (structural / upstream / not deposited)


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
    # Counts/ID-sets are strict-exact (round-equal). Set False for a *continuous* metric whose
    # value happens to be integer-valued (e.g. a "2x" fold) so it uses the float tolerance bands.
    ints_exact: bool = True
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


class SourceTag(BaseModel):
    """Source provenance + transparency for a reconstructed panel (D14): which source the
    panel faithfully reproduces (``+``) vs diverges from (``−``).

    A panel rebuilt from a deposited table that differs from the published figure reads as
    ``ST6+ Fig4e−`` — honest and neutral, not accusatory. The common cause is benign (the
    figure is a different biological/experimental replicate than what was deposited); the tag
    records the provenance without editorialising about the paper."""

    ref: str               # "ST6", "Fig4e", "GSE153674", …
    faithful: bool = True  # + reproduced faithfully ; − reconstructed but diverges
    note: str = ""

    @property
    def badge(self) -> str:
        return f"{self.ref}{'+' if self.faithful else '−'}"


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


class PanelLift(BaseModel):
    """A staged X3-lifted panel image for the extract↔Reproduction bridge (★D).

    Pure presentation metadata: where the panel sits in the source PDF (``page_index``/``bbox``),
    the lift ``kind`` (vector crop vs raster extract), and the served ``thumbnail_url``. ``digitizable``
    gates the in-paper "Digitize this panel" entry — only chart panels (bar/line/scatter) can be
    traced. **This never influences the Reproducibility Score** (digitize ≠ reproduce): it carries no
    golden/computed value and the scorecard ignores it entirely."""

    page_index: int = 0
    bbox: tuple[float, float, float, float] | None = None
    kind: str = "raster"          # "vector" | "raster"
    thumbnail_url: str = ""        # served static asset, e.g. /repro-assets/hani/2B.png
    digitizable: bool = False      # only chart forms (bar/line/scatter) can be traced


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
    sources: list[SourceTag] = Field(default_factory=list)  # provenance (+/−) per source (D14)
    # Reproducibility-Score rollup weight: the figure's numeric "heart" panel (the central DE /
    # signature claim) outweighs a form re-plot of a deposited table (≈0.5). Default 1.0.
    weight: float = 1.0
    note: str = ""  # form/claim panels (no printed number) record why there's no golden here
    vector_copy_ref: str | None = None
    # ★D bridge: an optional staged thumbnail/lift for the read-only view. Purely presentational —
    # attached by the serving layer (repro_assets), never by the reproduction logic, and the
    # scorecard is byte-identical whether or not it is present (digitize ≠ reproduce).
    lift: PanelLift | None = None
    status: str = "pending"  # pending|extracted|mapped|anchored|run|validated|blocked

    @property
    def key(self) -> str:
        return f"{self.figure}{self.panel}"

    @property
    def provenance(self) -> str:
        """The rendered source-provenance badge, e.g. ``ST6+ Fig4e−`` (empty if untagged)."""
        return " ".join(t.badge for t in self.sources)

    @property
    def diverges_from(self) -> list[str]:
        """Sources this panel reconstructs but does not match (the ``−`` tags)."""
        return [t.ref for t in self.sources if not t.faithful]


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


class PanelScore(BaseModel):
    """The graded Reproducibility Score for one panel (the FE heatmap cell).

    ``reproducibility`` answers "can the figure be regenerated?" (paper+data property);
    ``selom_confidence`` answers "is Selom's reconstruction trustworthy?" (our-tool property).
    They diverge exactly when the story is interesting — JEV 4e scores reproducibility 58 (the
    figure differs from its own deposit) but selom_confidence 100 (Selom nailed the deposited
    table). The ``attribution`` chip + ``provenance`` badge keep the color from ever reading as
    accusatory."""

    panel_key: str
    reproducibility: int | None = None   # None == out of scope (grey, excluded from denominator)
    selom_confidence: int | None = None
    tier: str
    color: str
    attribution: str = ATTR_SELOM
    provenance: str = ""                 # the +/− source badge (e.g. "ST6+ Fig4e−")
    in_scope: bool = True
    weight: float = 1.0
    note: str = ""

    @property
    def attribution_icon(self) -> str:
        if self.attribution == ATTR_SELOM:
            return "✓" if (self.reproducibility or 0) >= 30 else "✗"
        return {ATTR_ENGINE: "⚙", ATTR_PAPER: "📄", ATTR_DATA: "🗄"}.get(self.attribution, "·")


class PaperScore(BaseModel):
    """The weighted rollup over a paper's in-scope scored panels + a coverage stat. Heart panels
    (the figure's central numeric claim) outweigh form re-plots via :attr:`Panel.weight`."""

    paper_id: str
    reproducibility: int | None = None
    selom_confidence: int | None = None
    tier: str
    color: str
    n_scored: int = 0
    n_in_scope: int = 0
    n_out_of_scope: int = 0
    n_form_only: int = 0
    coverage: str = ""


class Scorecard(BaseModel):
    paper_id: str
    n_panels: int = 0
    n_in_scope: int = 0
    totals_by_verdict: dict = Field(default_factory=dict)
    totals_by_blame: dict = Field(default_factory=dict)
    # Findings-first (D10): the headline "what the engine found", not buried under failures.
    findings: dict = Field(default_factory=dict)
    # Source provenance (D14): in-scope panels reconstructed faithfully from a source but
    # diverging from the published figure — surfaced transparently (e.g. "4e: ST6+ Fig4e−"),
    # never as a blame. Usually a benign different-replicate difference.
    provenance_divergences: list[str] = Field(default_factory=list)
    # Reproducibility Score (the graded 0–100 layer): per-panel cells + the weighted paper rollup.
    panel_scores: list[PanelScore] = Field(default_factory=list)
    score: PaperScore | None = None
    generated_at: str = Field(default_factory=_now)


class Paper(BaseModel):
    id: str
    slug: str
    title: str = ""
    doi: str = ""
    pdf_path: str = ""
    # The paper's primary data modality (scrna | bulk | proteomics | …), used to frame the
    # auto-generated Methods intro (lit-synth Phase D). Empty = mixed/unknown -> a neutral lead;
    # skill `omics` is a capability list, not a run modality, so this is declared, never inferred.
    modality: str = ""
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
    if scope in OUT_OF_SCOPE_SCOPES:
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
            ints_exact=gold.ints_exact,
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
    scope_of = {p.key: p.scope for p in ledger.panels}
    in_scope = sum(1 for p in ledger.panels if p.scope not in OUT_OF_SCOPE_SCOPES)
    reproduced = 0
    for val in ledger.validations:
        panel_in_scope = scope_of.get(val.panel_key) not in OUT_OF_SCOPE_SCOPES
        for r in val.results:
            by_verdict[r.verdict] = by_verdict.get(r.verdict, 0) + 1
            if r.blame:
                by_blame[r.blame] = by_blame.get(r.blame, 0) + 1
            if panel_in_scope and r.verdict in (EXACT, CLOSE) and r.blame not in FAILURE_BLAMES:
                reproduced += 1
    # Findings-first headline: discoveries, not failures — led by what Selom faithfully
    # reproduced, so a paper that DOES reproduce reads as a win (not an empty failure board).
    findings = {
        "reproduced": reproduced,
        "paper_irreproducible": by_blame.get(PAPER_IRREPRODUCIBLE, 0),
        "structural_limit": by_blame.get(STRUCTURAL_LIMIT, 0),
        "engine_delta": by_blame.get(ENGINE_DELTA, 0),
        "upstream_delta": by_blame.get(UPSTREAM_DELTA, 0),
        "selom_engine_bugs": by_blame.get(SELOM_ENGINE, 0),
    }
    # Provenance transparency (D14): in-scope panels that reconstruct a source faithfully but
    # diverge from the published figure — shown, not blamed.
    divergences = [
        f"{p.key}: {p.provenance}"
        for p in ledger.panels
        if p.scope not in OUT_OF_SCOPE_SCOPES and p.diverges_from
    ]
    # Reproducibility Score (the graded layer): one cell per validated panel + the paper rollup.
    val_by_key = {v.panel_key: v for v in ledger.validations}
    sweep_by_key: dict[str, Sweep] = {}
    for s in ledger.sweeps:
        sweep_by_key.setdefault(s.panel_key, s)  # first sweep per panel
    panel_scores = [
        score_panel(p, val_by_key[p.key], sweep_by_key.get(p.key))
        for p in ledger.panels
        if p.key in val_by_key
    ]
    return Scorecard(
        paper_id=ledger.paper.id,
        n_panels=len(ledger.panels),
        n_in_scope=in_scope,
        totals_by_verdict=by_verdict,
        totals_by_blame=by_blame,
        findings=findings,
        provenance_divergences=divergences,
        panel_scores=panel_scores,
        score=score_paper(ledger, panel_scores),
    )


# --- Reproducibility Score (graded layer over verdict/blame/provenance, Selom-unique) ----------


def score_to_tier(score: int | None) -> tuple[str, str]:
    """Map a 0–100 reproducibility score to its named tier + heatmap color (``None`` → grey)."""
    if score is None:
        return OUT_OF_SCOPE_TIER, TIER_COLORS[OUT_OF_SCOPE_TIER]
    for tier, lo in ((VERIFIED, 95), (REPRODUCED, 80), (RECOVERABLE, 65),
                     (DEPOSIT_FAITHFUL, 50), (IRREPRODUCIBLE, 30)):
        if score >= lo:
            return tier, TIER_COLORS[tier]
    return DISCREPANT, TIER_COLORS[DISCREPANT]


def _metric_score(verdict: str, blame: str | None, *, substituted: bool) -> tuple[int, int, str]:
    """One metric → ``(reproducibility, selom_confidence, attribution)``. The panel takes its
    worst-reproducibility metric (matching the panel-verdict "as good as its worst" rule).

    Blame drives the tier; the two axes split so the headline color is never accusatory:
    a paper-irreproducible or structural miss scores LOW on reproducibility but HIGH on
    selom_confidence (Selom did its job — the gap is the paper's or the data's)."""
    if blame == SELOM_ENGINE:
        return 15, 15, ATTR_SELOM        # Discrepant — a genuine Selom defect
    if blame == ENGINE_DELTA:
        return 72, 70, ATTR_ENGINE       # Recoverable — figure reachable with the gold-standard engine
    if blame == PAPER_IRREPRODUCIBLE:
        return 40, 100, ATTR_PAPER       # Irreproducible — authors' own tool misses too (Selom ✓)
    if blame == UPSTREAM_DELTA:
        return 45, 85, ATTR_DATA         # Irreproducible — right engine on our intermediate still misses
    if blame == STRUCTURAL_LIMIT:
        return 38, 100, ATTR_DATA        # Irreproducible — the deposit can't reach it (Selom ✓)
    # blame is None (exact) or DELTA_UNMEASURED (missed/in-band but unattributed).
    if verdict == EXACT:
        return (92 if substituted else 100), 100, ATTR_SELOM
    if verdict == CLOSE:
        return 84, 90, ATTR_SELOM
    return 50, 60, ATTR_SELOM            # FAIL with no oracle — honest uncertainty about our own value


def score_panel(panel: Panel, validation: Validation, sweep: Sweep | None = None) -> PanelScore:
    """Grade one panel 0–100 from its verdict + blame + provenance + sweep (pure).

    Out-of-scope panels (wet-lab / data-not-deposited) score ``None`` (grey, excluded from the
    denominator). Otherwise the panel takes its worst in-scope metric, then two overlays apply:
    a panel that faithfully matches its deposit but diverges from the published figure caps at
    Deposit-faithful (D14, selom_confidence stays high); a value reachable only at an
    engine-recovered unstated setting caps at Recoverable."""
    if panel.scope in OUT_OF_SCOPE_SCOPES:
        tier, color = score_to_tier(None)
        return PanelScore(panel_key=panel.key, tier=tier, color=color, attribution=ATTR_DATA,
                          provenance=panel.provenance, in_scope=False, weight=panel.weight,
                          note=f"out of scope ({panel.scope}) — excluded from the denominator")
    substituted = bool(panel.method_subs)
    scored = [_metric_score(r.verdict, r.blame, substituted=substituted)
              for r in validation.results]
    if not scored:
        tier, color = score_to_tier(None)
        return PanelScore(panel_key=panel.key, tier=tier, color=color, weight=panel.weight,
                          provenance=panel.provenance, note="no numeric target to score")
    repro, _, attribution = min(scored, key=lambda t: t[0])  # panel = its worst in-scope metric
    confidence = min(t[1] for t in scored)
    if panel.diverges_from and repro >= 50:
        repro, attribution = min(repro, 58), ATTR_PAPER       # Deposit-faithful overlay (D14)
    elif sweep is not None and sweep.reproducing_setting is not None and repro >= 80:
        repro, attribution = min(repro, 78), ATTR_ENGINE      # Recoverable overlay (unstated setting)
    tier, color = score_to_tier(repro)
    return PanelScore(panel_key=panel.key, reproducibility=repro, selom_confidence=confidence,
                      tier=tier, color=color, attribution=attribution,
                      provenance=panel.provenance, weight=panel.weight)


def score_paper(ledger: Ledger, panel_scores: list[PanelScore]) -> PaperScore:
    """Weighted rollup over in-scope scored panels + a coverage stat (heart > form via weight)."""
    scored = [ps for ps in panel_scores if ps.reproducibility is not None]
    n_in_scope = sum(1 for p in ledger.panels if p.scope not in OUT_OF_SCOPE_SCOPES)
    n_out = sum(1 for p in ledger.panels if p.scope in OUT_OF_SCOPE_SCOPES)
    n_form = sum(1 for p in ledger.panels
                 if p.scope not in OUT_OF_SCOPE_SCOPES and not p.golden)
    if scored:
        wsum = sum(ps.weight for ps in scored) or 1.0
        repro = round(sum(ps.reproducibility * ps.weight for ps in scored) / wsum)
        conf = round(sum((ps.selom_confidence or 0) * ps.weight for ps in scored) / wsum)
    else:
        repro = conf = None
    tier, color = score_to_tier(repro)
    parts = [f"{len(scored)} scored / {n_in_scope} in-scope"]
    if n_out:
        parts.append(f"{n_out} out-of-scope")
    if n_form:
        parts.append(f"{n_form} form-only")
    return PaperScore(paper_id=ledger.paper.id, reproducibility=repro, selom_confidence=conf,
                      tier=tier, color=color, n_scored=len(scored), n_in_scope=n_in_scope,
                      n_out_of_scope=n_out, n_form_only=n_form, coverage=" · ".join(parts))


def format_score(score: PaperScore | None) -> str:
    """One-line headline for a paper's Reproducibility Score."""
    if score is None or score.reproducibility is None:
        return "Reproducibility Score: N/A (no scored panels)"
    return (f"Reproducibility Score: {score.reproducibility}/100 ({score.tier}) · "
            f"Selom-confidence {score.selom_confidence}/100 · {score.coverage}")


def format_panel_scores(panel_scores: list[PanelScore]) -> list[str]:
    """Per-panel heatmap lines: ``<key>  <score>  <tier>  <attr-icon>  <provenance>``."""
    lines = []
    for ps in panel_scores:
        val = "N/A" if ps.reproducibility is None else str(ps.reproducibility)
        lines.append(f"    {ps.panel_key:5s} {val:>4}  {ps.tier:16s} "
                     f"{ps.attribution_icon} {ps.provenance}".rstrip())
    return lines


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
