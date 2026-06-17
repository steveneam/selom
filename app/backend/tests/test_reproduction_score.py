"""Reproducibility Score — the graded 0–100 layer over verdict/blame/provenance.

Two axes kept SEPARATE (the design's whole point): ``reproducibility`` = "can the figure be
regenerated?" (paper+data) vs ``selom_confidence`` = "is Selom's reconstruction trustworthy?"
(our tool). A paper-irreproducible figure must score LOW reproducibility but HIGH confidence —
detecting it is a win, not a Selom failure. The two real ledgers are the rollup fixtures
(JEV ~86 Reproduced / 100 confidence; RPGRIP1 ~63 Deposit-faithful / 92 confidence, 0 defects).
"""

import reproduction as R
from reproduction import Golden, Ledger, MethodSub, OracleResult, Panel, Paper, SourceTag

import reproduction_jev as jev
import reproduction_rpgrip1 as rp1


# --- tier banding (score → named tier + heatmap color) ------------------------


def test_score_to_tier_band_boundaries():
    assert R.score_to_tier(100)[0] == R.VERIFIED
    assert R.score_to_tier(95)[0] == R.VERIFIED
    assert R.score_to_tier(94)[0] == R.REPRODUCED
    assert R.score_to_tier(80)[0] == R.REPRODUCED
    assert R.score_to_tier(79)[0] == R.RECOVERABLE
    assert R.score_to_tier(65)[0] == R.RECOVERABLE
    assert R.score_to_tier(64)[0] == R.DEPOSIT_FAITHFUL
    assert R.score_to_tier(50)[0] == R.DEPOSIT_FAITHFUL
    assert R.score_to_tier(49)[0] == R.IRREPRODUCIBLE
    assert R.score_to_tier(30)[0] == R.IRREPRODUCIBLE
    assert R.score_to_tier(29)[0] == R.DISCREPANT
    assert R.score_to_tier(1)[0] == R.DISCREPANT


def test_score_to_tier_color_and_out_of_scope():
    assert R.score_to_tier(100) == (R.VERIFIED, R.TIER_COLORS[R.VERIFIED])
    assert R.score_to_tier(None) == (R.OUT_OF_SCOPE_TIER, R.TIER_COLORS[R.OUT_OF_SCOPE_TIER])


# --- per-panel scoring: one signal per panel ----------------------------------


def _scored(golden, computed, *, sub=False, oracle=None, structural=False,
            scope=R.TRANSCRIPTOMIC, sources=None, sweep=None, ints_exact=True):
    """Build a single-metric panel, validate it, and score it — one signal at a time."""
    panel = Panel(
        paper_id="p", figure="1", panel="a", scope=scope,
        method_subs=[MethodSub(paper_tool="edgeR", selom_tool="pyDESeq2")] if sub else [],
        sources=sources or [],
        golden=[Golden(metric="m", value=golden, structural_limit=structural,
                       ints_exact=ints_exact)],
    )
    oracles = {"m": oracle} if oracle else None
    val = R.validate_panel(panel, {"m": computed}, run_id="r", oracles=oracles)
    return R.score_panel(panel, val, sweep)


def test_verified_exact_no_substitution():
    ps = _scored(1133, 1133)
    assert ps.reproducibility == 100 and ps.tier == R.VERIFIED
    assert ps.selom_confidence == 100
    assert ps.attribution == R.ATTR_SELOM and ps.attribution_icon == "✓"


def test_reproduced_exact_with_substitution():
    # An exact match achieved via a substituted method reproduces the backing table → Reproduced.
    ps = _scored(447, 447, sub=True)
    assert ps.reproducibility == 92 and ps.tier == R.REPRODUCED


def test_reproduced_close_within_tolerance():
    ps = _scored(-71, -73)  # RHO −71% vs −73% → close
    assert ps.reproducibility == 84 and ps.tier == R.REPRODUCED
    assert ps.selom_confidence == 90


def test_recoverable_engine_delta():
    # fgsea (gold-standard engine) on the same ranking ≈ paper, gseapy ≪ → engine-delta.
    eng = OracleResult(tool="fgsea", ran_on=R.SELOM_INTERMEDIATE,
                       agrees_with_paper=True, agrees_with_selom=False)
    ps = _scored(119, 36, oracle=eng, sub=True)
    assert ps.reproducibility == 72 and ps.tier == R.RECOVERABLE
    assert ps.attribution == R.ATTR_ENGINE and ps.attribution_icon == "⚙"
    assert ps.selom_confidence == 70  # our shipped engine under-calls — the confidence axis carries it


def test_irreproducible_paper_side_keeps_high_confidence():
    # The headline: the figure can't be regenerated (authors' own tool misses), but Selom did its
    # job — LOW reproducibility, HIGH selom_confidence, attributed to the paper (never accusatory).
    raw = OracleResult(tool="edgeR", ran_on=R.DEPOSITED_RAW, agrees_with_paper=False)
    ps = _scored(78, 19, oracle=raw, sub=True)
    assert ps.reproducibility == 40 and ps.tier == R.IRREPRODUCIBLE
    assert ps.selom_confidence == 100
    assert ps.attribution == R.ATTR_PAPER and ps.attribution_icon == "📄"


def test_irreproducible_structural_limit():
    ps = _scored(2.0, 1.1, structural=True, ints_exact=False)
    assert ps.reproducibility == 38 and ps.tier == R.IRREPRODUCIBLE
    assert ps.attribution == R.ATTR_DATA and ps.attribution_icon == "🗄"
    assert ps.selom_confidence == 100


def test_irreproducible_upstream_delta():
    ups = OracleResult(tool="fgsea", ran_on=R.SELOM_INTERMEDIATE, agrees_with_paper=False)
    ps = _scored(52, 0, oracle=ups, sub=True)
    assert ps.reproducibility == 45 and ps.tier == R.IRREPRODUCIBLE
    assert ps.attribution == R.ATTR_DATA


