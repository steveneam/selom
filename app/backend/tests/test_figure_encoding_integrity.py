"""Guards for the three encoding defects the Phase-F parity audit found.

Each of these shipped, passed every gate, and was invisible in review because the figure *spec*
looked correct — the defect only existed once Plotly interpreted it. They are grouped here because
they share one root cause worth naming: **a Plotly spec can be well-formed and still encode
something different from what the skill meant.** A test on the dict shape cannot see that; these
assert the interpretation.

See ``docs/cnsplots-port/parity-audit.md`` §1 (D1, D2, D3).
"""

from __future__ import annotations

import pytest

from skills._plotly import numeric_label_order
from skills.enrichment.run import _DOT_MAX_PX, _DOT_MIN_PX, dotplot_spec, dotplot_split_spec
from skills.heatmap.run import heatmap_spec


# ---------------------------------------------------------------- D2: categorical axes
def test_heatmap_axes_declare_category_type():
    """A heatmap's axes carry LABELS, never a scale.

    Without an explicit type, Plotly infers a LINEAR axis from numeric-looking labels and lays the
    columns out at their numeric values — which on a real 17-cluster matrix left the map filling
    ~55% of the canvas with 7 clusters unreadable as distinct columns.
    """
    spec = heatmap_spec([[0.0, 1.0]], ["0", "10"], ["GENE1"], "t", "cluster")
    assert spec["layout"]["xaxis"]["type"] == "category"
    assert spec["layout"]["yaxis"]["type"] == "category"


def test_heatmap_axes_declare_category_type_in_clustermap_layout():
    """The clustermap branch builds its own axis dicts — it must not lose the pin."""
    dendro = {"icoord": [[0.0, 0.0, 1.0, 1.0]], "dcoord": [[0.0, 1.0, 1.0, 0.0]]}
    spec = heatmap_spec(
        [[0.0, 1.0], [1.0, 0.0]], ["0", "10"], ["G1", "G2"], "t", "cluster", row_dendro=dendro
    )
    assert spec["layout"]["xaxis"]["type"] == "category"
    assert spec["layout"]["yaxis"]["type"] == "category"


@pytest.mark.parametrize(
    ("labels", "expected"),
    [
        # the exact shape pandas' groupby hands back for Leiden ids: lexicographic
        (["0", "1", "10", "11", "2", "9"], ["0", "1", "2", "9", "10", "11"]),
        (["3", "1", "2"], ["1", "2", "3"]),
        (["0", "1", "2"], None),          # already numeric-ordered -> no permutation
        (["WT", "KO"], None),             # not numeric -> caller's order is meaningful, leave it
        (["1", "KO"], None),              # mixed -> not ours to reorder
        ([], None),
    ],
)
def test_numeric_label_order(labels, expected):
    order = numeric_label_order(labels)
    if expected is None:
        assert order is None
    else:
        assert [labels[i] for i in order] == expected


def test_numeric_label_order_permutes_a_matrix_in_step():
    """The helper returns INDICES precisely so a caller can permute its matrix with them."""
    labels = ["0", "10", "2"]
    z = [[1.0, 2.0, 3.0]]
    order = numeric_label_order(labels)
    assert [labels[i] for i in order] == ["0", "2", "10"]
    assert [[row[i] for i in order] for row in z] == [[1.0, 3.0, 2.0]]


# ---------------------------------------------------------------- D1: dot-size encoding
def _sizes(spec, trace=0):
    return spec["data"][trace]["marker"]["size"]


def test_enrichment_dot_sizes_are_pixel_diameters_not_raw_counts():
    """`marker.size` is a DIAMETER IN PIXELS. Passing the raw overlap count drew 1-3 px dots."""
    spec = dotplot_spec(["A", "B", "C"], [3.0, 2.0, 1.0], [1, 2, 3], "t")
    sizes = _sizes(spec)
    assert min(sizes) >= _DOT_MIN_PX, "a dot must stay visible at the smallest count"
    assert max(sizes) == pytest.approx(_DOT_MAX_PX)


