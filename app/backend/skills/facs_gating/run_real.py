"""Real flow-cytometry engine — FlowIO (FCS reader) + FlowUtils (compensation +
GatingML transforms) + clean-room numpy gating/stats; Plotly for render.

Why not FlowKit: the high-level FlowKit toolkit hard-pins ``pandas<3`` (RISKS #12),
incompatible with this backend's ``pandas>=3.0``. Its genuinely-hard parts, though, are
SEPARATE BSD-3, numpy-only packages that run fine on pandas 3.0 — FCS parsing (FlowIO)
and compensation + the logicle / arcsinh / log transforms (FlowUtils, C-accelerated,
patent-clear). The thin top layer FlowKit adds — a ``GatingStrategy`` over a gate tree
plus a population report — is just geometry + counting, reimplemented here in numpy.
Same clean-room split as Melody ↔ Harmony. Because gate bounds already live in
transformed DISPLAY space (the ``_flow.parse_gates`` contract), membership is a
vectorized comparison / point-in-polygon — no GatingStrategy needed.

Pipeline: ``FlowData(path)`` → compensate (embedded $SPILLOVER / operator matrix / none)
→ transform every channel for display + gating (logicle / arcsinh / log / linear) →
render the chosen Plotly view → evaluate the (nested) rectangle / polygon / quadrant gate
tree → a population StatsTable (count, %parent, %total, median MFI on the compensated
events). The trace, gate shapes and table are assembled by the shared, dependency-free
``skills._flow`` builders, so the wire shape is identical to the stub.
"""
import json
import math

from skills import _flow
from skills._plotly import jsonable

_LN10 = math.log(10.0)


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import flowio
    import flowutils

    fd = flowio.FlowData(str(data_path))
    labels = list(fd.pnn_labels)
    pns = list(fd.pns_labels or [])
    x_label, y_label = _resolve_xy(labels, pns, params)
    if x_label is None or y_label is None:
        raise ValueError("facs_gating: could not resolve x/y channels from the FCS")

    raw = fd.as_array().astype(float)                     # (n_events, n_channels), linear
    comp, _compensated = _compensate(raw, fd, labels, params, np, flowutils)

    t_top = float(max(1.0, float(np.nanmax(np.abs(comp)))))
    disp = _transform_all(comp, params, t_top, np, flowutils)  # transformed display + gate space

    idx = {lab: i for i, lab in enumerate(labels)}
    xi, yi = idx[x_label], idx[y_label]

    # ---- display trace (finite-filtered + down-sampled; gating uses ALL events) ----
    xt, yt = disp[:, xi], disp[:, yi]
    finite = np.isfinite(xt) & np.isfinite(yt)
    xf, yf = xt[finite], yt[finite]
    cap = int(params.get("max_events", 50000) or 50000)
    keep = _subsample_idx(xf.shape[0], cap, np)
    xd, yd = xf[keep].tolist(), yf[keep].tolist()

    plot = str(params.get("plot", "density")).strip().lower()
    bins = int(params.get("bins", 256) or 256)
    trace = _build_trace(plot, xd, yd, bins, np)

    title = f"Flow cytometry — {plot} ({x_label} × {y_label})"
    layout = _flow.figure_layout(plot, x_label, y_label, title, _xform_name(params))

    gates = _flow.parse_gates(params.get("gates", ""), x_label, y_label)
    shapes, annos = _flow.gate_shapes(gates, x_label, y_label)
    if shapes:
        layout["shapes"] = shapes
    if annos:
        layout["annotations"] = annos

    rows = _gating_rows(gates, disp, comp, idx, xi, yi, np)
    spec = {"data": [trace], "layout": layout,
            "table": _flow.population_table(rows, x_label, y_label,
                                            title="Population statistics")}
    return jsonable(spec)


# ---- channels ---------------------------------------------------------------
def _resolve_xy(labels, pns, params):
    x = _flow.resolve_channel(labels, params.get("x_channel", ""), pns)
    y = _flow.resolve_channel(labels, params.get("y_channel", ""), pns)
    if x is None or y is None:
        dx, dy = _flow.default_channels(labels)
        x, y = (x or dx), (y or dy)
    return x, y