def test_discrepant_selom_bug():
    # Authors' tool reproduces the paper on raw; Selom (same method, no sub) differs → real defect.
    raw = OracleResult(tool="edgeR", ran_on=R.DEPOSITED_RAW, agrees_with_paper=True)
    ps = _scored(78, 19, oracle=raw, sub=False)
    assert ps.reproducibility == 15 and ps.tier == R.DISCREPANT
    assert ps.attribution == R.ATTR_SELOM and ps.attribution_icon == "✗"


def test_out_of_scope_is_grey_and_excluded():
    ps = _scored(1, None, scope=R.WET_LAB)
    assert ps.reproducibility is None and ps.tier == R.OUT_OF_SCOPE_TIER
    assert ps.in_scope is False
    assert ps.color == R.TIER_COLORS[R.OUT_OF_SCOPE_TIER]


# --- the design's headline: deposit-faithful keeps the two axes apart ----------


def test_deposit_faithful_overlay_separates_the_two_axes():
    # JEV 4e: Selom reproduces the deposited ST6 EXACTLY (selom_confidence 100), but the published
    # figure diverges (reproducibility capped to 58, amber, attributed to a different replicate).
    ps = _scored(447, 447, sources=[SourceTag(ref="ST6", faithful=True),
                                    SourceTag(ref="Fig4e", faithful=False, note="diff replicate")])
    assert ps.reproducibility == 58 and ps.tier == R.DEPOSIT_FAITHFUL
    assert ps.selom_confidence == 100         # we nailed the deposit — that's the whole point
    assert ps.attribution == R.ATTR_PAPER and ps.attribution_icon == "📄"
    assert ps.provenance == "ST6+ Fig4e−"


def test_panel_takes_its_worst_metric():
    # universe exact (100) + signature.count paper-irreproducible (40) → the panel scores 40.
    raw = OracleResult(tool="edgeR", ran_on=R.DEPOSITED_RAW, agrees_with_paper=False)
    panel = Panel(paper_id="p", figure="5", panel="sig", method_subs=[MethodSub(
        paper_tool="edgeR", selom_tool="pyDESeq2")],
        golden=[Golden(metric="universe", value=1133, deterministic=True),
                Golden(metric="sig", value=78)])
    val = R.validate_panel(panel, {"universe": 1133, "sig": 19}, run_id="r",
                           oracles={"sig": raw})
    ps = R.score_panel(panel, val)
    assert ps.reproducibility == 40 and ps.attribution == R.ATTR_PAPER


# --- weighted rollup + coverage ------------------------------------------------


def test_weight_pulls_the_rollup_toward_the_heart_panel():
    paper = Paper(id="p", slug="p", title="P")
    heart = Panel(paper_id="p", figure="1", panel="a", weight=2.0,  # irreproducible heart
                  golden=[Golden(metric="m", value=78)])
    form = Panel(paper_id="p", figure="1", panel="b", weight=0.5,   # verified form re-plot
                 golden=[Golden(metric="n", value=50)])
    ledger = Ledger(paper=paper, panels=[heart, form])
    raw = OracleResult(tool="edgeR", ran_on=R.DEPOSITED_RAW, agrees_with_paper=False)
    ledger.validations.append(R.validate_panel(heart, {"m": 19}, run_id="r1", oracles={"m": raw}))
    ledger.validations.append(R.validate_panel(form, {"n": 50}, run_id="r2"))
    sc = R.build_scorecard(ledger)
    # weighted: (40*2 + 100*0.5) / 2.5 = 52 — the heavy irreproducible heart dominates the light form.
    assert sc.score.reproducibility == 52
    assert sc.score.n_scored == 2 and sc.score.n_in_scope == 2


# --- the two real ledgers as rollup fixtures -----------------------------------


def test_jev_rollup_reproduced_with_full_confidence():
    sc = jev.drive_captured().scorecard
    assert sc.score.reproducibility == 86 and sc.score.tier == R.REPRODUCED
    assert sc.score.selom_confidence == 100            # Selom nailed every deposit
    assert sc.score.n_scored == 7 and sc.score.n_in_scope == 7
    assert sc.score.n_out_of_scope == 4 and sc.score.n_form_only == 0
    by_key = {ps.panel_key: ps for ps in sc.panel_scores}
    assert by_key["4e"].tier == R.DEPOSIT_FAITHFUL      # the one amber panel
    assert by_key["4e"].attribution == R.ATTR_PAPER and by_key["4e"].provenance == "ST6+ Fig4e−"
    assert by_key["8a"].reproducibility is None         # data-not-deposited → grey, excluded


def test_rpgrip1_rollup_low_repro_but_zero_selom_defects():
    sc = rp1.drive_captured().scorecard
    assert sc.score.reproducibility == 63 and sc.score.tier == R.DEPOSIT_FAITHFUL
    assert sc.score.selom_confidence == 92
    assert sc.findings["selom_engine_bugs"] == 0        # the gap is paper/data-side, not ours
    assert sc.score.n_scored == 7 and sc.score.n_in_scope == 10 and sc.score.n_form_only == 3
    by_key = {ps.panel_key: ps for ps in sc.panel_scores}
    assert by_key["5sig"].tier == R.IRREPRODUCIBLE and by_key["5sig"].attribution == R.ATTR_PAPER
    assert by_key["5D"].reproducibility is None         # wet-lab → grey, excluded
    # The headline gap: reproducibility (63) well below selom_confidence (92) — the paper is hard
    # to reproduce, Selom did its job.
    assert sc.score.selom_confidence - sc.score.reproducibility >= 20