def test_enrichment_dot_sizes_stay_ordered_with_the_counts():
    """The encoding must remain monotone — bigger overlap, strictly bigger dot."""
    counts = [1, 4, 9, 30]
    spec = dotplot_spec([f"P{c}" for c in counts], [1.0] * len(counts), counts, "t")
    # dotplot_spec reverses the arrays for Plotly's bottom-up y axis, so re-pair before comparing
    by_count = sorted(zip(reversed(counts), _sizes(spec)))
    sizes_in_count_order = [s for _, s in by_count]
    assert sizes_in_count_order == sorted(sizes_in_count_order)
    assert len(set(sizes_in_count_order)) == len(counts), "distinct counts must be distinguishable"


def test_enrichment_emits_a_size_legend():
    """A size channel with no key cannot be decoded; Plotly builds no size legend of its own."""
    spec = dotplot_spec(["A", "B", "C"], [3.0, 2.0, 1.0], [1, 5, 12], "t")
    proxies = [t for t in spec["data"] if t.get("legendgroup") == "dotsize"]
    assert proxies, "expected legend proxy traces for the dot-size key"
    assert all(t["x"] == [None] for t in proxies), "a key trace must plot no data"
    assert spec["data"][0].get("showlegend") is False, "the data trace must not duplicate the key"
    assert {t["name"] for t in proxies} == {"1 gene", "5 genes", "12 genes"}


def test_enrichment_size_legend_is_absent_when_there_is_nothing_to_key():
    spec = dotplot_spec(["A"], [1.0], [0], "t")
    assert [t for t in spec["data"] if t.get("legendgroup") == "dotsize"] == []


def test_split_dotplot_scales_both_directions_on_one_scale():
    """Up and down are separate traces. Scaling each to its own maximum would draw the same
    overlap count at two different sizes — an encoding that silently lies."""
    up = [{"pathway": "U", "nlp": 2.0, "overlap": 10}]
    down = [{"pathway": "D", "nlp": 2.0, "overlap": 10}, {"pathway": "D2", "nlp": 1.0,
                                                          "overlap": 40}]
    spec = dotplot_split_spec(up, down, "t")
    down_sizes, up_sizes = _sizes(spec, 0), _sizes(spec, 1)
    assert up_sizes[0] == down_sizes[0], "overlap 10 must be one size in both directions"
    assert max(down_sizes) == pytest.approx(_DOT_MAX_PX)


# ---------------------------------------------------------------- D3: one font, both sides
def test_default_style_font_matches_the_journal_styles_stack():
    """The default style must resolve to the same face as every other style.

    It previously led with `Inter`, which nothing bundles, so it fell through to a different
    fallback than the frontend's chain did — the figure on screen and the figure in the export
    were set in different typefaces.
    """
    from skills.styles import SANS_OPEN, STYLES

    assert STYLES["selom"].font_family == SANS_OPEN
    assert "Inter" not in STYLES["selom"].font_family


def test_no_style_declares_a_font_nothing_bundles():
    """Ratchet: adding a style whose stack leads with an unbundled family reintroduces D3."""
    from skills.styles import STYLES

    unbundled = ("Inter", "Helvetica Neue")
    for style in STYLES.values():
        lead = style.font_family.split(",")[0].strip().strip("'\"")
        assert lead not in unbundled, (
            f"style {style.id!r} leads with {lead!r}, which is bundled by neither the frontend nor "
            "the render image — it will resolve differently on the two sides (parity-audit D3)"
        )


# ------------------------------------------------ D2 again: the ANNOTATION layer (2026-08-04)
# Declaring `type: "category"` fixes the TRACE and not the annotation layer, which is a separate
# coordinate parser with the same numeric-string weakness. Found in `confusion`, whose per-cell
# counts scrambled across a correctly-laid-out heatmap and pushed one label clean off the plot.
def test_confusion_cell_labels_are_positioned_by_index_not_category_name():
    """Cell text must be pinned by integer index, never by the category's name.

    On a category axis Plotly coerces a numeric-looking STRING coordinate to a number and then
    reads it as a SLOT INDEX — so an annotation at ``x="7"`` lands on the 8th category rather than
    the one called "7". Cluster ids are numeric strings on every scRNA path, so naming the category
    mislays every label; ids at or past the category count are drawn outside the plot entirely.
    """
    from skills.confusion.run import confusion_spec

    spec = confusion_spec([[5, 1], [2, 9]], ["a", "b"], ["5", "7"], {},
                          "reference", "predicted", "t")
    annotations = spec["layout"]["annotations"]
    assert annotations, "confusion must label its cells"
    for anno in annotations:
        assert isinstance(anno["x"], int), f"annotation x is {anno['x']!r}, not an index"
        assert isinstance(anno["y"], int), f"annotation y is {anno['y']!r}, not an index"


