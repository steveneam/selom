"""The shared significance-annotation engine (skills/_stats.py) — the ``pairs=`` feature.

Covers the four things that can silently produce a WRONG figure rather than a failed run:
the star thresholds, the multiple-comparison correction (and its effect on the drawn stars),
the bracket geometry on a plot that is not anchored at zero, and the table naming its own
p column honestly.
"""

import math

import pytest

from skills import _stats


# --- stars + tests ------------------------------------------------------------------------
def test_sig_stars_thresholds():
    assert _stats.sig_stars(0.0005) == "***"
    assert _stats.sig_stars(0.005) == "**"
    assert _stats.sig_stars(0.03) == "*"
    assert _stats.sig_stars(0.2) == "ns"
    assert _stats.sig_stars(None) == "ns"
    assert _stats.sig_stars(float("nan")) == "ns"
    assert _stats.sig_stars("not a number") == "ns"


def test_sig_stars_boundaries_are_strict():
    """Exactly 0.05 is NOT significant — the convention is p < 0.05, and a boundary that
    rounds the wrong way turns a null result into a starred one."""
    assert _stats.sig_stars(0.05) == "ns"
    assert _stats.sig_stars(0.0499999) == "*"
    assert _stats.sig_stars(0.01) == "*"
    assert _stats.sig_stars(0.001) == "**"


def test_compare_groups_needs_two_per_side():
    assert _stats.compare_groups([1.0], [2.0, 3.0]) is None
    assert _stats.compare_groups([], []) is None
    p = _stats.compare_groups([1.0, 1.1, 0.9], [5.0, 5.1, 4.9])
    assert p is not None and p < 0.001


def test_compare_groups_tests_differ():
    a, b = [1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]
    welch = _stats.compare_groups(a, b, "welch")
    mwu = _stats.compare_groups(a, b, "mannwhitney")
    assert welch is not None and mwu is not None and welch != mwu


# --- multiple-comparison correction --------------------------------------------------------
def test_bonferroni_scales_by_family_size():
    out = _stats.adjust_pvalues([0.01, 0.02, 0.03], "bonferroni")
    assert out == [0.03, 0.06, 0.09]


def test_bonferroni_caps_at_one():
    assert _stats.adjust_pvalues([0.5, 0.9], "bonferroni") == [1.0, 1.0]


def test_bh_is_monotone_and_step_up():
    """BH: p*n/rank, then enforced non-decreasing with p. The largest p is never inflated."""
    out = _stats.adjust_pvalues([0.01, 0.02, 0.03, 0.04], "bh")
    assert out == sorted(out)                      # monotone in the input order (already sorted)
    assert out[-1] == pytest.approx(0.04)          # largest: p*n/n == p
    assert out[0] == pytest.approx(0.04)           # step-up pulls the smallest up to its neighbour
    assert all(v <= 1.0 for v in out)


def test_bh_matches_a_hand_worked_case():
    # p*n/rank = [0.001*4/1, 0.008*4/2, 0.039*4/3, 0.041*4/4] = [0.004, 0.016, 0.052, 0.041]
    # step-up from the largest: 0.041 -> 0.041, then min(0.052, 0.041) = 0.041, ...
    out = _stats.adjust_pvalues([0.001, 0.008, 0.039, 0.041], "bh")
    assert out == pytest.approx([0.004, 0.016, 0.041, 0.041])


def test_bh_matches_scipy():
    """The oracle check. adjust_pvalues is hand-rolled (pure Python, so a figure never needs
    scipy to be honest about its own multiplicity) — so it is pinned against the reference
    implementation, unsorted input included, rather than against my own arithmetic."""
    import numpy as np
    from scipy.stats import false_discovery_control

    for case in ([0.001, 0.008, 0.039, 0.041],
                 [0.01, 0.02, 0.03, 0.04],
                 [0.0001, 0.3, 0.5, 0.02, 0.9, 0.045],   # unsorted
                 [0.04, 0.01]):
        assert _stats.adjust_pvalues(case, "bh") == pytest.approx(
            list(false_discovery_control(np.array(case), method="bh")))


def test_correction_none_is_identity():
    vals = [0.01, 0.5, None]
    assert _stats.adjust_pvalues(vals, "none") == vals
    assert _stats.adjust_pvalues(vals, "") == vals


def test_none_pvalues_do_not_join_the_family():
    """An untestable pair (n<2) must not inflate everyone else's correction."""
    out = _stats.adjust_pvalues([0.01, None, 0.02], "bonferroni")
    assert out[1] is None
    assert out[0] == pytest.approx(0.02)   # family size 2, not 3
    assert out[2] == pytest.approx(0.04)


