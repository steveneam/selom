"""Journal style registry + the /figures/styles + /figures/style/apply API.

`selom` byte-identical output is already pinned by the golden tests; here we check
the registry, the non-default styles' tokens land, the transform is safe to
re-apply (style switching round-trips), and the API surface.
"""

import copy

from fastapi.testclient import TestClient

from main import app
from skills import styles, theme

client = TestClient(app)


def _base_fig():
    return {
        "data": [{"type": "scatter", "x": [1, 2, 3], "y": [3, 1, 2], "marker": {"color": "#123456"}}],
        "layout": {"title": {"text": "t"}, "xaxis": {"title": "x"}, "yaxis": {"title": "y"}},
    }


def _volcano_fig():
    return {
        "data": [
            {"type": "scatter", "name": "up", "x": [1], "y": [1], "marker": {}},
            {"type": "scatter", "name": "down", "x": [-1], "y": [1], "marker": {}},
            {"type": "scatter", "name": "n.s.", "x": [0], "y": [0], "marker": {}},
        ],
        "layout": {"title": "Volcano"},
    }


# --- registry ----------------------------------------------------------------


def test_registry_has_the_five_v1_styles():
    ids = {s["id"] for s in styles.list_styles()}
    assert ids == {"selom", "nature", "cell", "science", "grayscale"}


def test_get_style_resolves_and_defaults():
    assert styles.get_style("nature").id == "nature"
    assert styles.get_style("does-not-exist").id == styles.DEFAULT_STYLE  # unknown → default
    assert styles.get_style(None).id == "selom"


# --- transform ---------------------------------------------------------------


def test_nature_tokens_land():
    out = theme.apply(_base_fig(), "some_skill", "nature")
    nat = styles.get_style("nature")
    assert out["layout"]["font"]["family"] == nat.font_family
    assert out["layout"]["colorway"] == nat.colorway
    assert out["layout"]["font"]["color"] == nat.ink


def test_grayscale_palette_and_volcano():
    out = theme.apply(_volcano_fig(), "volcano", "grayscale")
    gs = styles.get_style("grayscale")
    assert out["layout"]["colorway"] == gs.colorway
    by_name = {t.get("name"): t for t in out["data"]}
    assert by_name["up"]["marker"]["color"] == gs.volcano["up"]
    assert by_name["down"]["marker"]["color"] == gs.volcano["down"]


def test_style_switch_round_trips():
    # selom -> nature -> selom must restore the selom tokens (re-application safe).
    selom = styles.get_style("selom")
    once = theme.apply(_base_fig(), "skill", "selom")
    via_nature = theme.apply(once, "skill", "nature")
    back = theme.apply(via_nature, "skill", "selom")
    assert back["layout"]["font"]["family"] == selom.font_family
    assert back["layout"]["colorway"] == selom.colorway
    assert back["layout"]["font"]["color"] == selom.ink


def test_apply_is_non_destructive_to_input():
    fig = _base_fig()
    before = copy.deepcopy(fig)
    theme.apply(fig, "skill", "nature")
    assert fig == before  # the transform works on a copy; the input spec is untouched


# --- API ---------------------------------------------------------------------


def test_styles_endpoint():
    r = client.get("/figures/styles")
    assert r.status_code == 200
    ids = {s["id"] for s in r.json()["styles"]}
    assert "nature" in ids and "grayscale" in ids


def test_style_apply_endpoint():
    r = client.post("/figures/style/apply", json={"figure": _base_fig(), "skill_id": "x", "style": "cell"})
    assert r.status_code == 200
    assert r.json()["figure"]["layout"]["font"]["family"] == styles.get_style("cell").font_family


def test_style_apply_rejects_bad_figure():
    assert client.post("/figures/style/apply", json={"figure": {"nope": 1}}).status_code == 400


# --- Phase F2: the ported cnsplots styling values (docs/cnsplots-port/parity-audit.md §3) -------


def test_default_style_carries_the_ported_furniture():
    """The rows the audit marked PORT are style TOKENS, so one edit restyles all 36 skills."""
    st = styles.get_style("selom")
    assert st.force_grid is False           # row 5 — publication default is gridless
    assert st.title_weight == "bold"        # row 1
    assert st.size_title == 14              # row 3 — the title:tick ramp was 1.45x
    assert st.axis_width < 1.0              # row 6 — cnsplots' spine is 0.5 pt, not 1 px
    assert st.tick_len < 4.0 and st.tick_width < 1.0   # row 7


def test_theme_lands_the_ported_furniture_on_a_figure():
    fig = theme.apply(_base_fig(), "regression")
    lay = fig["layout"]
    assert lay["title"]["font"]["weight"] == "bold"
    for axis in ("xaxis", "yaxis"):
        assert lay[axis]["showgrid"] is False
        assert lay[axis]["linewidth"] == styles.get_style("selom").axis_width
        assert lay[axis]["ticklen"] == styles.get_style("selom").tick_len
        # a gridless axis must not carry grid paint it will never use
        assert "gridcolor" not in lay[axis]


def test_diverging_matrices_put_high_values_at_the_RED_end():
    """Row 15. The skills hard-coded RdBu + reversescale, which reads HIGH as blue — backwards
    from the genomics convention for an expression z-score."""
    fig = theme.apply(
        {"data": [{"type": "heatmap", "z": [[-1, 1]], "colorscale": "RdBu",
                   "reversescale": True, "zmid": 0}], "layout": {}},
        "heatmap",
    )
    trace = fig["data"][0]
    assert "reversescale" not in trace
    assert trace["colorscale"] == styles.get_style("selom").diverging


def test_diverging_marker_matrices_are_covered_too():
    """`cepo` draws its diverging scores as a DOT matrix, so the midpoint is marker.cmid."""
    fig = theme.apply(
        {"data": [{"type": "scatter", "mode": "markers", "x": [1], "y": [1],
                   "marker": {"color": [0.5], "colorscale": "RdBu", "reversescale": True,
                              "cmid": 0}}], "layout": {}},
        "cepo",
    )
    marker = fig["data"][0]["marker"]
    assert "reversescale" not in marker
    assert marker["colorscale"] == styles.get_style("selom").diverging


def test_categorical_annotation_strips_keep_their_own_scale():
    """A clustermap's category strips are heatmaps with NO midpoint and a deliberate stepwise
    scale. Restyling them would destroy the category encoding."""
    strip = {"type": "heatmap", "z": [[0, 1]], "colorscale": [[0, "#aaa"], [1, "#bbb"]],
             "zmin": -0.5, "zmax": 1.5}
    fig = theme.apply({"data": [strip], "layout": {}}, "heatmap")
    assert fig["data"][0]["colorscale"] == [[0, "#aaa"], [1, "#bbb"]]
