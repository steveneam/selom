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
    show_error = to_bool(params.get("show_error", True))
    # Styling knobs (mean-spread-styling-spec): spread metric, bar look, significance, reference line.
    error = str(params.get("error", "sem")).strip().lower()
    bar_fill = str(params.get("bar_fill", "pattern")).strip().lower()
    sig_test = str(params.get("sig_test", "welch")).strip().lower()
    legend = to_bool(params.get("legend", False))
    comparisons = _parse_comparisons(params.get("comparisons", ""))
    hline = _to_float_or_none(params.get("hline"))
    vline = _to_float_or_none(params.get("vline"))

    # Fan-out path: handed the waveform table (no marker column) → measure the a/b peak from the
    # traces, the owner's "max b-wave peak from the traces at a chosen intensity". Device markers
    # win when present (above) per D2; this is the measure-from-traces fallback + the own-recording path.
    # Operator-set landmark marks (docs/erg-manual-marks/spec.md) — applied only on the
    # measure-from-traces path (device markers stay authoritative when a metrics table is supplied).
    manual_marks = _erg.parse_manual_marks(params.get("manual_marks", ""))
    measured_from_traces = False
    if value_col not in df.columns and {"time_ms", "voltage_uv"}.issubset(df.columns):
        # Cone-aware a/b: photopic (light-adapted) responses are faster, so the cone landmark
        # windows must measure them (the scotopic b-window would miss an early cone b-wave). The
        # per-row stimulus_type wins inside metrics_from_waveforms; this default covers a plain
        # waveform CSV with no stimulus_type column (the user's adaptation/stimulus_type hint).
        default_mode = _erg.adaptation_mode(params.get("adaptation", "auto"), params.get("stimulus_type", ""))
        df = _erg.metrics_from_waveforms(df, default_mode=default_mode, marks=manual_marks)
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
                              wave_label=wave_label, error=error, show_error=show_error,
                              bar_fill=bar_fill,
                              comparisons=comparisons, sig_test=sig_test,
                              hline=hline, hline_label=str(params.get("hline_label", "")),
                              vline=vline, vline_label=str(params.get("vline_label", "")),
                              legend=legend)
    # Honest provenance (R-honesty-1): device markers vs Selom-measured-from-traces.
    source = "measured from traces" if measured_from_traces else "device markers"
    err_label = _erg.ERR_LABEL.get(error, "SEM")
    # Manual-marks provenance (erg-manual-marks R6, caption-level): how many plotted eyes were
    # measured at an operator-set landmark vs the auto window. Only on the from-traces path.
    prov = ""
    src_col = {"a_wave_uv": "a_source", "b_wave_uv": "b_source"}.get(value_col)
    if measured_from_traces and src_col and src_col in sub.columns:
        plotted = sub[sub["condition"].isin(order) & sub[value_col].notna()]
        n_manual = int((plotted[src_col].astype(str) == "manual").sum())
        if n_manual:
            prov = f", {n_manual} of {len(plotted)} operator-adjusted"
    spec["table"] = table(["condition", "n (eyes)", f"mean {wave_label} ({unit})", f"{err_label} ({unit})"],
                          tbl_rows, title=f"ERG {wave_label} (mean ± {err_label}, {source}{prov})")
    return spec


def _parse_comparisons(raw):
    """``"A~B, C~D"`` (or ``;``-separated) → ``[(condA, condB, override), …]`` for the significance
    brackets. An optional ``:`` suffix overrides the stars — ``"A~B:**"`` (literal stars) or
    ``"A~B:0.003"`` (a p-value) — else Selom computes them (the Both-available choice). Empty /
    malformed pairs are skipped (no brackets, not an error)."""
    out = []
    for chunk in str(raw or "").replace(";", ",").split(","):
        pair, _, override = chunk.partition(":")
        parts = [p.strip() for p in pair.split("~")]
        if len(parts) == 2 and parts[0] and parts[1]:
            out.append((parts[0], parts[1], override.strip() or None))
    return out


def _to_float_or_none(v):
    try:
        return float(v) if v is not None and str(v).strip() != "" else None
    except (ValueError, TypeError):
        return None
