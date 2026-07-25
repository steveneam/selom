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
    comp, compensated = _compensate(raw, fd, labels, params, np, flowutils)

    ts, xform_meta = _resolve_transform(fd, labels, params)
    disp = _transform_all(comp, params, ts, np, flowutils)  # transformed display + gate space

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

    gates, dropped = _flow.parse_gates(params.get("gates", ""), x_label, y_label)
    shapes, annos = _flow.gate_shapes(gates, x_label, y_label)
    if shapes:
        layout["shapes"] = shapes
    if annos:
        layout["annotations"] = annos

    # Declare what compensation ACTUALLY happened, so the auto-methods text states the outcome
    # instead of restating the request. `compensate=auto` degrades to raw events whenever the FCS
    # carries no $SPILLOVER, the spill string is malformed, or its detectors/shape do not match the
    # channels (see _compensate) — claiming a spillover matrix was applied in that case is a
    # printed-vs-computed lie (milestone review 2026-07-25, finding A6). Written always (not only on
    # failure): a reader of the recorded figure can then tell compensated from uncompensated.
    #
    # `transform` is the same honesty channel for the GATE SPACE (A15): the resolved per-channel t
    # and where it came from. Gate bounds travel in transformed display space, so without the
    # resolved t the numbers in the table cannot be recomputed or audited, and a gate drawn on one
    # export is not portable to a re-acquisition of the same panel.
    layout["meta"] = {**(layout.get("meta") or {}),
                      "compensation_applied": bool(compensated),
                      "transform": xform_meta}

    rows = _gating_rows(gates, disp, comp, idx, xi, yi, np)
    rows += _dropped_rows(dropped)
    # A16: any gate that PARSED but could not be evaluated (a channel the FCS doesn't carry) is
    # already carried as a verdict row by _gating_rows. Nothing the operator defined vanishes.
    unresolved = [r for r in rows if r.get("status") not in (None, _flow.GATE_STATUS_OK)]
    if unresolved:
        layout["meta"]["gates_unresolved"] = [
            {"population": r["population"], "reason": r["status"]} for r in unresolved]

    spec = {"data": [trace], "layout": layout,
            "table": _flow.population_table(rows, x_label, y_label,
                                            title="Population statistics")}
    return jsonable(spec)


def _dropped_rows(dropped):
    """A verdict ROW per gate the parser dropped — never a vanished population (A16)."""
    return [{"population": d["label"], "parent": None, "count": None,
             "pct_parent": None, "pct_total": None, "mfi_x": None, "mfi_y": None,
             "status": d["reason"]} for d in dropped]


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


# The GatingML transform's ``t`` (the top of scale) used to be derived from the DATA:
# ``t_top = max(1, max|comp|)``, one scalar for every channel. Gate bounds travel in transformed
# display space, so the meaning of a saved gate depended on an extremum of the specific event array
# — one saturating event shifted the whole transform and therefore every count, %-parent and MFI in
# the table — and the resolved value was never recorded, so the numbers could not be recomputed or
# audited and a gate was not portable to a re-acquisition of the same panel (A15). The docstring's
# claim that this was "the same single t_top FlowKit's per-run transform used" was also wrong:
# FlowKit derives ``t`` from the FCS ``$PnR`` range keyword, PER CHANNEL.
#
# So ``t`` is now anchored to METADATA, resolved in this order and always recorded:
#   1. the explicit ``transform_t`` param (> 0)  — an operator pinning the gate space,
#   2. each channel's ``$PnR`` from the FCS      — what the acquisition itself declares,
#   3. _DEFAULT_T                                — a fixed, reproducible 18-bit top of scale.
# None of the three depends on the events, so the same gate spec reproduces on a re-acquisition.
_DEFAULT_T = 262144.0   # 2^18 — the standard top of scale for an 18-bit acquisition
_LOGICLE_M, _LOGICLE_W, _LOGICLE_A = 4.5, 0.5, 0.0
_LOG_M = 4.5
_ASINH_M = 4.0


def _pnr_by_channel(fd, labels):
    """``$PnR`` (the acquisition's declared top of scale) per channel index, or ``None``.

    ``flowio.FlowData.channels`` is ``{index-as-string: {pnn, pns, pne, png, pnr}}`` — 1-based,
    matching the FCS ``$Pn`` numbering.
    """
    chans = getattr(fd, "channels", None) or {}
    out = [None] * len(labels)
    for key, spec in chans.items():
        try:
            i = int(key) - 1
            r = float((spec or {}).get("pnr"))
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(labels) and math.isfinite(r) and r > 0:
            out[i] = r
    return out


