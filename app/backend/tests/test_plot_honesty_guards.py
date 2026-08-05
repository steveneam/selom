"""Guards on what the four 2026-08-04 plot types REFUSE to do.

Every skill here can produce a confident, well-formed, publication-looking figure from data that
does not support the claim it makes. Those refusals are the load-bearing behaviour — a bug in one
does not crash anything, it prints a number nobody can challenge — so they are pinned here rather
than left to review.

The shared shape: **a statistic is only reported when the data can carry it.** cnsplots is the
reference for the geometry of all four (BSD-3, `docs/cnsplots-port/source-review.md` §3.2) and it
makes the opposite trade in two places on purpose — `slopeplot` computes no statistic at all, and
`lollipopplot` will draw an error bar wherever pandas can compute one. Selom reports more, so it
has more to get wrong.
"""

from __future__ import annotations

import pytest

from skills.confusion.run import _agreement, confusion_spec
from skills.lollipop.run import _ci, lollipop_spec
from skills.ridge.run import gaussian_kde, ridge_spec, silverman_bandwidth
from skills.slope.run import slope_spec


# ---------------------------------------------------------------- lollipop: the interval
def test_lollipop_refuses_a_confidence_interval_below_three_values():
    """A 2-point bootstrap resamples from two numbers and describes the resampler, not the data."""
    assert _ci([1.0, 2.0], "median") is None
    assert _ci([1.0, 2.0, 3.0], "median") is not None


def test_lollipop_on_a_preaggregated_table_draws_no_error_bars_and_claims_no_ci():
    """One row per category (the shape a ranked list actually arrives in) has n=1 everywhere.

    The figure must carry no error bar and the table must not advertise CI columns — a column of
    "n/a" headed "CI low" states a claim the run never made.
    """
    spec = lollipop_spec({"a": [3.0], "b": [2.0], "c": [1.0]}, {}, "score", "term", "t")
    dots = next(t for t in spec["data"] if t.get("mode", "").startswith("markers"))
    assert "error_x" not in dots and "error_y" not in dots
    assert "CI low" not in spec["table"]["columns"]


def test_lollipop_bootstrap_is_deterministic():
    """A seeded resampler, so the same table redraws byte-identically."""
    values = [1.0, 4.0, 2.0, 8.0, 5.0, 3.0, 9.0]
    assert _ci(values, "median") == _ci(values, "median")


def test_lollipop_drops_brackets_when_every_group_is_a_single_value():
    """`composition` takes the ordering half only because n=1 vs n=1 reads "ns" whatever the data
    says. A lollipop meets both shapes, so it makes the same call per run rather than by design."""
    spec = lollipop_spec({"a": [3.0], "b": [2.0]}, {"pairs": "a~b"}, "score", "term", "t")
    assert not spec["layout"].get("shapes")
    assert "Pairwise" not in (spec["table"].get("title") or "")


def test_lollipop_keeps_brackets_when_the_groups_have_replicates():
    """The other direction — the refusal must not swallow a legitimate comparison."""
    spec = lollipop_spec({"a": [3.0, 3.2, 2.9, 3.1], "b": [1.0, 1.2, 0.9, 1.1]},
                         {"pairs": "a~b"}, "score", "term", "t")
    assert spec["layout"].get("shapes"), "a real pairwise comparison must still draw its bracket"


def test_lollipop_keeps_BOTH_tables_when_pairs_is_set():
    """The squeeze is gone (docs/stats-tables/spec.md slice 3).

    Asking for `pairs` used to DISCARD the ranked values — rank, n and the asymmetric bootstrap CI
    bounds, none of which are readable off a dot — because the wire carried exactly one table. The
    trade was made the right way round, but it was forced by the wire shape rather than by anything
    about the science. Both are attached now, in the runner's order: the ranked values are the
    primary result and the pairwise table is the provenance of the stars already drawn."""
    from skills._table import as_tables

    values = {"a": [3.0, 3.2, 2.9, 3.1, 3.05], "b": [1.0, 1.2, 0.9, 1.1, 1.05]}
    spec = lollipop_spec(values, {"pairs": "a~b"}, "score", "term", "t")
    tables = as_tables(spec["table"])
    assert len(tables) == 2, "the ranked values must survive a pairwise run"

    ranked, pairwise = tables
    assert ranked["columns"][0] == "rank"
    assert "CI low" in ranked["columns"], "the bootstrap interval is the thing that was being lost"
    assert "Pairwise" in (pairwise.get("title") or "")
    assert "p" in pairwise["columns"]
    # G4: stacked panels are told apart by their titles, so a multi-table result must name each.
    assert all((t.get("title") or "").strip() for t in tables)

    # ...and the drawn stars still have their numbers, which is what the old trade protected.
    assert spec["layout"].get("shapes"), "the brackets are still drawn"
    assert pairwise["rows"], "the p-values behind those stars are still reachable"