def test_check_figure_rejects_a_category_annotation_pinned_by_name():
    """The ratchet, both directions: the guard fires on the defect and stays quiet without it."""
    from skills.smoke import check_figure

    def figure(anno_x):
        return {
            "data": [{"type": "heatmap", "z": [[1, 2]], "x": ["5", "7"], "y": ["a"]}],
            "layout": {
                "xaxis": {"type": "category"}, "yaxis": {"type": "category"},
                "annotations": [{"x": anno_x, "y": 0, "text": "1", "showarrow": False}],
            },
        }

    assert "SLOT INDEX" in check_figure(figure("7"))
    assert check_figure(figure(1)) == ""


# ------------------------------------------------ D1 again: marker size as a UNIT (2026-08-04)
def test_check_figure_rejects_sub_pixel_marker_sizes():
    """A marker.size under 2px is the matplotlib-area-vs-Plotly-diameter confusion, not a choice.

    matplotlib's scatter ``s`` is an AREA in points²; Plotly's ``marker.size`` is a pixel DIAMETER.
    Porting a value across (or passing a raw count, as `enrichment` did) draws dots 1-3px wide —
    a figure that is valid, themed, exported, and unreadable. cnsplots' own ``lollipopplot``
    defaults ``markersize=20`` in ``s`` units, so the trap is live on every port from it.
    """
    from skills.smoke import check_figure

    def figure(size):
        return {"data": [{"type": "scatter", "x": [1], "y": [1], "marker": {"size": size}}],
                "layout": {}}

    assert "marker.size" in check_figure(figure(1.5))
    # An array is judged on its MAXIMUM: a real bubble encoding has small points at the bottom of
    # its range, but if even the largest is sub-pixel the whole encoding is in the wrong unit.
    assert "marker.size" in check_figure(figure([1, 1.8, 1.2]))
    assert check_figure(figure(9)) == ""
    assert check_figure(figure([1, 2, 14])) == ""               # a real bubble range is fine
    # A trace that declares how its numbers map to pixels has said what it means — left alone.
    assert check_figure({"data": [{"type": "scatter", "x": [1], "y": [1],
                                   "marker": {"size": [1, 2], "sizeref": 0.01}}],
                         "layout": {}}) == ""


def test_lollipop_dot_is_a_visible_pixel_diameter():
    """Ratchet on the port itself: the dot size must survive as pixels, not cnsplots' area."""
    from skills.lollipop.run import _DOT_SIZE

    assert 4 <= _DOT_SIZE <= 20, f"{_DOT_SIZE} is not a plausible pixel diameter"


# ------------------------------------------------ colour that carries MEANING (2026-08-04)
def test_lollipop_stem_declares_its_own_colour():
    """The stem is furniture and must not consume a colourway slot.

    Left to the theme, the stem trace takes the next colour in the sequence and the figure renders
    a blue stem under an orange dot — one mark reading as two unrelated series. No assertion on the
    spec can catch that, because nothing in the spec says which trace is furniture.
    """
    from skills.lollipop.run import lollipop_spec

    spec = lollipop_spec({"a": [1.0, 2.0, 3.0], "b": [4.0, 5.0, 6.0]}, {}, "v", "g", "t")
    stem = next(t for t in spec["data"] if t.get("name") == "stem")
    assert stem["line"].get("color"), "the stem must set its own colour"


def test_ridge_leaves_fill_and_line_colour_to_the_theme():
    """A `fill: "toself"` scatter derives its FILL from the trace's line colour.

    So pinning the outline silently repaints every ridge that colour and the colourway never
    arrives — which is exactly what happened when the outline was set to a neutral grey to make the
    stack read more clearly. Both keys must stay unset.
    """
    from skills.ridge.run import ridge_spec

    values = {"a": [1.0, 1.4, 2.2, 2.9, 3.1], "b": [4.0, 4.6, 5.2, 5.8, 6.1]}
    spec = ridge_spec(values, {}, "v", "g", "t")
    ridges = [t for t in spec["data"] if t.get("fill") == "toself"]
    assert len(ridges) == 2
    for trace in ridges:
        assert "fillcolor" not in trace
        assert "color" not in trace.get("line", {})
