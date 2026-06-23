"""Real ERG flicker: read the long ERG waveform table, keep the flicker steps, and render the
steady-state waveform grid (or the N1→P1-vs-frequency summary) + the per-condition N1/P1 table.

Input CSV (canonical ``erg_waveforms_long``): ``condition``, ``time_ms``, ``voltage_uv``
(required); ``flicker_hz``, ``stimulus_type``, ``eye``, ``condition_order`` (optional but used).

The N1→P1 metric prefers the **device markers** when the feed carries them: a Diagnosys export's
materialize path joins the device N1→P1 on as ``device_n1p1_uv`` + ``device_p1_implicit_ms``
(``_celeris.flicker_device_metrics``), so the dropped recording drives the device value at each
frequency (D2 / R-flicker-3, ``source="device"``). With no device column (the iWorx feed, or a
plain waveform CSV) Selom re-derives N1→P1 from the phase-averaged steady-state cycle
(``_erg.flicker_landmarks``, ``source="Selom"``). Either way the caption names the source.
"""
from skills import _erg
from skills._engine import to_bool
from skills._plotly import jsonable
from skills.proprietary.erg_flicker.run import flicker_grid, flicker_table, freq_spec

_REQUIRED = {"condition", "time_ms", "voltage_uv"}


def _flicker_rows(df):
    """Keep the flicker steps: by ``stimulus_type == "flicker"`` when present, else by a non-null
    ``flicker_hz``. Honest ValueError when neither signal is present or no flicker step exists."""
    if "stimulus_type" in df.columns:
        sub = df[df["stimulus_type"].astype(str) == "flicker"]
        if sub.empty:
            raise ValueError("erg_flicker: no flicker steps in this export "
                             "(no rows with stimulus_type='flicker').")
        return sub
    if "flicker_hz" in df.columns:
        sub = df[df["flicker_hz"].notna()]
        if not sub.empty:
            return sub
    raise ValueError("erg_flicker: input has no flicker information "
                     "(need a stimulus_type='flicker' or a flicker_hz column).")