# --- the pairs contract --------------------------------------------------------------------
def test_parse_pairs_forms():
    assert _stats.parse_pairs("A~B") == [("A", "B", None)]
    assert _stats.parse_pairs("A~B, C~D") == [("A", "B", None), ("C", "D", None)]
    assert _stats.parse_pairs("A~B; C~D") == [("A", "B", None), ("C", "D", None)]
    assert _stats.parse_pairs("A~B:**") == [("A", "B", "**")]
    assert _stats.parse_pairs("A~B:0.003") == [("A", "B", "0.003")]
    assert _stats.parse_pairs(" WT ~ KO ") == [("WT", "KO", None)]


def test_parse_pairs_skips_malformed_rather_than_raising():
    """A typo should cost a bracket, not the whole run."""
    assert _stats.parse_pairs("A~B, garbage, ~, C~") == [("A", "B", None)]
    assert _stats.parse_pairs("") == []
    assert _stats.parse_pairs(None) == []


def test_parse_pairs_accepts_structured_input():
    assert _stats.parse_pairs([("A", "B"), ["C", "D", "*"]]) == [("A", "B", None), ("C", "D", "*")]


def test_resolve_stars_override_wins_and_reports_no_p():
    stars, p = _stats.resolve_stars("**", [1.0, 1.0, 1.0], [1.0, 1.0, 1.0], "welch")
    assert stars == "**"
    assert p is None, "a literal star override computed no p — the table must not invent one"


def test_resolve_stars_numeric_override_yields_that_p():
    stars, p = _stats.resolve_stars("0.003", [], [], "welch")
    assert (stars, p) == ("**", 0.003)


def test_resolve_stars_falls_through_to_the_test():
    stars, p = _stats.resolve_stars(None, [1.0, 1.1, 0.9], [5.0, 5.1, 4.9], "welch")
    assert stars == "***" and p is not None


# --- test_pairs ------------------------------------------------------------------------------
def _vals():
    return {"WT": [1.0, 1.1, 0.9, 1.05], "KO": [5.0, 5.1, 4.9, 5.05], "Rx": [1.2, 1.3, 1.1, 1.25]}


def test_test_pairs_drops_unknown_keys():
    out = _stats.test_pairs([("WT", "nope", None), ("WT", "KO", None)], _vals())
    assert [(r["a"], r["b"]) for r in out] == [("WT", "KO")]


def test_test_pairs_carries_n_and_p():
    out = _stats.test_pairs([("WT", "KO", None)], _vals())
    assert out[0]["n_a"] == 4 and out[0]["n_b"] == 4
    assert out[0]["p"] is not None and out[0]["stars"] == "***"


def test_correction_changes_the_drawn_stars_not_just_the_table():
    """The whole point: if the table is corrected and the figure is not, the figure lies."""
    vals = {"a": [1.0, 1.02, 0.98], "b": [1.06, 1.08, 1.04], "c": [1.12, 1.14, 1.1],
            "d": [1.18, 1.2, 1.16]}
    pairs = [("a", "b", None), ("a", "c", None), ("a", "d", None), ("b", "c", None)]
    plain = _stats.test_pairs(pairs, vals, correction="none")
    corrected = _stats.test_pairs(pairs, vals, correction="bonferroni")
    assert [r["p_adj"] for r in plain] == [None] * 4 or all(
        r["p_adj"] == r["p"] for r in plain)
    # every corrected p is >= its raw p, and no corrected star is stronger than its raw star
    rank = {"ns": 0, "*": 1, "**": 2, "***": 3}
    for pl, co in zip(plain, corrected):
        assert co["p_adj"] >= pl["p"] - 1e-12
        assert rank[co["stars"]] <= rank[pl["stars"]]


def test_correction_never_overrides_a_hand_set_star():
    out = _stats.test_pairs([("WT", "KO", "***")], _vals(), correction="bonferroni")
    assert out[0]["stars"] == "***"


# --- geometry ---------------------------------------------------------------------------------
def test_brackets_stack_without_overlapping():
    results = _stats.test_pairs([("WT", "KO", None), ("WT", "Rx", None)], _vals())
    shapes, annos, top = _stats.bracket_shapes(results, {"WT": 0, "KO": 1, "Rx": 2}, 5.1)
    assert len(annos) == 2
    ys = [a["y"] for a in annos]
    assert ys[0] < ys[1], "the second bracket must sit above the first"
    assert top > max(ys), "the returned ceiling must clear the topmost star"


def test_bracket_span_defaults_to_top_for_a_zero_anchored_plot():
    """The bar-chart default, unchanged — this is what keeps the ERG goldens identical."""
    results = _stats.test_pairs([("WT", "KO", None)], _vals())
    _, annos, top = _stats.bracket_shapes(results, {"WT": 0, "KO": 1}, 10.0)
    assert top == pytest.approx(10.0 + 10.0 * 0.12 * 2)


