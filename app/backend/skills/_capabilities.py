"""Central per-skill editing-capability stamp (docs/figure-data-capabilities/generalization-spec.md §C).

Injected once in ``theme.apply`` so the per-figure ``meta.selom.capabilities`` contract isn't scattered
across skill runners. Render-inert: Plotly ignores ``layout.meta``; this drives the editor's tools +
gestures, not pixels. Only skills with a profile here are stamped; a skill that already carries a
richer stamp (e.g. an ERG trace grid, stamped figure-instance-aware by ``_tracegrid``) is never
clobbered. The FE resolves the contract in ``lib/figure-model.ts::deriveFigureModel``.
"""

from __future__ import annotations

# skill_id -> the capability block merged into ``layout.meta.selom.capabilities``.
_PROFILES: dict[str, dict] = {
    # Volcano: a stray plot-area drag must not box-zoom (global no-op — declared for self-documentation,
    # redundant with the FE global flip); the FC / p-value threshold lines are directly draggable (the
    # editor re-buckets every point live client-side, ONE re-run commits the DE table + labels); and any
    # plotted point can be CLICK-LABELLED with its gene symbol (an instant annotation, no re-run —
    # generalization-spec §H; the gene symbols ride each point's ``customdata``).
    "volcano": {
        "gesture": {"default": "none", "zoomTools": True, "scrollZoom": False},
        "tools": {"thresholds": True, "geneLabels": True},
    },
    # Heatmap: the diverging colour scale is directly re-tonable — drag the colour bar (top → zmax,
    # bottom → zmin, middle → zmid) or the Style midpoint/saturation sliders re-tone the existing
    # z-matrix LIVE (an instant figure-store edit, undoable, NO re-run; the genes/clustering change
    # stays a staged re-run). heatmap-spec.md.
    "heatmap": {
        "gesture": {"default": "none", "zoomTools": True, "scrollZoom": False},
        "tools": {"heatmapTones": True},
    },
}


def stamp(spec: dict, skill_id: str) -> dict:
    """Merge ``skill_id``'s capability profile into ``spec`` (in place) and return it.

    No-op when the skill has no profile or the spec is malformed. An existing block at a given key
    wins (``setdefault``) — a richer per-figure stamp (ERG) is authoritative and never overwritten.
    """
    profile = _PROFILES.get(skill_id)
    if not profile or not isinstance(spec, dict):
        return spec
    layout = spec.get("layout")
    if not isinstance(layout, dict):
        return spec
    caps = layout.setdefault("meta", {}).setdefault("selom", {}).setdefault("capabilities", {})
    if not isinstance(caps, dict):
        return spec
    for key, value in profile.items():
        caps.setdefault(key, value)
    return spec
