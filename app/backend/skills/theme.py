"""Selom publication theme — one look across every skill's Plotly spec.

Applied centrally in ``contract.run_skill`` so every execution path (sync API,
async jobs, goldens) emits the same publication-grade figure. Pure dict
transforms over the spec — touches only styling (layout, fonts, palette, marker/
line style), never the data arrays, so figures stay fully editable Plotly specs.

The look is parametrized by a **style** (``skills.styles``): a named token pack
(font, palette, ink/grid/axis colours, weights, title alignment). ``theme.apply``
takes a style id and reads its tokens, so the same transform can render a figure
in any installed journal style; ``"selom"`` (the default) reproduces the original
hard-coded look byte-for-byte. Base styling lands on every figure; figure-type
polish is dispatched by skill id (``_KIND``). Unknown skills get base only.
"""
import copy

from skills.styles import DEFAULT_STYLE, get_style

# Render-cache version (Task C2). The figure-envelope cache keys on
# ``(source hash, skill_id, style, THEME_VERSION)``; bump this whenever the theme transform or the
# style tokens change so every cached envelope misses cleanly — the same discipline as a skill's
# ``version`` invalidating the C1 compute cache. ``apply`` itself is unaffected.
THEME_VERSION = "2"  # F2: ported cnsplots styling values + the matrix kind

# skill id -> figure-type polish
_KIND = {
    "volcano": "volcano",
    "umap_scrna": "embedding",
    "annotate": "embedding",
    "trajectory": "trajectory",
    "upset": "upset",
    "normalization_qc": "qc",
    "erg_traces": "trace_grid",
    "heatmap": "matrix",
    "corr_heatmap": "matrix",
    "cepo": "matrix",
    "confusion": "matrix",
    # A Venn has no axes to style — the circles ARE the coordinate system, and its
    # x/y ranges exist only to hold the geometry. Same axis-less treatment as a trace grid.
    "venn": "axisless",
}

# Render-inert figure tag (``layout.meta.selom.figureKind``, set by primitives like
# ``_tracegrid.grid_spec``) → theme kind. Preferred over ``_KIND`` so a skill that emits DIFFERENT
# figure kinds per view (e.g. ``erg_flicker``: a trace grid for the waveform view, a plain
# axes-bearing line for the summary view) is themed by what it actually produced, not by its id.
# Backward-compatible: ``erg_traces`` is already tagged ``trace_grid`` and also maps there in
# ``_KIND``, so existing goldens are unchanged.
_FIGUREKIND_TO_KIND = {"trace_grid": "trace_grid"}


def _declared_scale(trace):
    """A trace's self-declared colour-scale family (``meta.selom.scale``), or None.

    Render-inert (Plotly ignores ``meta``), and read in preference to guessing from the trace's
    shape — see :func:`_style_matrix`."""
    try:
        return trace["meta"]["selom"]["scale"]
    except (KeyError, TypeError):
        return None


def _tagged_kind(spec):
    try:
        return _FIGUREKIND_TO_KIND.get(spec["layout"]["meta"]["selom"]["figureKind"])
    except (KeyError, TypeError):
        return None


# ---- axis / base -------------------------------------------------------------
def _axis(st, grid=True):
    ax = dict(
        showline=True, linecolor=st.axis, linewidth=st.axis_width, mirror=False,
        ticks="outside", tickcolor=st.axis, ticklen=st.tick_len, tickwidth=st.tick_width,
        tickfont=dict(size=st.size_tick, color=st.ink),
        zeroline=False, showgrid=grid,
    )
    if grid:
        ax["gridcolor"] = st.grid
        ax["gridwidth"] = 1
    return ax


def _style_axis(st, orig, grid=True):
    """Restyle an axis, preserving its title text and any explicit range/type."""
    orig = dict(orig or {})
    title = orig.get("title")
    keep = {k: orig[k] for k in ("range", "type", "scaleanchor", "scaleratio", "domain", "anchor",
                                 "categoryorder", "categoryarray", "side",
                                 # explicit tick + range specs a skill set deliberately (e.g. a bar
                                 # chart's category tick labels, a zero-pinned axis) — preserve them
                                 # so base theming restyles the axis without discarding its structure.
                                 # `automargin` keeps long category labels (gene / pathway / gene-set
                                 # names on heatmaps) from clipping — the skill opts in, theming kept it.
                                 "tickmode", "tickvals", "ticktext", "tickangle", "rangemode",
                                 "automargin") if k in orig}
    new = _axis(st, grid=grid)
    new.update(keep)
    tfont = dict(size=st.size_axis_title, color=st.ink_strong)
    if isinstance(title, dict):
        new["title"] = {**title, "font": tfont}
    elif isinstance(title, str):
        new["title"] = dict(text=title, font=tfont)
    return new


