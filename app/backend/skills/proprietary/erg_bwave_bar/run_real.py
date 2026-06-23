"""Real ERG amplitude bar: per-condition mean ± SEM a- or b-wave at one flash intensity,
with every eye overlaid as a point.

Two input shapes are accepted, so the bar is a true fan-out sibling of the trace grid:

* ``erg_metrics_long`` — the device's own markers (``a_wave_uv``/``b_wave_uv`` per eye × step).
  Preferred when present (the device is authoritative — docs/diagnosys-erg/spec.md D2).
* ``erg_waveforms_long`` — the raw waveforms the trace grid draws (``time_ms``/``voltage_uv``).
  When no marker column is present the a/b peak is **measured from the traces** per
  (sample × condition × intensity × eye) with ``_erg.landmarks`` — the same metric the grid
  reports — so the bar runs straight off the dropped recording at the intensity you pick.

The ``wave`` param selects a-wave or b-wave (``b`` default); ``intensity_group`` picks the flash.
"""
from skills import _erg
from skills._engine import to_bool
from skills._table import table
from skills.proprietary.erg_bwave_bar.run import bar_spec

_TRUTHY = {"y", "yes", "true", "1", "t"}


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    df = pd.read_csv(data_path)
    group = str(params.get("intensity_group", "Group4"))
    wave = str(params.get("wave", "b")).strip().lower()
    if wave not in ("a", "b"):
        wave = "b"
    # `value_col` stays an advanced override; empty (the default) → derive from `wave`.
    value_col = str(params.get("value_col") or "").strip() or f"{wave}_wave_uv"
    wave_label = "a-wave" if value_col == "a_wave_uv" else (
        "b-wave" if value_col == "b_wave_uv" else value_col)
    show_points = to_bool(params.get("points", True))

    # Fan-out path: handed the waveform table (no marker column) → measure the a/b peak from the
    # traces, the owner's "max b-wave peak from the traces at a chosen intensity". Device markers
    # win when present (above) per D2; this is the measure-from-traces fallback + the own-recording path.
    measured_from_traces = False
    if value_col not in df.columns and {"time_ms", "voltage_uv"}.issubset(df.columns):
        df = _metrics_from_waveforms(df)
        measured_from_traces = True

    for col in ("condition", "intensity_group", value_col):
        if col not in df.columns:
            raise ValueError(f"erg_bwave_bar: input missing required column {col!r}")

    # Multi-mode exports (Diagnosys) carry scotopic + photopic flash steps whose per-mode intensity
    # groups share Group labels — keep ONE mode (the friendly `adaptation` hint, or explicit
    # `stimulus_type`; auto = scotopic) so Group4 means one thing. No-op without the column.
    adapt = ""
    if "stimulus_type" in df.columns:
        present = [s for s in df["stimulus_type"].dropna().astype(str).unique() if s]
        pick, adapt = _erg.resolve_flash_mode(
            present, params.get("adaptation", "auto"), params.get("stimulus_type", ""))
        if pick:
            sub = df[df["stimulus_type"].astype(str) == pick]
            if not sub.empty:
                df = sub

    # Honour an optional QC column (drop flagged eyes from both the bar and the points).
    if "qc_excluded" in df.columns:
        df = df[~df["qc_excluded"].astype(str).str.strip().str.lower().isin(_TRUTHY)]

    sub = df[df["intensity_group"].astype(str) == group]
    if sub.empty:
        raise ValueError(f"erg_bwave_bar: no rows for intensity_group={group!r}")

    # Column order: explicit condition_order if present, else canonical, else first-seen.
    if "condition_order" in df.columns and df["condition_order"].notna().any():
        order = (df.dropna(subset=["condition_order"]).sort_values("condition_order")
                 ["condition"].drop_duplicates().tolist())
    else:
        seen = list(dict.fromkeys(sub["condition"].tolist()))
        order = ([c for c in _erg.CONDITION_ORDER if c in seen]
                 + [c for c in seen if c not in _erg.CONDITION_ORDER])

    cond_values = []
    for cond in order:
        vals = sub[sub["condition"] == cond][value_col].dropna().astype(float).tolist()
        if vals:
            cond_values.append((cond, vals))
    if not cond_values:
        raise ValueError("erg_bwave_bar: no values to plot after filtering")

    # Display unit (default µV → byte-identical). Peak = the largest single-eye amplitude (µV).
    peak_uv = max((max(vals) for _c, vals in cond_values), default=0.0)
    unit = _erg.resolve_display_unit(params.get("display_unit", "uV"), peak_uv)
    factor = _erg.unit_factor(unit)

    # Intensity caption: the log cd·s/m² if the table carries it, else the group label.
    intensity_label = group
    if "intensity_log_cd_s_m2" in sub.columns:
        logs = sub["intensity_log_cd_s_m2"].dropna()
        if not logs.empty:
            intensity_label = f"{float(logs.iloc[0]):g} log cd·s/m²"

    spec, tbl_rows = bar_spec(cond_values, intensity_label=intensity_label,
                              title=f"{adapt or 'scotopic'} {wave_label} by condition".capitalize(),
                              unit=unit, factor=factor, show_points=show_points,
                              wave_label=wave_label)
    # Honest provenance (R-honesty-1): device markers vs Selom-measured-from-traces.
    source = "measured from traces" if measured_from_traces else "device markers"
    spec["table"] = table(["condition", "n (eyes)", f"mean {wave_label} ({unit})", f"SEM ({unit})"],
                          tbl_rows, title=f"ERG {wave_label} (mean ± SEM, {source})")
    return spec


def _fs_from(time_ms) -> float:
    """Sampling rate (Hz) from the time axis (ms)."""
    if len(time_ms) < 2:
        return 5000.0
    dt = float(time_ms[1]) - float(time_ms[0])
    return 1000.0 / dt if dt else 5000.0


def _metrics_from_waveforms(df):
    """``erg_waveforms_long`` → a per-eye a/b metrics frame measured from the traces.

    One trace per (sample × condition × intensity × eye) → one ``_erg.landmarks`` measurement →
    one bar point. Both a- and b-wave are measured (cheap) so either ``wave`` works. Carries the
    intensity / stimulus columns through so the downstream filters behave as on a metrics table.
    """
    import pandas as pd

    keys = [k for k in ("sample_id", "condition", "intensity_group", "eye") if k in df.columns]
    if "condition" not in keys or "intensity_group" not in keys:
        return df  # not a recognizable waveform grouping → let the required-column check fail honestly
    carry = [c for c in ("intensity_log_cd_s_m2", "stimulus_type", "condition_order") if c in df.columns]
    rows = []
    for kv, seg in df.groupby(keys, dropna=False):
        seg = seg.sort_values("time_ms")
        t = seg["time_ms"].astype(float).tolist()
        y = seg["voltage_uv"].astype(float).tolist()
        if len(t) < 4:
            continue
        lm = _erg.landmarks(t, y, fs=_fs_from(t))
        rec = dict(zip(keys, kv if isinstance(kv, tuple) else (kv,)))
        rec["a_wave_uv"] = lm["a_wave_uv"]
        rec["b_wave_uv"] = lm["b_wave_uv"]
        for c in carry:
            vals = seg[c].dropna()
            rec[c] = vals.iloc[0] if not vals.empty else None
        rows.append(rec)
    return pd.DataFrame(rows)