def _fs_from(time_ms) -> float:
    if len(time_ms) < 2:
        return 5000.0
    dt = float(time_ms[1]) - float(time_ms[0])
    return 1000.0 / dt if dt else 5000.0


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    df = pd.read_csv(data_path)
    missing = _REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"erg_flicker: input missing required columns {sorted(missing)}")

    df = _flicker_rows(df)
    view = str(params.get("view", "waveform")).strip().lower()
    do_filter = to_bool(params.get("filter", True))
    lowpass = float(params.get("lowpass_hz", 120.0))
    show_marks = to_bool(params.get("marks", True))  # N1/P1 dots on each waveform panel (M3)
    has_hz = "flicker_hz" in df.columns
    # Device N1→P1 ride-along (Diagnosys materialize path) → prefer it over Selom re-derivation (D2).
    has_device = "device_n1p1_uv" in df.columns and df["device_n1p1_uv"].notna().any()

    # Frequency key per row: the real Hz when present, else the step/group label (no metric then).
    if has_hz:
        df = df[df["flicker_hz"].notna()]
        freqs = sorted(float(v) for v in df["flicker_hz"].dropna().unique())
    else:
        gcol = "intensity_group" if "intensity_group" in df.columns else "step"
        freqs = sorted(str(v) for v in df[gcol].dropna().unique())
    if not freqs:
        raise ValueError("erg_flicker: no flicker frequencies found.")
    row_of = {f: i for i, f in enumerate(freqs)}
    row_labels = [f"{f:g} Hz" if has_hz else str(f) for f in freqs]

    # Condition order: explicit condition_order, else canonical, else first-seen.
    if "condition_order" in df.columns and df["condition_order"].notna().any():
        order = (df.dropna(subset=["condition_order"]).sort_values("condition_order")
                 ["condition"].drop_duplicates().tolist())
    else:
        seen = list(dict.fromkeys(df["condition"].tolist()))
        order = ([c for c in _erg.CONDITION_ORDER if c in seen]
                 + [c for c in seen if c not in _erg.CONDITION_ORDER])
    col_of = {c: i for i, c in enumerate(order)}
    col_labels = [_erg.COL_LABELS.get(c, c) for c in order]

    panels, tbl_rows = [], []
    metric = {}  # (condition, freq) -> n1p1 µV (for the summary view)
    used_device = False
    peak_uv = 0.0
    for cond in order:
        cd = df[df["condition"] == cond]
        for f in freqs:
            seg_rows = cd[(cd["flicker_hz"].astype(float) == f)] if has_hz else \
                cd[cd[("intensity_group" if "intensity_group" in cd.columns else "step")].astype(str) == f]
            if seg_rows.empty:
                continue
            # Average across eyes at each time point → one representative steady-state trace.
            seg = (seg_rows.groupby("time_ms", as_index=False)["voltage_uv"].mean()
                   .sort_values("time_ms"))
            t = seg["time_ms"].tolist()
            y_raw = seg["voltage_uv"].tolist()
            if len(t) < 4:
                continue
            n_eyes = int(seg_rows["eye"].nunique()) if "eye" in seg_rows.columns else 1
            fs = _fs_from(t)
            y_disp = _erg.clean_trace(y_raw, fs=fs, lowpass=lowpass) if do_filter \
                else [float(v) for v in y_raw]
            peak_uv = max(peak_uv, max((abs(v) for v in y_disp), default=0.0))
            panel = {"row": row_of[f], "col": col_of[cond], "x": t, "y": y_disp,
                     "color": _erg.COLORS.get(cond), "name": f"{cond} {row_labels[row_of[f]]}",
                     "group": cond}
            # N1/P1 marker dots on the first visible cycle of the drawn trace (M3, visual locator —
            # the table's N1→P1 amplitude is the device/folded-cycle value, not these coordinates).
            marks = _erg.flicker_first_cycle_marks(t, y_disp, float(f)) if (show_marks and has_hz) else None
            if marks:
                panel["markers"] = [
                    {"x": marks["n1"][0], "y": marks["n1"][1], "label": "N1", "color": "#333333"},
                    {"x": marks["p1"][0], "y": marks["p1"][1], "label": "P1", "color": "#333333"},
                ]
            panels.append(panel)
            # N1→P1: prefer the device markers riding on the feed (one value per eye → mean across
            # eyes), else re-derive from the phase-averaged steady-state cycle (raw baseline trace,
            # not the display-cleaned copy; needs a real frequency to fold).
            n1p1 = p1_ms = None
            if has_device and "device_n1p1_uv" in seg_rows.columns:
                gcol = "eye" if "eye" in seg_rows.columns else "condition"
                dn = seg_rows.groupby(gcol)["device_n1p1_uv"].first().dropna()
                dp = seg_rows.groupby(gcol)["device_p1_implicit_ms"].first().dropna()
                if not dn.empty:
                    n1p1 = round(float(dn.mean()), 3)
                    p1_ms = round(float(dp.mean()), 1) if not dp.empty else None
                    used_device = True
            if n1p1 is None:
                lm = _erg.flicker_landmarks(t, y_raw, float(f)) if has_hz else None
                if lm:
                    n1p1, p1_ms = lm["n1p1_uv"], lm["p1_implicit_ms"]
            metric[(cond, f)] = n1p1
            tbl_rows.append([cond, (float(f) if has_hz else f), n1p1, p1_ms, n_eyes])

    if not panels:
        raise ValueError("erg_flicker: no flicker panels built from input")

    unit = _erg.resolve_display_unit(params.get("display_unit", "uV"), peak_uv)
    factor = _erg.unit_factor(unit)
    if factor != 1.0:
        for p in panels:
            p["y"] = [v * factor for v in p["y"]]
            for m in p.get("markers", []):
                m["y"] = m["y"] * factor

    table_rows = [[c, hz, _erg.disp_round(v, factor) if v is not None else "—",
                   (p1 if p1 is not None else "—"), n]
                  for c, hz, v, p1, n in tbl_rows]
    source = "device" if used_device else "Selom"  # honest provenance (R-honesty-1 / R-flicker-3)

    if view == "summary":
        if not has_hz:
            raise ValueError("erg_flicker: the summary view needs a flicker_hz column "
                             "(amplitude-versus-frequency); use view='waveform' instead.")
        cond_series = []
        for cond in order:
            xs = [f for f in freqs if metric.get((cond, f)) is not None]
            ys = [metric[(cond, f)] for f in xs]
            if xs:
                cond_series.append((cond, xs, ys))
        if not cond_series:
            raise ValueError("erg_flicker: no N1→P1 amplitudes to plot for the summary view.")
        spec = freq_spec(cond_series, unit=unit, factor=factor,
                         title="Flicker N1–P1 vs frequency")
        spec["table"] = flicker_table(table_rows, unit, source=source)
        return jsonable(spec)

    title = "Flicker ERG (" + ", ".join(row_labels) + ")" if has_hz else "Flicker ERG"
    spec = flicker_grid(panels, nrows=len(freqs), ncols=len(order),
                        row_labels=row_labels, col_labels=col_labels,
                        params=params, unit=unit, factor=factor, title=title)
    spec["table"] = flicker_table(table_rows, unit, source=source)
    return jsonable(spec)