def test_bracket_span_rescues_an_unanchored_plot():
    """Values clustered at ~100 with a span of ~1: sizing off the top would put the bracket
    ~12 units away. With the real span it sits just above the data."""
    results = _stats.test_pairs([("WT", "KO", None)], _vals())
    _, annos, top = _stats.bracket_shapes(results, {"WT": 0, "KO": 1}, 101.0, span=1.0)
    assert top - 101.0 < 1.0, "bracket headroom must scale with the data span, not its magnitude"


def test_horizontal_orientation_swaps_the_axes():
    results = _stats.test_pairs([("WT", "KO", None)], _vals())
    v_shapes, v_annos, _ = _stats.bracket_shapes(results, {"WT": 0, "KO": 1}, 5.1)
    h_shapes, h_annos, _ = _stats.bracket_shapes(
        results, {"WT": 0, "KO": 1}, 5.1, orientation="h")
    # vertical: categories span x, the bracket sits at a constant y
    assert v_shapes[0]["x0"] == 0 and v_shapes[0]["x1"] == 1
    assert v_shapes[0]["y0"] == v_shapes[0]["y1"]
    # horizontal: mirrored
    assert h_shapes[0]["y0"] == 0 and h_shapes[0]["y1"] == 1
    assert h_shapes[0]["x0"] == h_shapes[0]["x1"]
    assert v_annos[0]["yanchor"] == "bottom" and h_annos[0]["xanchor"] == "left"


def test_no_results_leaves_the_axis_alone():
    shapes, annos, top = _stats.bracket_shapes([], {"WT": 0}, 7.5)
    assert shapes == [] and annos == [] and top == 7.5


def test_bracket_shapes_are_json_safe():
    results = _stats.test_pairs([("WT", "KO", None)], _vals())
    shapes, annos, _ = _stats.bracket_shapes(results, {"WT": 0, "KO": 1}, 5.1)
    for d in [*shapes, *annos]:
        for v in d.values():
            assert not isinstance(v, float) or math.isfinite(v)


# --- n= labels and the order contract ----------------------------------------------------------
def test_count_labels_welds_n_to_the_label():
    out = _stats.count_labels(["WT", "KO"], _vals())
    assert out == {"WT": "WT<br>n=4", "KO": "KO<br>n=4"}


def test_count_labels_respects_display_labels_and_ignores_non_finite():
    vals = {"WT": [1.0, float("nan"), 3.0, None]}
    out = _stats.count_labels(["WT"], vals, {"WT": "Wild type"})
    assert out == {"WT": "Wild type<br>n=2"}


def test_resolve_order_puts_named_first_then_the_rest():
    assert _stats.resolve_order(["c", "a", "b"], "a, b") == ["a", "b", "c"]


def test_resolve_order_ignores_unknown_and_dedupes():
    """A stale category name in a saved spec should reorder what it can, not fail."""
    assert _stats.resolve_order(["a", "b"], "b, ghost, b") == ["b", "a"]
    assert _stats.resolve_order(["a", "b"], None) == ["a", "b"]
    assert _stats.resolve_order(["a", "b"], "") == ["a", "b"]


def test_parse_list_forms():
    assert _stats.parse_list("a, b;c") == ["a", "b", "c"]
    assert _stats.parse_list(["a", " b "]) == ["a", "b"]
    assert _stats.parse_list(None) == []


# --- the Statistics table -----------------------------------------------------------------------
def test_pairs_table_names_an_uncorrected_column_p():
    results = _stats.test_pairs([("WT", "KO", None)], _vals())
    tbl = _stats.pairs_table(results, test="welch")
    assert tbl["columns"] == ["group A", "group B", "n A", "n B", "p", ""]
    assert "Welch t, two-sided" in tbl["title"]
    assert "corrected" not in tbl["title"]


def test_pairs_table_adds_a_named_column_only_when_correction_ran():
    """A column headed for an adjustment that did not happen is the WS3.1 lie."""
    results = _stats.test_pairs([("WT", "KO", None)], _vals(), correction="bonferroni")
    tbl = _stats.pairs_table(results, test="welch", correction="bonferroni")
    assert tbl["columns"] == ["group A", "group B", "n A", "n B", "p", "p (bonferroni)", ""]
    assert "bonferroni-corrected" in tbl["title"]


def test_pairs_table_never_fabricates_a_p_for_a_hand_set_star():
    results = _stats.test_pairs([("WT", "KO", "**")], _vals())
    tbl = _stats.pairs_table(results)
    assert tbl["rows"][0][4] == "set by hand"
    assert tbl["rows"][0][-1] == "**"


def test_pairs_table_is_none_when_nothing_was_tested():
    assert _stats.pairs_table([]) is None


def test_pairs_table_reports_an_untestable_pair_as_na():
    results = _stats.test_pairs([("WT", "solo", None)], {"WT": [1.0, 2.0], "solo": [3.0]})
    tbl = _stats.pairs_table(results)
    assert tbl["rows"][0][4] == "n/a"
    assert tbl["rows"][0][-1] == "ns"