def _apply_base(st, spec, grid=True):
    lay = spec.setdefault("layout", {})
    lay["font"] = dict(family=st.font_family, size=st.size_base, color=st.ink)
    lay["paper_bgcolor"] = st.paper
    lay["plot_bgcolor"] = st.paper
    lay["colorway"] = list(st.colorway)
    lay["hoverlabel"] = dict(font=dict(family=st.font_family, size=12), bgcolor=st.ink_strong)
    lay.setdefault("margin", dict(t=46, r=24, b=52, l=64))
    t = lay.get("title")
    tfont = dict(family=st.font_family, size=st.size_title, color=st.ink_strong,
                 weight=st.title_weight)
    tx, txa = (0.01, "left") if st.title_align == "left" else (0.5, "center")
    if isinstance(t, dict):
        lay["title"] = {**t, "font": tfont, "x": tx, "xanchor": txa}
    elif isinstance(t, str):
        lay["title"] = dict(text=t, font=tfont, x=tx, xanchor=txa)
    lg = lay.get("legend", {})
    # Legend density (audit row 11). cnsplots shrinks its legend markers (markerscale 0.5) and
    # tightens the handles so the key costs the plot as little width as possible; Plotly's levers
    # are itemwidth (the marker+gap column) and tracegroupgap. `itemsizing` is deliberately NOT set
    # here — a figure whose legend IS the size key (enrichment) sets it itself and must win.
    lay["legend"] = {**{"itemwidth": 30, "tracegroupgap": 6}, **lg,
                     "font": dict(size=st.size_legend, color=st.ink),
                     "bgcolor": "rgba(0,0,0,0)", "bordercolor": "rgba(0,0,0,0)"}
    for k in ("xaxis", "yaxis"):
        if k in lay:
            lay[k] = _style_axis(st, lay[k], grid=grid)
    return spec


# ---- figure-type polish ------------------------------------------------------
def _style_volcano(st, spec, grid=True):
    _apply_base(st, spec, grid=grid)
    for tr in spec["data"]:
        nm = tr.get("name")
        if nm in st.volcano:
            mk = tr.setdefault("marker", {})
            mk["color"] = st.volcano[nm]
            if nm == "n.s.":
                mk["size"] = 4.5
                mk["opacity"] = 0.45
            else:
                mk["size"] = 6.5
                mk["opacity"] = 0.85
                mk["line"] = dict(width=0)
        if tr.get("mode") == "text":
            tr["textfont"] = dict(family=st.font_family, size=st.size_text, color=st.ink_strong)
            tr.setdefault("textposition", "top center")
    for sh in spec.get("layout", {}).get("shapes", []):
        sh["line"] = dict(color="#b3bcc6", width=1, dash="dash")
        sh["opacity"] = 0.9
    return spec