# ---- compensation -----------------------------------------------------------
def _compensate(raw, fd, labels, params, np, flowutils):
    """Return ``(events, compensated?)``.

    ``matrix`` = operator JSON (``{"detectors": [...], "matrix": [[...]]}``); ``auto`` =
    the FCS's embedded $SPILLOVER (parsed by FlowUtils); ``none`` = raw. Detector names
    map to event columns by PnN label; a shape/label mismatch degrades to raw (never
    raises). Applies the inverse spillover to the detector columns via FlowUtils.
    """
    mode = str(params.get("compensate", "auto")).strip().lower()
    if mode == "none":
        return raw, False

    detectors, matrix = None, None
    if mode == "matrix":
        spec = params.get("comp_matrix", "")
        spec = spec if isinstance(spec, dict) else (json.loads(spec) if spec else None)
        if isinstance(spec, dict):
            detectors = spec.get("detectors") or spec.get("channels")
            matrix = spec.get("matrix") or spec.get("spill")
    else:  # auto — embedded $SPILL / $SPILLOVER
        spill = fd.text.get("spillover") or fd.text.get("spill") or fd.text.get("$spillover")
        if spill:
            try:
                matrix, detectors = flowutils.compensate.get_spill(spill)
            except Exception:  # noqa: BLE001 — malformed spill string → run uncompensated
                pass

    if not detectors or matrix is None:
        return raw, False
    lab_idx = {str(lab).strip().lower(): i for i, lab in enumerate(labels)}
    cols = [lab_idx.get(str(d).strip().lower()) for d in detectors]
    if any(c is None for c in cols):
        return raw, False
    spill = np.asarray(matrix, dtype=float)
    if spill.shape != (len(cols), len(cols)):
        return raw, False
    comp = flowutils.compensate.compensate(raw.copy(), spill, fluoro_indices=cols)
    return (comp if comp is not None else raw), comp is not None


# ---- transform --------------------------------------------------------------
def _xform_name(params):
    mode = str(params.get("transform", "logicle")).strip().lower()
    return mode if mode in ("logicle", "arcsinh", "log", "linear") else "logicle"


def _transform_all(comp, params, t_top, np, flowutils):
    """Transform EVERY channel into display space with the chosen GatingML transform, so a
    gate on any channel is compared in the same space the plot is drawn in. Uses the same
    single ``t_top`` (global max abs) FlowKit's per-run transform used, so gate bounds keep
    their meaning across engines."""
    mode = _xform_name(params)
    ci = list(range(comp.shape[1]))
    data = comp.astype(float, copy=True)
    if mode == "linear":
        return data / t_top
    if mode == "arcsinh":
        # GatingML asinh with param_t = cofactor·sinh(m·ln10) reduces to the biologist's
        # normalized cofactor arcsinh, asinh(x / cofactor) / (m·ln10).
        cofactor = float(params.get("cofactor", 150.0) or 150.0)
        m = 4.0
        return flowutils.transforms.asinh(data, ci, cofactor * math.sinh(m * _LN10), m, 0.0)
    if mode == "log":
        return flowutils.transforms.log(data, ci, t_top, 4.5)
    return flowutils.transforms.logicle(data, ci, t=t_top, m=4.5, w=0.5, a=0.0)


def _subsample_idx(n, cap, np):
    """Deterministic down-sample to ``cap`` events (evenly-spaced) for a light trace."""
    if n <= cap:
        return np.arange(n)
    return np.linspace(0, n - 1, cap).astype(int)


# ---- trace ------------------------------------------------------------------
def _build_trace(plot, xd, yd, bins, np):
    if plot == "contour":
        return _flow.contour_trace(xd, yd, bins)
    if plot == "histogram":
        return _flow.histogram_trace(xd, bins)
    if plot == "scatter":
        return _flow.scatter_trace(xd, yd, _kde_density(xd, yd, np))
    return _flow.density_trace(xd, yd, bins)


def _kde_density(xd, yd, np):
    """Per-event gaussian-KDE density for the scatter colouring (degrades to flat)."""
    if len(xd) < 3:
        return [0.0] * len(xd)
    try:
        from scipy.stats import gaussian_kde

        pts = np.vstack([xd, yd])
        return gaussian_kde(pts)(pts).tolist()
    except Exception:  # noqa: BLE001 — singular / degenerate spread: flat colour is fine
        return [0.0] * len(xd)