def test_lollipop_without_pairs_still_attaches_ONE_bare_table():
    """The no-op half: nothing changes for a run that asked for no comparison. A bare object, not a
    one-element list — every persisted `table_stats` row holds an object."""
    spec = lollipop_spec({"a": [3.0, 3.2, 2.9], "b": [1.0, 1.2, 0.9]}, {}, "score", "term", "t")
    assert isinstance(spec["table"], dict)
    assert spec["table"]["columns"][0] == "rank"


# ---------------------------------------------------------------- confusion: the diagonal
def test_confusion_refuses_agreement_when_the_label_sets_differ():
    """Leiden ids against cell-type names have NO diagonal.

    An "accuracy" there would report an alignment nobody declared — the cell at (Rods, cluster 3)
    is not a 'correct' cell. This is the real-corpus path (`clusters` x `celltypes`), so the
    refusal is what the smoke matrix exercises every run.
    """
    assert _agreement([[5, 1], [2, 9]], ["Rods", "Cones"], ["3", "7"]) is None


def test_confusion_reports_agreement_when_the_vocabularies_match():
    counts = [[8, 2], [1, 9]]
    labels = ["Rods", "Cones"]
    agreement, kappa, n = _agreement(counts, labels, labels)
    assert n == 20
    assert agreement == pytest.approx(0.85)
    assert kappa == pytest.approx(0.7)          # (0.85 - 0.5) / (1 - 0.5)


def test_confusion_table_names_the_reason_metrics_are_absent():
    """Silence would read as "these labels agree perfectly" — it has to say why there is no number."""
    spec = confusion_spec([[5, 1], [2, 9]], ["Rods", "Cones"], ["3", "7"], {}, "ref", "pred", "t")
    title = spec["table"]["title"]
    assert "no diagonal" in title and "kappa" in title


def test_confusion_normalization_keeps_the_raw_count_reachable():
    """A 100% row of ONE observation looks identical to a 100% row of a thousand once normalized,
    so the count has to survive somewhere — it rides in customdata for the hover."""
    spec = confusion_spec([[1, 0], [500, 500]], ["a", "b"], ["x", "y"],
                          {"normalize": "row"}, "ref", "pred", "t")
    heat = spec["data"][0]
    assert heat["customdata"] == [[1.0, 0.0], [500.0, 500.0]]
    assert "customdata" in heat["hovertemplate"]


# ---------------------------------------------------------------- slope: the pairing
def test_slope_uses_a_paired_test_not_an_unpaired_one():
    """The figure's whole claim is the pairing; an unpaired test discards it.

    Constructed so the two tests disagree loudly: every subject rises by exactly 1.0 while the
    groups overlap almost completely. Paired sees a perfect, highly significant shift; unpaired
    sees two indistinguishable clouds.
    """
    from skills._stats import compare_groups, compare_paired

    before = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    after = [v + 1.0 for v in before]
    paired = compare_paired(before, after)
    unpaired = compare_groups(before, after)
    assert paired < 0.001
    assert unpaired > 0.3
    assert paired < unpaired / 100


def test_slope_paired_test_drops_a_pair_missing_either_side():
    """Half a pair carries no paired information, so it leaves as a unit."""
    from skills._stats import compare_paired

    clean = compare_paired([1.0, 2.0, 3.0], [2.0, 3.0, 4.0])
    ragged = compare_paired([1.0, 2.0, 3.0, 9.0], [2.0, 3.0, 4.0, float("nan")])
    assert ragged == pytest.approx(clean)


