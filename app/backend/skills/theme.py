"""Selom publication theme — one look across every skill's Plotly spec.

Applied centrally in ``contract.run_skill`` so every execution path (sync API,
async jobs, goldens) emits the same publication-grade figure. Pure dict
transforms over the spec — touches only styling (layout, fonts, palette, marker/
line style), never the data arrays, so figures stay fully editable Plotly specs.

Base styling lands on every figure; figure-type polish is dispatched by skill id
(``_KIND``). Unknown skills get base only.
"""
import copy

# ---- design tokens -----------------------------------------------------------
INK        = "#33404d"   # body text / ticks
INK_STRONG = "#1f2a37"   # titles, axis labels
GRID       = "#eef1f5"
AXIS       = "#c4ccd4"
PAPER      = "#ffffff"

FONT_FAMILY = "Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif"

# curated, colourblind-aware qualitative palette (blue/amber lead)
COLORWAY = ["#2f6db0", "#e08a2b", "#3f9b6b", "#c0392b",
            "#7d5ba6", "#1f9aa6", "#9aa017", "#6b7280"]
SEQUENTIAL = "Viridis"
VOLCANO = {"n.s.": "#cdd4dc", "up": "#c0392b", "down": "#2f6db0"}

# skill id -> figure-type polish
_KIND = {
    "volcano": "volcano",
    "umap_scrna": "embedding",
    "annotate": "embedding",
    "trajectory": "trajectory",
}


# ---- axis / base -------------------------------------------------------------
def _axis(grid=True):
    ax = dict(
        showline=True, linecolor=AXIS, linewidth=1, mirror=False,
        ticks="outside", tickcolor=AXIS, ticklen=4, tickwidth=1,
        tickfont=dict(size=11, color=INK),
        zeroline=False, showgrid=grid,
    )
    if grid:
        ax["gridcolor"] = GRID
        ax["gridwidth"] = 1
    return ax


def _style_axis(orig, grid=True):
    """Restyle an axis, preserving its title text and any explicit range/type."""
    orig = dict(orig or {})
    title = orig.get("title")
    keep = {k: orig[k] for k in ("range", "type", "scaleanchor", "scaleratio", "domain", "anchor") if k in orig}
    new = _axis(grid=grid)
    new.update(keep)
    tfont = dict(size=13, color=INK_STRONG)
    if isinstance(title, dict):
        new["title"] = {**title, "font": tfont}
    elif isinstance(title, str):
        new["title"] = dict(text=title, font=tfont)
    return new


def _apply_base(spec, grid=True):
    lay = spec.setdefault("layout", {})
    lay["font"] = dict(family=FONT_FAMILY, size=13, color=INK)
    lay["paper_bgcolor"] = PAPER
    lay["plot_bgcolor"] = PAPER
    lay["colorway"] = COLORWAY
    lay["hoverlabel"] = dict(font=dict(family=FONT_FAMILY, size=12), bgcolor=INK_STRONG)
    lay.setdefault("margin", dict(t=46, r=24, b=52, l=64))
    t = lay.get("title")
    tfont = dict(family=FONT_FAMILY, size=16, color=INK_STRONG)
    if isinstance(t, dict):
        lay["title"] = {**t, "font": tfont, "x": 0.01, "xanchor": "left"}
    elif isinstance(t, str):
        lay["title"] = dict(text=t, font=tfont, x=0.01, xanchor="left")
    lg = lay.get("legend", {})
    lay["legend"] = {**lg, "font": dict(size=11, color=INK),
                     "bgcolor": "rgba(0,0,0,0)", "bordercolor": "rgba(0,0,0,0)"}
    for k in ("xaxis", "yaxis"):
        if k in lay:
            lay[k] = _style_axis(lay[k], grid=grid)
    return spec


# ---- figure-type polish ------------------------------------------------------
def _style_volcano(spec):
    _apply_base(spec, grid=True)
    for tr in spec["data"]:
        nm = tr.get("name")
        if nm in VOLCANO:
            mk = tr.setdefault("marker", {})
            mk["color"] = VOLCANO[nm]
            if nm == "n.s.":
                mk["size"] = 4.5
                mk["opacity"] = 0.45
            else:
                mk["size"] = 6.5
                mk["opacity"] = 0.85
                mk["line"] = dict(width=0)
        if tr.get("mode") == "text":
            tr["textfont"] = dict(family=FONT_FAMILY, size=10.5, color=INK_STRONG)
            tr.setdefault("textposition", "top center")
    for sh in spec.get("layout", {}).get("shapes", []):
        sh["line"] = dict(color="#b3bcc6", width=1, dash="dash")
        sh["opacity"] = 0.9
    return spec


def _style_embedding(spec, pseudotime=False):
    """UMAP/trajectory: square embedding, subdued backbone, crisp cells."""
    _apply_base(spec, grid=False)
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
                    mk["colorscale"] = mk.get("colorscale", SEQUENTIAL)
                    mk["colorbar"] = dict(
                        title=dict(text="pseudotime", font=dict(size=11, color=INK_STRONG)),
                        thickness=12, len=0.55, outlinewidth=0,
                        tickfont=dict(size=10, color=INK), ypad=0,
                    )
    lay = spec["layout"]
    lay.setdefault("xaxis", {})
    lay.setdefault("yaxis", {})
    lay["yaxis"]["scaleanchor"] = "x"
    lay["yaxis"]["scaleratio"] = 1
    lay["xaxis"].setdefault("title", dict(text="UMAP 1"))
    lay["yaxis"].setdefault("title", dict(text="UMAP 2"))
    return spec


# ---- public entrypoint -------------------------------------------------------
def apply(spec, skill_id):
    """Return a themed copy of a Plotly figure spec for ``skill_id``."""
    if not isinstance(spec, dict) or "data" not in spec:
        return spec
    spec = copy.deepcopy(spec)
    kind = _KIND.get(skill_id, "base")
    if kind == "volcano":
        return _style_volcano(spec)
    if kind == "embedding":
        return _style_embedding(spec, pseudotime=False)
    if kind == "trajectory":
        return _style_embedding(spec, pseudotime=True)
    return _apply_base(spec)
