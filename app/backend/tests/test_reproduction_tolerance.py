"""Metric-type-aware tolerance grader (P5 — engine-delta ≠ irreproducible).

A ``Golden``'s tolerance band should follow its metric TYPE, not be hand-set per golden: exact
counts/ID-sets stay strict, while engine-sensitive families (GSEA term counts via gseapy↔fgsea,
integration mixing via Melody↔Harmony) are graded at a wide band so a *measured* engine
substitution isn't mislabelled as a reproduction failure. These lock the resolution rules
(``infer_metric_type`` / ``resolve_tolerances``) and that an untyped golden grades byte-identically
to before (the non-regression guarantee the 4 ledgers depend on).
"""

from __future__ import annotations

import reproduction as R
from extract.golden import to_golden
from extract.models import SOURCE_FIGURE, GoldenTarget


# --- infer_metric_type --------------------------------------------------------


def test_infer_engine_sensitive_and_strict_families():
    assert R.infer_metric_type("rod2_enriched_terms") == R.MT_GSEA_TERM_COUNT
    assert R.infer_metric_type("n_terms", skill_id="gsea") == R.MT_GSEA_TERM_COUNT
    assert R.infer_metric_type("batch_mixing") == R.MT_INTEGRATION
    assert R.infer_metric_type("ilisi", skill_id="integration") == R.MT_INTEGRATION
    for m in ("de_total", "de_up", "de_down"):
        assert R.infer_metric_type(m) == R.MT_DE_COUNT


def test_infer_unknown_metric_is_untyped():
    # Conservative: anything without a characteristic reproducibility behaviour stays untyped,
    # so typing never silently widens a metric that should be graded strictly.
    assert R.infer_metric_type("signature.count") == ""
    assert R.infer_metric_type("pc1_var") == ""
    assert R.infer_metric_type("") == ""


# --- resolve_tolerances -------------------------------------------------------


def test_untyped_golden_resolves_to_its_own_fields():
    # The non-regression contract: no metric_type → grade at the golden's own fields verbatim.
    gold = R.Golden(metric="rod2_enriched_terms", value=119, close_tol=0.30)
    tol = R.resolve_tolerances(gold)
    assert tol == {"rel_tol": 0.01, "close_tol": 0.30, "ints_exact": True, "direction_close": False}


def test_typed_golden_takes_the_family_band():
    gold = R.Golden(metric="rod2_enriched_terms", value=119, metric_type=R.MT_GSEA_TERM_COUNT)
    tol = R.resolve_tolerances(gold)
    assert tol == {"rel_tol": 0.10, "close_tol": 0.30, "ints_exact": False, "direction_close": False}


def test_explicit_tolerance_overrides_the_type_default():
    # type = default, explicit = win: a pinned close_tol beats the family band.
    gold = R.Golden(metric="rod2_enriched_terms", value=119,
                    metric_type=R.MT_GSEA_TERM_COUNT, close_tol=0.05)
    tol = R.resolve_tolerances(gold)
    assert tol["close_tol"] == 0.05            # explicit
    assert tol["rel_tol"] == 0.10              # still from the type


# --- the band actually changes the verdict (via validate_panel) ---------------


def _panel(gold: R.Golden) -> R.Panel:
    return R.Panel(paper_id="t", figure="1", panel="", skill_id="x", golden=[gold])


def _verdict(gold: R.Golden, computed) -> str:
    val = R.validate_panel(_panel(gold), {gold.metric: computed}, run_id="r")
    return val.results[0].verdict


def test_gsea_term_count_widened_band_rescues_a_near_miss():
    # paper 119, an fgsea-like 88: the default close band (0.25) FAILs it (26% off), but the
    # engine-sensitive family band (0.30) grades it CLOSE — a known engine-delta, not a failure.
    untyped = R.Golden(metric="rod2_enriched_terms", value=119)
    typed = R.Golden(metric="rod2_enriched_terms", value=119, metric_type=R.MT_GSEA_TERM_COUNT)
    assert _verdict(untyped, 88) == R.FAIL
    assert _verdict(typed, 88) == R.CLOSE


def test_integration_small_engine_delta_grades_exact():
    # Melody vs Harmony mixing 0.50 vs 0.54 (8% off): default → merely CLOSE; the integration
    # family's 10% exact band reads it as reproduced (EXACT).
    untyped = R.Golden(metric="batch_mixing", value=0.50, ints_exact=False)
    typed = R.Golden(metric="batch_mixing", value=0.50, metric_type=R.MT_INTEGRATION)
    assert _verdict(untyped, 0.54) == R.CLOSE
    assert _verdict(typed, 0.54) == R.EXACT


def test_de_count_type_stays_strict():
    # The DE-count family must NOT loosen integer exactness: 180 vs 180 exact, 180 vs 88 fails.
    typed = R.Golden(metric="de_total", value=180, metric_type=R.MT_DE_COUNT)
    assert _verdict(typed, 180) == R.EXACT
    assert _verdict(typed, 88) == R.FAIL


def test_typed_de_count_matches_untyped_de_count():
    # MT_DE_COUNT == the strict default, so tagging a DE count is a tolerance no-op (this is what
    # keeps the drive's auto-typed DE goldens byte-identical to the hand-authored ledgers).
    typed = R.Golden(metric="de_total", value=180, metric_type=R.MT_DE_COUNT)
    untyped = R.Golden(metric="de_total", value=180)
    for c in (180, 181, 200, 88):
        assert _verdict(typed, c) == _verdict(untyped, c)


# --- drive auto-goldens carry the inferred type -------------------------------


def test_to_golden_stamps_the_inferred_metric_type():
    g = GoldenTarget(metric="de_total", value=180, paper_id="p", figure="4", panel="e",
                     source=SOURCE_FIGURE, confidence=1.0)
    assert to_golden(g).metric_type == R.MT_DE_COUNT
    # An unknown metric stays untyped → graded at the defaults (no surprise widening).
    other = GoldenTarget(metric="signature.count", value=78, paper_id="p", figure="5", panel="",
                         source=SOURCE_FIGURE, confidence=1.0)
    assert to_golden(other).metric_type == ""
