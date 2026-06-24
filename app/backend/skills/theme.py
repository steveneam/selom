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

# skill id -> figure-type polish
_KIND = {
    "volcano": "volcano",
    "umap_scrna": "embedding",
    "annotate": "embedding",
    "trajectory": "trajectory",
    "upset": "upset",
    "normalization_qc": "qc",
    "erg_traces": "trace_grid",
}

# Render-inert figure tag (``layout.meta.selom.figureKind``, set by primitives like
# ``_tracegrid.grid_spec``) → theme kind. Preferred over ``_KIND`` so a skill that emits DIFFERENT
# figure kinds per view (e.g. ``erg_flicker``: a trace grid for the waveform view, a plain
# axes-bearing line for the summary view) is themed by what it actually produced, not by its id.
# Backward-compatible: ``erg_traces`` is already tagged ``trace_grid`` and also maps there in
# ``_KIND``, so existing goldens are unchanged.
_FIGUREKIND_TO_KIND = {"trace_grid": "trace_grid"}


def _tagged_kind(spec):
    try:
        return _FIGUREKIND_TO_KIND.get(spec["layout"]["meta"]["selom"]["figureKind"])
    except (KeyError, TypeError):
        return None


# ---- axis / base -------------------------------------------------------------
def _axis(st, grid=True):
    ax = dict(
        showline=True, linecolor=st.axis, linewidth=1, mirror=False,
        ticks="outside", tickcolor=st.axis, ticklen=4, tickwidth=1,
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
    tfont = dict(family=st.font_family, size=st.size_title, color=st.ink_strong)
    tx, txa = (0.01, "left") if st.title_align == "left" else (0.5, "center")
    if isinstance(t, dict):
        lay["title"] = {**t, "font": tfont, "x": tx, "xanchor": txa}
    elif isinstance(t, str):
        lay["title"] = dict(text=t, font=tfont, x=tx, xanchor=txa)
    lg = lay.get("legend", {})
    lay["legend"] = {**lg, "font": dict(size=st.size_legend, color=st.ink),
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
    lay = spec.setdefault("layout", {})
    lay["font"] = dict(family=st.font_family, size=st.size_base, color=st.ink)
    lay["paper_bgcolor"] = st.paper
    lay["plot_bgcolor"] = st.paper
    lay["colorway"] = list(st.colorway)
    lay.setdefault("margin", dict(t=10, r=10, b=10, l=10))
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


def _theme_for_kind(st, spec, kind):
    """Dispatch a deep-copied spec to its figure-type styler (one return surface for ``apply``)."""
    if kind == "volcano":
        grid = True if st.force_grid is None else st.force_grid
        return _style_volcano(st, spec, grid=grid)
    if kind == "embedding":
        return _style_embedding(st, spec, pseudotime=False)
    if kind == "trajectory":
        return _style_embedding(st, spec, pseudotime=True)
    if kind == "upset":
        return _style_upset(st, spec)
    if kind == "qc":
        # multi-panel QC violins: gridless to match the secondary panels theme skips
        return _apply_base(st, spec, grid=False)
    if kind == "trace_grid":
        return _style_trace_grid(st, spec)
    grid = True if st.force_grid is None else st.force_grid
    return _apply_base(st, spec, grid=grid)
