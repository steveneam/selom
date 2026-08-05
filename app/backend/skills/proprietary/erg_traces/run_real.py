"""Real ERG trace grid: read a long ERG waveform table and render the chosen
representatives through the generic trace-grid primitive.

Input CSV columns (canonical ``erg_waveforms_long``): ``condition``, ``intensity_group``,
``time_ms``, ``voltage_uv`` (required); ``condition_order``, ``intensity_log_cd_s_m2``,
``role`` (optional but used). Each (condition × intensity) trace is cleaned ("clean flats,
keep OPs") and an a/b-wave table is attached (native — Pillar 1).
"""
from skills import _erg
from skills._engine import to_bool
from skills._plotly import jsonable
from skills._table import table
from skills._tracegrid import grid_spec

_REQUIRED = {"condition", "intensity_group", "time_ms", "voltage_uv"}


def _filter_mode(df, params):
    """Multi-mode exports (Diagnosys) carry scotopic + photopic + flicker steps, each with its own
    per-mode intensity groups — so a single trace grid must render ONE mode or the intensity rows
    collide. Resolve the flash mode from the friendly ``adaptation`` hint (or explicit
    ``stimulus_type``) and keep those rows. Returns ``(df, adaptation_label)``. A no-op when there
    is no ``stimulus_type`` column (the iWorx path) — so that path is unchanged."""
    if "stimulus_type" not in df.columns:
        return df, ""
    present = [s for s in df["stimulus_type"].dropna().astype(str).unique() if s]
    pick, adapt = _erg.resolve_flash_mode(
        present, params.get("adaptation", "auto"), params.get("stimulus_type", ""))
    if pick:
        sub = df[df["stimulus_type"].astype(str) == pick]
        if not sub.empty:
            return sub, adapt
    return df, adapt


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    df = pd.read_csv(data_path)
    missing = _REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"erg_traces: input missing required columns {sorted(missing)}")

    df, adapt = _filter_mode(df, params)
    # Landmark mode for the a/b table: cone (photopic) windows when the data/param says photopic,
    # else scotopic. `adapt` reflects the stimulus_type filter when that column is present; else fall
    # back to the user's adaptation/stimulus_type hint (a plain waveform CSV with no such column).
    # The adaptation this figure CLAIMS (title + methods paragraph) — and, here, the landmark mode.
    # Under `adaptation="auto"` it is resolved from the DATA, which no parameter can tell the prose,
    # so it is recorded below when it differs from the param-derived answer (default run unchanged).
    param_mode = _erg.adaptation_mode(params.get("adaptation", "auto"), params.get("stimulus_type", ""))
    metric_mode = adapt or param_mode
    # Operator-set landmark marks (docs/records/erg-manual-marks/spec.md). The trace grid is the primary
    # authoring surface: a per-panel mark is keyed by (condition, "", intensity_group, "") — empty
    # stimulus/eye, so it also drives the per-eye bar + intensity-response via the wildcard match.
    manual_marks = _erg.parse_manual_marks(params.get("manual_marks", ""))
    # a/b auto-seed detector: `windowed` (default, byte-identical) or the opt-in `robust` SavGol +
    # prominence detector with a pre-stimulus noise gate. Only changes the auto seed times/amplitudes.
    ab_detector = str(params.get("ab_detector", "windowed")).strip().lower()
    # Show the a/b landmark dots on each panel (R4). Default off → the real figure is visually
    # unchanged; the editor flips this on to drag/confirm marks. The `mark_meta` (render-inert) is
    # emitted regardless so the Marks panel can list segments + auto times without the dots showing.
    show_marks = to_bool(params.get("marks", False))
    # Pinned a/b labels on the dots (figure-data-capabilities §6). Default on; a clean export can
    # hide them (legend-only) without removing the dots.
    show_labels = to_bool(params.get("mark_labels", True))
    # Inner-retinal metrics (L1-09). The measurements shipped in `a84636c` with no surface at all —
    # shipped-not-reachable. Both default OFF, so the figure, its table and its golden are unchanged
    # unless asked for; each adds columns to the ALREADY-ATTACHED statistics table (no new output).
    # An unmeasurable segment renders its REASON, never a 0 (A17).
    show_ops = to_bool(params.get("oscillatory_potentials", False))
    show_phnr = to_bool(params.get("phnr", False))
    # Central tendency: `representative` (one exemplar trace per condition×intensity — the
    # back-compatible default), `mean` (average the n eye/animal recordings at each time), or `none`
    # (no averaged trace — draw every replicate at equal weight: "individual traces only").
    central = str(params.get("central", "representative")).strip().lower()
    role = params.get("role", "representative")
    # `role` selects the exemplar rows for the representative view. For mean/none we use ALL
    # recordings regardless of role, so the role filter is skipped (every replicate contributes).
    if "role" in df.columns and role and central == "representative":
        df = df[df["role"].astype(str) == str(role)]
    if df.empty:
        raise ValueError(f"erg_traces: no rows for role={role!r}")

    do_filter = to_bool(params.get("filter", True))
    # Display smoothing default = 120 Hz (owner sign-off 2026-06-23): cuts mains/instrument
    # hum so flat conditions settle while preserving the PDE6B partial-rescue b-wave. The
    # a/b-wave metric below reads the RAW trace, so selection is unaffected by this cutoff.
    lowpass = float(params.get("lowpass_hz", 120.0))

    # Spread styling (mean-spread-styling-spec) — only meaningful when central=mean.
    spread = str(params.get("spread", "band")).strip().lower()
    error = str(params.get("error", "sem")).strip().lower()
    error_every = max(1, int(params.get("error_every", 25) or 25))
    band_alpha = float(params.get("band_alpha", 0.25))
    boundary = str(params.get("boundary_lines", "none")).strip().lower()
    # Band colour: empty = match each trace's colour (so the band is never a mismatched grey); a hex
    # overrides it for all bands (owner ask 2026-06-24).
    band_color_override = str(params.get("band_color", "")).strip()

    # Column order: explicit condition_order if present, else canonical, else first-seen.
    if "condition_order" in df.columns and df["condition_order"].notna().any():
        order = (df.dropna(subset=["condition_order"]).sort_values("condition_order")
                 ["condition"].drop_duplicates().tolist())
    else:
        seen = list(dict.fromkeys(df["condition"].tolist()))
        order = ([c for c in _erg.CONDITION_ORDER if c in seen]
                 + [c for c in seen if c not in _erg.CONDITION_ORDER])
    col_of = {c: i for i, c in enumerate(order)}

    groups = sorted(df["intensity_group"].dropna().unique(), key=_grp_key)
    row_of = {g: i for i, g in enumerate(groups)}

    ig_log = {}
    if "intensity_log_cd_s_m2" in df.columns:
        for g in groups:
            vals = df[df["intensity_group"] == g]["intensity_log_cd_s_m2"].dropna()
            if not vals.empty:
                ig_log[g] = round(float(vals.iloc[0]), 2)
    row_labels = [str(ig_log.get(g, g)) for g in groups]
    col_labels = [_erg.COL_LABELS.get(c, c) for c in order]

    # A "replicate" = one recording = a unique (sample_id, eye) within a condition×intensity. A
    # single-eye iWorx/Diagnosys file yields one replicate per cell (representative == today); a
    # multi-eye or multi-file cohort yields n, which `mean` averages and the band/error span.
    rep_keys = [c for c in ("sample_id", "eye") if c in df.columns]

    # Every condition gets a STABLE explicit colour — its mapped ERG palette colour, else a
    # deterministic fallback from the shared line palette (e.g. a C57/Rd10 cohort that isn't in the
    # ERG palette). This keeps each condition one consistent colour across its intensity rows AND
    # lets its band match the trace (the band was grey only because an unmapped condition had no
    # colour → it fell back to grey while the line auto-coloured). Owner ask 2026-06-24.
    color_of = {c: _erg.COLORS.get(c) or _erg.LINE_PALETTE[i % len(_erg.LINE_PALETTE)]
                for i, c in enumerate(order)}

    panels, tbl_rows = [], []
    peak_uv, n_seen = 0.0, []
    # Per-run mark provenance (erg-manual-marks R6): one entry per a/b marker per cell, aggregating
    # the auto seed time, the finally-measured time, and whether the operator moved it.
    prov_log: list = []
    lm_log: list = []   # every landmarks() result, for the a/b-detector disclosure (A18)
    ops_log: list = []  # every oscillatory_potentials() result, for the group summary (L1-09)
    for cond in order:
        cd = df[df["condition"] == cond]
        color = color_of[cond]
        band_color = band_color_override or color  # default: the band matches its trace
        for g in groups:
            seg = cd[cd["intensity_group"] == g]
            if seg.empty:
                continue
            reps = _replicate_traces(seg, rep_keys, do_filter, lowpass)
            if not reps:
                continue
            panel = {"row": row_of[g], "col": col_of[cond], "color": color, "group": cond}
            manual = _erg.marks_for(manual_marks, cond, "", g, "")
            if central == "mean":
                ref_t, mean_clean, mean_raw, lo, hi, errs, n = _aggregate(reps, error)
                panel["x"], panel["y"] = ref_t, mean_clean
                panel["name"] = f"{cond} {g} (n={n})"
                _apply_spread(panel, spread, ref_t, mean_clean, lo, hi, errs, reps,
                              color, band_color, band_alpha, boundary, error_every, n)
                n_seen.append(n)
                # Measure the a/b table on the AVERAGED RAW trace (matches the mean line drawn).
                lm = _erg.landmarks(ref_t, mean_raw, fs=_fs_from(ref_t), mode=metric_mode,
                                    manual=manual, detector=ab_detector)
                measure_t, measure_y = ref_t, mean_raw
            elif central == "none":
                # No averaged trace — draw every replicate at equal weight (individual traces only).
                ref_t, _, mean_raw, _, _, _, n = _aggregate(reps, error)
                panel["x"], panel["y"] = reps[0][0], reps[0][2]
                panel["opacity"] = 0.55
                panel["extra_lines"] = [{"x": r[0], "y": r[2], "color": color, "alpha": 0.55}
                                        for r in reps[1:]]
                panel["name"] = f"{cond} {g} (n={n}, individual)"
                n_seen.append(n)
                lm = _erg.landmarks(ref_t, mean_raw, fs=_fs_from(ref_t), mode=metric_mode,
                                    manual=manual, detector=ab_detector)  # table = cohort mean
                measure_t, measure_y = ref_t, mean_raw
            else:  # representative — the first replicate (single-eye → byte-identical to before)
                t, raw_y, clean_y = reps[0]
                panel["x"], panel["y"] = t, clean_y
                panel["name"] = f"{cond} {g}"
                n_seen.append(1)
                # Measure on the RAW baseline-corrected trace (the validated metric), not the
                # display-cleaned copy — the dual smooth is internal to landmarks().
                lm = _erg.landmarks(t, raw_y, fs=_fs_from(t), mode=metric_mode, manual=manual,
                                    detector=ab_detector)
                measure_t, measure_y = t, raw_y
            # Seed the a/b landmark marks for this cell (R4): `mark_meta` (always) carries the
            # segment identity + the auto/manual time + source for the Marks panel; the visual dots
            # (gated by `marks`) sit on the DRAWN trace at the landmark times.
            seg = _erg.segment_key(cond, "", g, "")
            row_lab = str(ig_log.get(g, g))
            cell_label = f"{cond} · {row_lab}"
            a_meta = {"segment": seg, "role": "a", "t_ms": lm["a_t_ms"], "source": lm["a_source"],
                      "uv": lm["a_wave_uv"], "label": cell_label}
            b_meta = {"segment": seg, "role": "b", "t_ms": lm["b_t_ms"], "source": lm["b_source"],
                      "uv": lm["b_wave_uv"], "label": cell_label}
            # Surface the auto seed on an operator-moved mark (R6 / editor "moved from …" readout);
            # omitted on the auto path so `meta.selom.marks` stays byte-identical with no manual_marks.
            if lm["a_source"] == "manual":
                a_meta["auto_t_ms"] = lm["a_auto_t_ms"]
            if lm["b_source"] == "manual":
                b_meta["auto_t_ms"] = lm["b_auto_t_ms"]
            panel["mark_meta"] = [a_meta, b_meta]
            prov_log.append(_erg.provenance_entry(seg, "a", lm["a_auto_t_ms"], lm["a_t_ms"], lm["a_source"]))
            prov_log.append(_erg.provenance_entry(seg, "b", lm["b_auto_t_ms"], lm["b_t_ms"], lm["b_source"]))
            lm_log.append(lm)   # A18 — figure-level detector disclosure (robust only)
            if show_marks:
                panel["markers"] = [
                    {"x": lm["a_t_ms"], "y": _y_at(panel["x"], panel["y"], lm["a_t_ms"]),
                     "label": "a" if show_labels else "", "color": _erg.ROLE_COLORS["a"],
                     "textpos": _erg.ROLE_TEXTPOS["a"]},
                    {"x": lm["b_t_ms"], "y": _y_at(panel["x"], panel["y"], lm["b_t_ms"]),
                     "label": "b" if show_labels else "", "color": _erg.ROLE_COLORS["b"],
                     "textpos": _erg.ROLE_TEXTPOS["b"]},
                ]
            peak_uv = max(peak_uv, max((abs(v) for v in panel["y"]), default=0.0))
            panels.append(panel)
            row = [cond, ig_log.get(g, str(g)), lm["b_wave_uv"], lm["a_wave_uv"], lm["b_t_ms"]]
            # Measured on the SAME raw baseline-corrected trace the a/b came from, so every column
            # in a row describes one recording.
            extra = _inner_retinal(measure_t, measure_y, show_ops, show_phnr, metric_mode)
            ops_log.append(extra.pop("_ops", None))
            tbl_rows.append(row + extra["cells"])

    if not panels:
        raise ValueError("erg_traces: no panels built from input")

    # Display unit (default µV → byte-identical). Rescaling the trace amplitudes keeps both the
    # grid scale bar AND the editor's overlay-axis title true; the spread overlays + a/b table
    # rescale with them so the band/error bars stay registered to the mean line.
    unit = _erg.resolve_display_unit(params.get("display_unit", "uV"), peak_uv)
    factor = _erg.unit_factor(unit)
    if factor != 1.0:
        for p in panels:
            _rescale_panel(p, factor)

    n_lo, n_hi = (min(n_seen), max(n_seen)) if n_seen else (0, 0)
    n_txt = f"n={n_lo}" if n_lo == n_hi else f"n={n_lo}–{n_hi}"
    if central == "mean":
        title = f"Mean {metric_mode} ERG (± {_erg.ERR_LABEL.get(error, 'SEM')}, {n_txt})"
        tbl_title = "ERG a/b-wave (means)"
    elif central == "none":
        title = f"Individual {metric_mode} ERG traces ({n_txt})"
        tbl_title = "ERG a/b-wave (cohort mean)"
    else:
        title = f"Representative {metric_mode} ERG"
        tbl_title = "ERG a/b-wave (representatives)"

    spec = grid_spec(
        panels, nrows=len(groups), ncols=len(order),
        scalebar={"x_len": float(params.get("scale_ms", 100.0)), "x_unit": "ms",
                  "y_len": float(params.get("scale_uv", 200.0)) * factor, "y_unit": unit},
        row_labels=row_labels, col_labels=col_labels,
        title=title,
    )
    # Manual-marks provenance (R6): caption states the operator-adjusted mix, and the per-marker log
    # rides meta.selom.markProvenance. Both only when a mark actually moved → byte-identical default.
    n_moved = sum(1 for e in prov_log if e["moved"])
    if n_moved:
        spec["layout"].setdefault("meta", {}).setdefault("selom", {})["markProvenance"] = prov_log
    # a/b-detector disclosure (A18): the opt-in `robust` detector measures DIFFERENT amplitudes from
    # the windowed default, so the recipe must name it. None for `windowed` → byte-identical default.
    ab_meta = _erg.detector_summary(lm_log)
    if ab_meta is not None:
        spec["layout"].setdefault("meta", {})["ab_detector"] = ab_meta
    if metric_mode != param_mode:
        spec["layout"].setdefault("meta", {})["adaptation"] = metric_mode
    cols = ["condition", "intensity (log cd·s/m²)", f"b-wave ({unit})", f"a-wave ({unit})",
            "b-wave t (ms)"] + _inner_retinal_columns(show_ops, show_phnr, unit)
    spec["table"] = table(
        cols,
        [[c, ig, _erg.disp_round(b, factor), _erg.disp_round(a, factor), bt, *rest]
         for c, ig, b, a, bt, *rest in tbl_rows],
        title=tbl_title + _erg.operator_adjusted_note(n_moved, len(prov_log)))
    # Group-level OP summary (A17's aggregation half): how many segments were NOT measurable, so a
    # reader of the recorded figure knows the mean excluded them rather than absorbing them as 0.
    ops_seen = [o for o in ops_log if o is not None]
    if ops_seen:
        spec["layout"].setdefault("meta", {})["oscillatory_potentials"] = _erg.op_group_mean(ops_seen)
    return jsonable(spec)