def _resolve_transform(fd, labels, params):
    """``(t_per_channel, provenance)`` — the transform's resolved parameters + where they came from.

    ``provenance`` is what ``layout.meta['transform']`` carries, so a reader of the recorded figure
    can reconstruct the gate space exactly: the transform name, the per-channel ``t`` and its
    source, and the shape parameters (``m``/``w``/``a``, or ``cofactor`` for arcsinh).
    """
    mode = _xform_name(params)
    n = len(labels)
    try:
        pinned = float(params.get("transform_t", 0.0) or 0.0)
    except (TypeError, ValueError):
        pinned = 0.0

    if pinned > 0:
        ts, source, fallback = [pinned] * n, "param", []
    else:
        pnr = _pnr_by_channel(fd, labels)
        ts = [r if r is not None else _DEFAULT_T for r in pnr]
        fallback = [str(labels[i]) for i, r in enumerate(pnr) if r is None]
        source = ("fcs_pnr" if not fallback
                  else "default" if len(fallback) == n else "fcs_pnr+default")

    meta = {
        "name": mode,
        "t_source": source,
        "t_per_channel": {str(lab): float(t) for lab, t in zip(labels, ts)},
        "t_default_channels": fallback,
        "t_default": _DEFAULT_T,
    }
    if mode == "arcsinh":
        # The arcsinh path is anchored to `cofactor`, not to t — say so rather than record a t the
        # computation never used.
        meta["t_source"] = "not_applicable"
        meta["t_per_channel"] = {}
        meta["t_default_channels"] = []
        meta["cofactor"] = float(params.get("cofactor", 150.0) or 150.0)
        meta["m"] = _ASINH_M
    elif mode == "logicle":
        meta["m"], meta["w"], meta["a"] = _LOGICLE_M, _LOGICLE_W, _LOGICLE_A
    elif mode == "log":
        meta["m"] = _LOG_M
    return ts, meta


def _transform_all(comp, params, ts, np, flowutils):
    """Transform EVERY channel into display space with the chosen GatingML transform, so a gate on
    any channel is compared in the same space the plot is drawn in.

    ``ts`` is the per-channel top of scale from :func:`_resolve_transform`. Channels sharing one
    ``t`` (the common case — one acquisition, one ``$PnR``) are transformed in a single call, so
    this is the same work the single-``t_top`` version did."""
    mode = _xform_name(params)
    data = comp.astype(float, copy=True)
    if mode == "arcsinh":
        # GatingML asinh with param_t = cofactor·sinh(m·ln10) reduces to the biologist's
        # normalized cofactor arcsinh, asinh(x / cofactor) / (m·ln10). No `t` involved.
        cofactor = float(params.get("cofactor", 150.0) or 150.0)
        return flowutils.transforms.asinh(data, list(range(comp.shape[1])),
                                          cofactor * math.sinh(_ASINH_M * _LN10), _ASINH_M, 0.0)
    groups: dict[float, list[int]] = {}
    for i, t in enumerate(ts[: comp.shape[1]]):
        groups.setdefault(float(t), []).append(i)
    for t, ci in groups.items():
        if mode == "linear":
            data[:, ci] = data[:, ci] / t
        elif mode == "log":
            data = flowutils.transforms.log(data, ci, t, _LOG_M)
        else:
            data = flowutils.transforms.logicle(data, ci, t=t, m=_LOGICLE_M,
                                                w=_LOGICLE_W, a=_LOGICLE_A)
    return data


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
    space; MFI = median of the COMPENSATED events for the plotted x/y channels.

    A gate that cannot be evaluated gets a ROW with ``count=None`` and a ``status`` naming why,
    never a silent ``continue`` (A16). Two silent drops lived here: a gate naming a channel the FCS
    does not carry, and an unrecognized ``type`` — and, worse, an unresolved PARENT fell back to
    ``all_mask``/``total``, so a child's %-parent was silently computed against ALL events. An
    unresolved gate's descendants are now marked unresolved too."""
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
    unresolved: dict = {}  # gate id -> the reason it (or its ancestor) could not be evaluated

    def _unresolved_row(g, reason):
        unresolved[g["id"]] = reason
        plabel = by_id[g["parent"]]["label"] if g.get("parent") in by_id else "All events"
        return {"population": g["label"], "parent": plabel, "count": None,
                "pct_parent": None, "pct_total": None, "mfi_x": None, "mfi_y": None,
                "status": reason}

    # Parents before children so every nested gate resolves against its parent's mask.
    for g in sorted(gates, key=lambda g: _depth(g, by_id)):
        parent = g.get("parent")
        # An unresolved ancestor makes this gate uncountable. Falling back to the root mask would
        # report a %-parent against ALL events — a wrong number presented as a right one.
        if parent in unresolved:
            rows.append(_unresolved_row(g, _flow.DROP_PARENT_UNRESOLVED))
            continue
        pmask = masks.get(parent, all_mask) if parent else all_mask
        pcount = counts.get(parent, total) if parent else total
        plabel = by_id[parent]["label"] if parent in by_id else "All events"
        cxi, cyi = idx.get(g.get("x")), idx.get(g.get("y"))
        if cxi is None or cyi is None:
            rows.append(_unresolved_row(g, _flow.DROP_CHANNEL_NOT_IN_FCS))
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
            rows.append(_unresolved_row(g, _flow.DROP_UNKNOWN_TYPE))
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