def _style_embedding(st, spec, pseudotime=False):
    """UMAP/trajectory: square embedding, subdued backbone, crisp cells."""
    _apply_base(st, spec, grid=False)
    def _is_backbone(tr):
        # a straight "lines" trace is a PAGA edge to demote; a spline is a lineage curve to keep
        return tr.get("mode") == "lines" and tr.get("line", {}).get("shape") != "spline"

    widths = [tr.get("line", {}).get("width") for tr in spec["data"]
              if _is_backbone(tr) and tr.get("line", {}).get("width")]
    wmax = max(widths) if widths else 1.0
    for tr in spec["data"]:
        if _is_backbone(tr):  # PAGA edge -> faint thin backbone
            w = tr.get("line", {}).get("width", 1.0)
            tr["line"] = dict(color="#aeb7c2", width=round(0.6 + (w / wmax) * 2.0, 2))
            tr["opacity"] = 0.5
            tr["hoverinfo"] = "skip"
            tr["showlegend"] = False
        elif tr.get("type") in ("scatter", "scattergl"):
            mk = tr.get("marker")
            if isinstance(mk, dict) and "color" in mk:
                mk["size"] = 5
                mk["opacity"] = 0.9
                if mk.get("colorbar") is not None or pseudotime:
                    mk["colorscale"] = mk.get("colorscale", st.sequential)
                    mk["colorbar"] = dict(
                        title=dict(text="pseudotime", font=dict(size=11, color=st.ink_strong)),
                        thickness=12, len=0.55, outlinewidth=0,
                        tickfont=dict(size=10, color=st.ink), ypad=0,
                    )
    lay = spec["layout"]
    lay.setdefault("xaxis", {})
    lay.setdefault("yaxis", {})
    lay["yaxis"]["scaleanchor"] = "x"
    lay["yaxis"]["scaleratio"] = 1
    lay["xaxis"].setdefault("title", dict(text="UMAP 1"))
    lay["yaxis"].setdefault("title", dict(text="UMAP 2"))
    return spec


def _style_matrix(st, spec):
    """Diverging matrices — expression z-scores, sample correlation, stability scores.

    Two things a matrix figure needs and did not have: no grid (it is a filled surface, so a grid
    can only be drawn *through* the data), and the style's diverging scale rather than a per-skill
    one. `heatmap`, `corr_heatmap` and `cepo` each hard-coded ``RdBu`` + ``reversescale`` — which
    put HIGH values at the blue end, backwards from the genomics convention (audit row 15).

    Only the midpoint declaration marks a trace as diverging — ``zmid`` on a heatmap, ``cmid`` on a
    coloured marker (``cepo`` draws its diverging DS scores as a dot matrix, not a filled one). The
    clustermap's categorical annotation strips are heatmaps too, but they carry ``zmin``/``zmax``
    with a stepwise scale and NO midpoint, so their colours are left alone.
    """
    _apply_base(st, spec, grid=False)
    for tr in spec["data"]:
        if tr.get("type") == "heatmap" and "zmid" in tr:
            tr["colorscale"] = st.diverging
            tr.pop("reversescale", None)
        # A COUNT matrix (confusion) is sequential: it has a floor at zero and no midpoint, so the
        # diverging ramp would invent one and paint "few" and "many" as two opposed directions. It
        # DECLARES itself rather than being inferred from "has zmin but no zmid" — the clustermap's
        # categorical annotation strips match that description exactly and must keep the stepwise
        # scale the docstring below protects.
        if tr.get("type") == "heatmap" and _declared_scale(tr) == "sequential":
            tr["colorscale"] = st.sequential
        marker = tr.get("marker")
        if isinstance(marker, dict) and "cmid" in marker:
            marker["colorscale"] = st.diverging
            marker.pop("reversescale", None)
    return spec


def _style_upset(st, spec):
    """UpSet: base styling, but the shared intersection axis stays label-free — the
    dot-matrix below it identifies each column, so x ticks would only add noise."""
    _apply_base(st, spec, grid=False)
    x = spec["layout"].get("xaxis", {})
    x.update(showticklabels=False, ticks="", showline=False)
    spec["layout"]["xaxis"] = x
    return spec


def _style_trace_grid(st, spec):
    """Axis-less small-multiples (ERG trace grid): base font/colour/title, but EVERY
    per-panel axis stays hidden. Unlike ``_apply_base`` we must not restyle the bare
    ``xaxis``/``yaxis`` (the first panel) into a visible axis — the scale bar is the
    only axis cue. Scale-bar shapes + label annotations are left as the primitive set them."""
    return _style_axisless(st, spec, margin=dict(t=10, r=10, b=10, l=10))