# ---- gating (clean-room, numpy) ---------------------------------------------
def _gating_rows(gates, disp, comp, idx, xi, yi, np):
    """Population rows from a clean-room gate-tree walk, prefixed with the root
    (All events). Gate membership is evaluated over ALL events in transformed display
    space; MFI = median of the COMPENSATED events for the plotted x/y channels."""
    total = int(disp.shape[0])

    def _median(mask, col):
        if mask is None:
            return None
        sel = comp[mask, col]
        return float(np.median(sel)) if sel.size else None

    all_mask = np.ones(total, dtype=bool)
    rows = [{"population": "All events", "parent": None, "count": total,
             "pct_parent": 100.0, "pct_total": 100.0,
             "mfi_x": _median(all_mask, xi), "mfi_y": _median(all_mask, yi)}]
    if not gates:
        return rows

    by_id = {g["id"]: g for g in gates}
    masks: dict = {}   # gate / quadrant id -> boolean membership over all events
    counts: dict = {}
    # Parents before children so every nested gate resolves against its parent's mask.
    for g in sorted(gates, key=lambda g: _depth(g, by_id)):
        parent = g.get("parent")
        pmask = masks.get(parent, all_mask) if parent else all_mask
        pcount = counts.get(parent, total) if parent else total
        plabel = by_id[parent]["label"] if parent in by_id else "All events"
        cxi, cyi = idx.get(g.get("x")), idx.get(g.get("y"))
        if cxi is None or cyi is None:
            continue
        gx, gy = disp[:, cxi], disp[:, cyi]

        if g["type"] == "quadrant":
            xs, ys = g["x_split"], g["y_split"]
            for suf, qm in (("ll", (gx < xs) & (gy < ys)),
                            ("lr", (gx >= xs) & (gy < ys)),
                            ("ul", (gx < xs) & (gy >= ys)),
                            ("ur", (gx >= xs) & (gy >= ys))):
                qid = f'{g["id"]}-{suf}'
                m = qm & pmask
                c = int(m.sum())
                masks[qid], counts[qid] = m, c
                rows.append(_stat_row(qid, plabel, c, pcount, total, _median(m, xi), _median(m, yi)))
            masks[g["id"]], counts[g["id"]] = pmask, pcount   # anchor for any child of the gate
            continue

        if g["type"] == "rect":
            m = _rect_mask(gx, gy, g, np) & pmask
        elif g["type"] == "polygon":
            m = _poly_mask(gx, gy, g["vertices"], np) & pmask
        else:
            continue
        c = int(m.sum())
        masks[g["id"]], counts[g["id"]] = m, c
        rows.append(_stat_row(g["label"], plabel, c, pcount, total, _median(m, xi), _median(m, yi)))
    return rows


def _stat_row(name, parent, count, parent_count, total, mfi_x, mfi_y):
    return {"population": name, "parent": parent, "count": count,
            "pct_parent": (100.0 * count / parent_count) if parent_count else 0.0,
            "pct_total": (100.0 * count / total) if total else 0.0,
            "mfi_x": mfi_x, "mfi_y": mfi_y}


def _rect_mask(gx, gy, g, np):
    """Boolean membership for a rectangle gate; a ``None`` bound is open on that side."""
    m = np.ones(gx.shape[0], dtype=bool)
    if g.get("x_min") is not None:
        m &= gx >= g["x_min"]
    if g.get("x_max") is not None:
        m &= gx <= g["x_max"]
    if g.get("y_min") is not None:
        m &= gy >= g["y_min"]
    if g.get("y_max") is not None:
        m &= gy <= g["y_max"]
    return m


def _poly_mask(gx, gy, verts, np):
    """Vectorized even-odd (ray-casting) point-in-polygon over all events at once."""
    vx = np.asarray([v[0] for v in verts], dtype=float)
    vy = np.asarray([v[1] for v in verts], dtype=float)
    n = len(verts)
    inside = np.zeros(gx.shape[0], dtype=bool)
    j = n - 1
    for i in range(n):
        cond = ((vy[i] > gy) != (vy[j] > gy)) & (
            gx < (vx[j] - vx[i]) * (gy - vy[i]) / (vy[j] - vy[i] + 1e-300) + vx[i])
        inside ^= cond
        j = i
    return inside


def _depth(g, by_id, _guard=0):
    p = g.get("parent")
    if not p or p not in by_id or _guard > 16:
        return 0
    return 1 + _depth(by_id[p], by_id, _guard + 1)
