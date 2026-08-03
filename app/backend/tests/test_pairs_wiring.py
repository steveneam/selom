"""The `pairs=` vocabulary as the categorical SKILLS expose it (boxplot · violin · composition).

test_stats.py covers the engine. This covers the wiring: that the params reach it, that a spec
with no pairs is untouched (which is what keeps the goldens stable), that the brackets land
inside the axis they grew, and that composition's category reorder cannot unstick a value from
its label.
"""

import pytest

from skills.boxplot.run import boxplot_spec
from skills.composition.run import _composition_spec
from skills.violin.run import violin_spec

GROUPS = {"WT": [1.0, 1.1, 0.9, 1.05], "KO": [5.0, 5.1, 4.9, 5.05], "Rx": [1.2, 1.3, 1.1, 1.25]}


def _box(params):
    return boxplot_spec(dict(GROUPS), params, "value", "group", "t")


def _violin(params):
    return violin_spec(dict(GROUPS), params, "value", "group", "t")


@pytest.mark.parametrize("build", [_box, _violin], ids=["boxplot", "violin"])
class TestSharedVocabulary:
    """Both distribution skills must speak the vocabulary identically — that is the point of a
    shared engine, and a divergence here means a user's params mean different things per skill."""

    def test_no_pairs_leaves_the_spec_untouched(self, build):
        spec = build({})
        assert "shapes" not in spec["layout"]
        assert "annotations" not in spec["layout"]
        assert "table" not in spec

    def test_pairs_draws_brackets_and_attaches_a_table(self, build):
        spec = build({"pairs": "WT~KO"})
        assert spec["layout"]["shapes"], "a bracket line + its two end ticks"
        assert [a["text"] for a in spec["layout"]["annotations"]] == ["***"]
        assert spec["table"]["rows"][0][:2] == ["WT", "KO"]

    def test_brackets_land_inside_the_grown_axis(self, build):
        """The bug this exists to catch: brackets drawn above a range that was not grown to
        hold them, so the stars are clipped off the top of the figure."""
        spec = build({"pairs": "WT~KO, WT~Rx"})
        axis = spec["layout"]["yaxis"]
        lo, hi = axis["range"]
        for anno in spec["layout"]["annotations"]:
            assert lo < anno["y"] < hi
        for shape in spec["layout"]["shapes"]:
            assert lo < shape["y0"] <= hi and lo < shape["y1"] <= hi

    def test_grown_axis_still_contains_the_data(self, build):
        """Growing the top must not crop the bottom — an explicit range starting at the data
        minimum would clip the lower whisker of the very plot being annotated."""
        spec = build({"pairs": "WT~KO"})
        lo, hi = spec["layout"]["yaxis"]["range"]
        flat = [v for vals in GROUPS.values() for v in vals]
        assert lo < min(flat) and hi > max(flat)

    def test_order_reorders_the_traces(self, build):
        spec = build({"order": "KO, Rx, WT"})
        assert [t["name"] for t in spec["data"]] == ["KO", "Rx", "WT"]

    def test_add_count_welds_n_to_each_trace_name(self, build):
        spec = build({"add_count": True})
        assert [t["name"] for t in spec["data"]] == ["WT<br>n=4", "KO<br>n=4", "Rx<br>n=4"]

    def test_brackets_follow_the_reordered_categories(self, build):
        """A bracket is drawn at category INDEX, so reordering must move the bracket with the
        category — otherwise the stars sit over the wrong pair."""
        spec = build({"pairs": "WT~KO", "order": "KO, Rx, WT"})
        # WT is now index 2 and KO index 0, so the bracket spans the full width (0 -> 2).
        line = spec["layout"]["shapes"][0]
        assert (line["x0"], line["x1"]) == (0, 2)

    def test_unknown_pair_names_are_skipped_not_fatal(self, build):
        spec = build({"pairs": "WT~ghost"})
        assert "shapes" not in spec["layout"] and "table" not in spec

    def test_correction_is_reported_in_the_table_header(self, build):
        spec = build({"pairs": "WT~KO, WT~Rx", "correction": "bonferroni"})
        assert "p (bonferroni)" in spec["table"]["columns"]
        assert "bonferroni-corrected" in spec["table"]["title"]

    def test_sig_test_choice_reaches_the_engine(self, build):
        welch = build({"pairs": "WT~KO"})["table"]
        mwu = build({"pairs": "WT~KO", "sig_test": "mannwhitney"})["table"]
        assert "Welch t" in welch["title"] and "Mann-Whitney U" in mwu["title"]
        assert welch["rows"][0][4] != mwu["rows"][0][4]


def test_boxplot_horizontal_rotates_the_brackets_onto_the_x_axis():
    spec = boxplot_spec(dict(GROUPS), {"pairs": "WT~KO", "orientation": "h"},
                        "value", "group", "t")
    line = spec["layout"]["shapes"][0]
    assert line["y0"] == 0 and line["y1"] == 1      # categories now on y
    assert line["x0"] == line["x1"]                 # the bracket sits at one x
    lo, hi = spec["layout"]["xaxis"]["range"]       # the VALUE axis is the one grown
    assert lo < line["x0"] < hi


def test_violin_passes_values_through_unrounded():
    """The real engine hands numpy through `jsonable`; rounding in the shared builder would
    silently change real-engine output."""
    spec = violin_spec({"a": [1.123456789, 2.0]}, {}, "v", "g", "t")
    assert spec["data"][0]["y"] == [1.123456789, 2.0]


# --- composition: the honest subset ----------------------------------------------------------
CATS = ["Rods", "Glia", "Microglia"]
SERIES = {"DR": [21.8, 2.6, 9.5], "PD": [4.5, 22.2, 15.2]}


def test_composition_order_carries_values_with_their_category():
    """The dangerous failure: reordering the axis but not the values, so every bar is
    mislabelled while the figure still looks plausible."""
    spec = _composition_spec(CATS, SERIES, "grouped", "v", "t", {"order": "Microglia, Rods"})
    cats = spec["data"][0]["x"]
    assert cats == ["Microglia", "Rods", "Glia"]
    by_name = {t["name"]: t["y"] for t in spec["data"]}
    assert by_name["DR"] == [9.5, 21.8, 2.6]    # each value followed its own category
    assert by_name["PD"] == [15.2, 4.5, 22.2]


def test_composition_order_is_a_noop_when_unset():
    plain = _composition_spec(CATS, SERIES, "grouped", "v", "t", {})
    none = _composition_spec(CATS, SERIES, "grouped", "v", "t", None)
    assert plain == none
    assert plain["data"][0]["x"] == CATS


def test_composition_ignores_unknown_category_names():
    spec = _composition_spec(CATS, SERIES, "grouped", "v", "t", {"order": "ghost, Glia"})
    assert spec["data"][0]["x"] == ["Glia", "Rods", "Microglia"]


def test_composition_has_no_pairs_param():
    """Composition holds ONE value per category x condition cell, so a pairwise test would
    compare n=1 with n=1 and print "ns" over every pair regardless of the data. It is
    deliberately not wired — see the note at the top of skills/composition/run.py."""
    import json
    import pathlib

    spec = json.loads(
        (pathlib.Path(__file__).parent.parent / "skills/composition/skill.json").read_text())
    assert "pairs" not in spec["param_spec"]
    assert "add_count" not in spec["param_spec"]
    assert "order" in spec["param_spec"]