def _style_axisless(st, spec, margin):
    """Shared body for figures that carry NO axes — a trace grid, a Venn.

    The distinction from ``_apply_base`` is that it must not build a styled axis at all:
    ``_style_axis`` copies only a keep-list of keys, which would drop ``visible: False``
    and paint a spine/ticks straight through a diagram that has no coordinate meaning.
    Everything the skill set on its axes (ranges, ``scaleanchor``) survives untouched.
    """
    lay = spec.setdefault("layout", {})
    lay["font"] = dict(family=st.font_family, size=st.size_base, color=st.ink)
    lay["paper_bgcolor"] = st.paper
    lay["plot_bgcolor"] = st.paper
    lay["colorway"] = list(st.colorway)
    lay.setdefault("margin", margin)
    t = lay.get("title")
    tfont = dict(family=st.font_family, size=st.size_title, color=st.ink_strong)
    tx, txa = (0.01, "left") if st.title_align == "left" else (0.5, "center")
    if isinstance(t, dict):
        lay["title"] = {**t, "font": tfont, "x": tx, "xanchor": txa}
    elif isinstance(t, str):
        lay["title"] = dict(text=t, font=tfont, x=tx, xanchor=txa)
    for k in list(lay):
        if k.startswith(("xaxis", "yaxis")):
            lay[k]["visible"] = False
    for ann in lay.get("annotations", []):
        ann.setdefault("font", {}).setdefault("family", st.font_family)
    return spec


# ---- public entrypoint -------------------------------------------------------
def apply(spec, skill_id, style=DEFAULT_STYLE):
    """Return a themed copy of a Plotly figure spec for ``skill_id`` in ``style``."""
    if not isinstance(spec, dict) or "data" not in spec:
        return spec
    st = get_style(style)
    spec = copy.deepcopy(spec)
    kind = _tagged_kind(spec) or _KIND.get(skill_id, "base")
    themed = _theme_for_kind(st, spec, kind)
    # Central per-skill editing-capability stamp (generalization-spec §C): render-inert; fills only
    # skills with a profile (e.g. volcano), never clobbers a richer existing stamp (ERG trace grids).
    from skills import _capabilities

    return _capabilities.stamp(themed, skill_id)


def render(spec, skill_id, style=DEFAULT_STYLE, source_key=None):
    """Cached :func:`apply` — the figure-envelope (render) tier of the source/render split (C2).

    The C1 compute cache holds the *pre-theme* source; this caches the *themed* figure keyed by
    ``(source identity, skill_id, style, THEME_VERSION)``. Consequences:
      * a theme/style change re-renders from the cached source **without re-running the skill**
        (the skill compute and the theming are now two separately-keyed cache tiers),
      * a repeat render of the same source+style is a cache hit (no re-theme).

    ``source_key`` lets the ``_execute`` path pass the compute key it already has (so a large source
    figure isn't re-hashed); ``/figures/style/apply`` omits it and the figure is hashed by content.
    Falls straight through to :func:`apply` when the cache is disabled (tests / forced cold) or the
    input isn't a themable spec — so behaviour is identical to calling ``apply`` directly."""
    from skills import _result_cache

    cache = _result_cache.get_cache()
    if not cache.enabled or not isinstance(spec, dict) or "data" not in spec:
        return apply(spec, skill_id, style)
    key = _result_cache.render_key(
        source_key if source_key is not None else spec, skill_id or "", style, THEME_VERSION
    )
    cached = cache.fetch(key)
    if cached is not None:
        return cached["figure"]
    themed = apply(spec, skill_id, style)
    cache.put(key, {"figure": themed})
    return themed


def _theme_for_kind(st, spec, kind):
    """Dispatch a deep-copied spec to its figure-type styler (one return surface for ``apply``)."""
    if kind == "volcano":
        grid = True if st.force_grid is None else st.force_grid
        return _style_volcano(st, spec, grid=grid)
    if kind == "embedding":
        return _style_embedding(st, spec, pseudotime=False)
    if kind == "trajectory":
        return _style_embedding(st, spec, pseudotime=True)
    if kind == "matrix":
        return _style_matrix(st, spec)
    if kind == "upset":
        return _style_upset(st, spec)
    if kind == "qc":
        # multi-panel QC violins: gridless to match the secondary panels theme skips
        return _apply_base(st, spec, grid=False)
    if kind == "trace_grid":
        return _style_trace_grid(st, spec)
    if kind == "axisless":
        # Roomier margin than a trace grid: a Venn's outer set names sit beyond the circles.
        return _style_axisless(st, spec, margin=dict(t=60, r=30, b=30, l=30))
    grid = True if st.force_grid is None else st.force_grid
    return _apply_base(st, spec, grid=grid)
