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
            if central == "mean":
                ref_t, mean_clean, mean_raw, lo, hi, errs, n = _aggregate(reps, error)
                panel["x"], panel["y"] = ref_t, mean_clean
                panel["name"] = f"{cond} {g} (n={n})"
                _apply_spread(panel, spread, ref_t, mean_clean, lo, hi, errs, reps,
                              color, band_color, band_alpha, boundary, error_every, n)
                n_seen.append(n)
                # Measure the a/b table on the AVERAGED RAW trace (matches the mean line drawn).
                lm = _erg.landmarks(ref_t, mean_raw, fs=_fs_from(ref_t))
            elif central == "none":
                # No averaged trace — draw every replicate at equal weight (individual traces only).
                ref_t, _, mean_raw, _, _, _, n = _aggregate(reps, error)
                panel["x"], panel["y"] = reps[0][0], reps[0][2]
                panel["opacity"] = 0.55
                panel["extra_lines"] = [{"x": r[0], "y": r[2], "color": color, "alpha": 0.55}
                                        for r in reps[1:]]
                panel["name"] = f"{cond} {g} (n={n}, individual)"
                n_seen.append(n)
                lm = _erg.landmarks(ref_t, mean_raw, fs=_fs_from(ref_t))  # table = cohort mean
            else:  # representative — the first replicate (single-eye → byte-identical to before)
                t, raw_y, clean_y = reps[0]
                panel["x"], panel["y"] = t, clean_y
                panel["name"] = f"{cond} {g}"
                n_seen.append(1)
                # Measure on the RAW baseline-corrected trace (the validated metric), not the
                # display-cleaned copy — the dual smooth is internal to landmarks().
                lm = _erg.landmarks(t, raw_y, fs=_fs_from(t))
            peak_uv = max(peak_uv, max((abs(v) for v in panel["y"]), default=0.0))
            panels.append(panel)
            tbl_rows.append([cond, ig_log.get(g, str(g)), lm["b_wave_uv"],
                             lm["a_wave_uv"], lm["b_t_ms"]])

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
        title = f"Mean {adapt or 'scotopic'} ERG (± {_erg.ERR_LABEL.get(error, 'SEM')}, {n_txt})"
        tbl_title = "ERG a/b-wave (means)"
    elif central == "none":
        title = f"Individual {adapt or 'scotopic'} ERG traces ({n_txt})"
        tbl_title = "ERG a/b-wave (cohort mean)"
    else:
        title = f"Representative {adapt or 'scotopic'} ERG"
        tbl_title = "ERG a/b-wave (representatives)"

    spec = grid_spec(
        panels, nrows=len(groups), ncols=len(order),
        scalebar={"x_len": float(params.get("scale_ms", 100.0)), "x_unit": "ms",
                  "y_len": float(params.get("scale_uv", 200.0)) * factor, "y_unit": unit},
        row_labels=row_labels, col_labels=col_labels,
        title=title,
    )
    spec["table"] = table(
        ["condition", "intensity (log cd·s/m²)", f"b-wave ({unit})", f"a-wave ({unit})",
         "b-wave t (ms)"],
        [[c, ig, _erg.disp_round(b, factor), _erg.disp_round(a, factor), bt]
         for c, ig, b, a, bt in tbl_rows],
        title=tbl_title)
    return jsonable(spec)


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