def _inner_retinal_columns(show_ops: bool, show_phnr: bool, unit: str) -> list:
    """The extra statistics-table columns the OP / PhNR metrics add (empty when both are off)."""
    cols = []
    if show_ops:
        cols += [f"ΣOP ({unit})", f"OP RMS ({unit})", "OPs (n)"]
    if show_phnr:
        cols += [f"PhNR BT ({unit})", "PhNR trough t (ms)"]
    return cols


def _inner_retinal(t, y, show_ops: bool, show_phnr: bool, mode: str) -> dict:
    """``{"cells": [...], "_ops": <result|None>}`` for one recording.

    OPs are the ISCEV 75-300 Hz wavelets (inner-retinal); PhNR is the slow negative wave after the
    photopic b-wave (retinal-ganglion-cell function). Neither is claimed when it could not be
    measured: an unmeasurable OP result renders its REASON in the cell (never a 0, which would BE
    the dysfunction reading — A17), and an unmeasurable PhNR renders "—"."""
    cells, ops = [], None
    if show_ops:
        ops = _erg.oscillatory_potentials(t, y, fs=_fs_from(t))
        if ops["measurable"]:
            cells += [ops["op_sum_uv"], ops["op_rms_uv"], ops["n_ops"]]
        else:
            label = _erg.NOT_MEASURABLE_LABELS[ops["reason"]]
            cells += [label, label, "—"]
    if show_phnr:
        # The PhNR is a PHOTOPIC measure; the cone b-window is the right anchor for its trough.
        phnr = _erg.photopic_negative_response(
            t, y, fs=_fs_from(t),
            b_window_ms=(12.0, 80.0) if mode == "photopic" else (40.0, 120.0))
        cells += ([phnr["phnr_bt_uv"], phnr["trough_t_ms"]] if phnr else ["—", "—"])
    return {"cells": cells, "_ops": ops}