def test_slope_reports_the_direction_split():
    """The number a bar chart destroys: a flat mean from half rising and half falling is a
    different finding from a flat mean from nobody moving."""
    paired = {"g": {"s1": (1.0, 2.0), "s2": (1.0, 2.0), "s3": (3.0, 1.0), "s4": (3.0, 1.0)}}
    spec = slope_spec(paired, ("before", "after"), {}, "v", "g", "t")
    row = spec["table"]["rows"][0]
    assert "2 up / 2 down" in row


def test_slope_colours_segments_by_direction():
    paired = {"g": {"up": (1.0, 2.0), "down": (2.0, 1.0)}}
    spec = slope_spec(paired, ("before", "after"), {}, "v", "g", "t")
    names = {t["name"] for t in spec["data"]}
    assert {"increased", "decreased"} <= names


def test_slope_refuses_when_nothing_is_paired():
    with pytest.raises(ValueError, match="nothing paired|paired"):
        slope_spec({"g": {}}, ("before", "after"), {}, "v", "g", "t")


# ---------------------------------------------------------------- ridge: the density
def test_ridge_kde_matches_scipy():
    """The hand-rolled KDE exists so the dependency-free stub draws the SAME curve as the real
    engine. That is only true if it agrees with the reference implementation."""
    scipy_stats = pytest.importorskip("scipy.stats")
    import numpy as np

    values = [1.0, 1.4, 2.2, 2.9, 3.1, 3.4, 4.8, 5.2]
    grid = [0.5 + 0.5 * i for i in range(12)]
    bw = silverman_bandwidth(values)
    mine = gaussian_kde(values, grid, bw)
    # scipy parameterizes bandwidth as a factor of the sample sd; hand it the same absolute width.
    theirs = scipy_stats.gaussian_kde(values, bw_method=bw / np.std(values, ddof=1))(grid)
    assert mine == pytest.approx(list(theirs), rel=1e-9)


def test_ridge_excludes_a_group_that_cannot_support_a_density_and_names_it():
    """A constant or 2-point group has no density to estimate. Dropping it silently would read as
    "this group had no data", so it is named in the table instead."""
    values = {"real": [1.0, 1.5, 2.2, 3.0, 3.4], "flat": [2.0, 2.0, 2.0, 2.0], "tiny": [1.0]}
    spec = ridge_spec(values, {}, "v", "g", "t")
    ridges = [t for t in spec["data"] if t.get("fill") == "toself"]
    assert len(ridges) == 1
    title = spec["table"]["title"]
    assert "excluded" in title and "flat" in title and "tiny" in title


def test_ridge_refuses_entirely_when_no_group_can_support_a_density():
    with pytest.raises(ValueError, match="strip"):
        ridge_spec({"a": [1.0], "b": [2.0]}, {}, "v", "g", "t")


def test_ridge_discloses_its_bandwidth():
    """A curve is exactly as bimodal as its bandwidth allows, so the smoothing is not an
    implementation detail — it is a parameter the reader needs to judge the shape."""
    spec = ridge_spec({"a": [1.0, 1.4, 2.2, 2.9, 3.1]}, {}, "v", "g", "t")
    assert "bandwidth" in spec["table"]["columns"]
    assert "Silverman" in spec["table"]["title"]


def test_ridge_common_scale_preserves_relative_density():
    """`peak` makes a 5-point group as tall as a 5000-point one — the convention, and a real
    distortion. `common` is the escape hatch, so it must actually differ."""
    values = {"wide": [0.0, 2.0, 4.0, 6.0, 8.0, 10.0], "tight": [4.9, 5.0, 5.1, 5.05, 4.95]}
    peak = ridge_spec(values, {"scale": "peak"}, "v", "g", "t")
    common = ridge_spec(values, {"scale": "common"}, "v", "g", "t")

    def peak_heights(spec):
        out = []
        for trace in spec["data"]:
            if trace.get("fill") != "toself":
                continue
            base = min(trace["y"])
            out.append(round(max(trace["y"]) - base, 6))
        return out

    assert peak_heights(peak) == pytest.approx([1.0, 1.0])
    heights = peak_heights(common)
    assert min(heights) < 0.5, "a common scale must let a broad distribution sit lower"
