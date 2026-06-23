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


def _filter_stimulus(df, requested):
    """Multi-mode exports (Diagnosys) carry scotopic + photopic + flicker steps, each with its own
    per-mode intensity groups — so a single trace grid must render ONE mode or the intensity rows
    collide. Filter to ``requested`` if given, else default to scotopic (the canonical dark-adapted
    ERG), else photopic. A no-op when there is no ``stimulus_type`` column (the iWorx path) — so
    that path is unchanged."""
    if "stimulus_type" not in df.columns:
        return df
    present = [s for s in df["stimulus_type"].dropna().astype(str).unique() if s]
    if not present:
        return df
    pick = str(requested) if requested else ""
    if not pick:
        pick = next((p for p in ("scotopic_flash", "photopic_flash") if p in present), "")
    if pick:
        sub = df[df["stimulus_type"].astype(str) == pick]
        if not sub.empty:
            return sub
    return df


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    df = pd.read_csv(data_path)
    missing = _REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"erg_traces: input missing required columns {sorted(missing)}")

    df = _filter_stimulus(df, params.get("stimulus_type", ""))
    role = params.get("role", "representative")
    if "role" in df.columns and role:
        df = df[df["role"].astype(str) == str(role)]
    if df.empty:
        raise ValueError(f"erg_traces: no rows for role={role!r}")

    do_filter = to_bool(params.get("filter", True))
    # Display smoothing default = 120 Hz (owner sign-off 2026-06-23): cuts mains/instrument
    # hum so flat conditions settle while preserving the PDE6B partial-rescue b-wave. The
    # a/b-wave metric below reads the RAW trace, so selection is unaffected by this cutoff.
    lowpass = float(params.get("lowpass_hz", 120.0))

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

    panels, tbl_rows = [], []
    peak_uv = 0.0
    for cond in order:
        cd = df[df["condition"] == cond]
        for g in groups:
            seg = cd[cd["intensity_group"] == g].sort_values("time_ms")
            if seg.empty:
                continue
            t = seg["time_ms"].tolist()
            y = seg["voltage_uv"].tolist()
            fs = _fs_from(t)
            yv = _erg.clean_trace(y, fs=fs, lowpass=lowpass) if do_filter else [float(v) for v in y]
            peak_uv = max(peak_uv, max((abs(v) for v in yv), default=0.0))
            panels.append({"row": row_of[g], "col": col_of[cond], "x": t, "y": yv,
                           "color": _erg.COLORS.get(cond), "name": f"{cond} {g}", "group": cond})
            # Measure on the RAW baseline-corrected trace (the validated metric), not the
            # display-cleaned copy — the dual smooth is internal to landmarks().
            lm = _erg.landmarks(t, y, fs=fs)
            tbl_rows.append([cond, ig_log.get(g, str(g)), lm["b_wave_uv"],
                             lm["a_wave_uv"], lm["b_t_ms"]])

    if not panels:
        raise ValueError("erg_traces: no panels built from input")

    # Display unit (default µV → byte-identical). Rescaling the trace amplitudes keeps both the
    # grid scale bar AND the editor's overlay-axis title true; the a/b table rescales with them.
    unit = _erg.resolve_display_unit(params.get("display_unit", "uV"), peak_uv)
    factor = _erg.unit_factor(unit)
    if factor != 1.0:
        for p in panels:
            p["y"] = [v * factor for v in p["y"]]

    spec = grid_spec(
        panels, nrows=len(groups), ncols=len(order),
        scalebar={"x_len": float(params.get("scale_ms", 100.0)), "x_unit": "ms",
                  "y_len": float(params.get("scale_uv", 200.0)) * factor, "y_unit": unit},
        row_labels=row_labels, col_labels=col_labels,
        title="Representative scotopic ERG",
    )
    spec["table"] = table(
        ["condition", "intensity (log cd·s/m²)", f"b-wave ({unit})", f"a-wave ({unit})",
         "b-wave t (ms)"],
        [[c, ig, _erg.disp_round(b, factor), _erg.disp_round(a, factor), bt]
         for c, ig, b, a, bt in tbl_rows],
        title="ERG a/b-wave (representatives)")
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