def _grp_key(v):
    """Sort key for intensity_group values, whether 'Group1'/'g1' or a bare int."""
    digits = "".join(ch for ch in str(v) if ch.isdigit())
    return int(digits) if digits else str(v)


def _fs_from(time_ms) -> float:
    """Sampling rate (Hz) from the time axis (ms)."""
    if len(time_ms) < 2:
        return 5000.0
    dt = float(time_ms[1]) - float(time_ms[0])
    return 1000.0 / dt if dt else 5000.0


def _y_at(xs, ys, t_ms: float) -> float:
    """Value of the drawn trace nearest time ``t_ms`` — places an a/b dot ON the line."""
    if not xs:
        return 0.0
    i = min(range(len(xs)), key=lambda k: abs(float(xs[k]) - float(t_ms)))
    return float(ys[i])


def _replicate_traces(seg, rep_keys, do_filter, lowpass):
    """Split a (condition × intensity) segment into individual replicate traces.

    With ``rep_keys`` (sample_id / eye) each unique combo is one recording → one trace; without
    them the whole segment is one trace (the minimal single-eye path → byte-identical). Returns
    ``[(t_list, raw_y_list, clean_y_list), …]`` in a deterministic order (sorted by the rep keys).
    The display-cleaned copy is computed once here; the raw copy feeds the a/b landmark metric."""
    def _one(sub):
        sub = sub.sort_values("time_ms")
        t = [float(v) for v in sub["time_ms"].tolist()]
        raw = [float(v) for v in sub["voltage_uv"].tolist()]
        if len(t) < 2:
            return None
        clean = _erg.clean_trace(raw, fs=_fs_from(t), lowpass=lowpass) if do_filter else list(raw)
        return t, raw, clean

    out = []
    if rep_keys:
        for _, sub in seg.groupby(rep_keys, dropna=False, sort=True):
            rec = _one(sub)
            if rec:
                out.append(rec)
    else:
        rec = _one(seg)
        if rec:
            out.append(rec)
    return out


def _aggregate(reps, error):
    """Average n replicate traces and compute the per-point spread, delegating to the shared
    ``_charts.aggregate_replicates`` so the math is identical to every other mean ± spread figure.
    Aggregates the display-cleaned copy (mean line + band/error) and the RAW copy (for the a/b
    landmark metric) separately. Returns
    ``(ref_t, mean_clean, mean_raw, band_lower, band_upper, err_array, n)``."""
    ref_t, mean_clean, lower, upper, errs, n = _erg.aggregate_replicates(
        [(r[0], r[2]) for r in reps], error)
    _, mean_raw, _, _, _, _ = _erg.aggregate_replicates([(r[0], r[1]) for r in reps], error)
    return ref_t, mean_clean, mean_raw, lower, upper, errs, n


def _apply_spread(panel, spread, ref_t, mean_clean, lower, upper, errs, reps,
                  color, band_color, band_alpha, boundary, error_every, n):
    """Attach the chosen spread overlay to a mean panel via the shared `_tracegrid` overlay hook.

    ``band`` / ``error_bars`` / ``both`` need n≥2 (else they'd be a zero-width artifact — degrade
    to the bare mean line). ``individual`` overlays the n raw replicate traces faintly behind the
    mean (always meaningful, even at n=1). ``band_color`` is the band fill colour (defaults to the
    trace ``color`` so the band matches its trace; an override recolours it)."""
    if spread in ("band", "both") and n >= 2:
        panel["band"] = {"x": ref_t, "lower": lower, "upper": upper, "color": band_color,
                         "alpha": band_alpha, "boundary": boundary, "group": panel["group"]}
    if spread in ("error_bars", "both") and n >= 2:
        panel["error"] = {"x": ref_t, "y": mean_clean, "err": errs, "every": error_every,
                          "color": color}
    if spread == "individual":
        panel["extra_lines"] = [{"x": r[0], "y": r[2], "color": color, "alpha": 0.18}
                                for r in reps]


def _rescale_panel(p, factor):
    """Rescale a panel's line + every spread overlay by the display-unit ``factor`` so the band,
    error bars, and replicate lines stay registered to the rescaled mean line."""
    p["y"] = [v * factor for v in p["y"]]
    b = p.get("band")
    if b:
        b["lower"] = [v * factor for v in b["lower"]]
        b["upper"] = [v * factor for v in b["upper"]]
    e = p.get("error")
    if e:
        e["y"] = [v * factor for v in e["y"]]
        e["err"] = [v * factor for v in e["err"]]
    for ln in p.get("extra_lines", []):
        ln["y"] = [v * factor for v in ln["y"]]
    for m in p.get("markers", []):  # a/b dots sit on the rescaled line
        m["y"] = m["y"] * factor
