"""Real ERG b-wave bar: read the long ERG metrics table, take one flash intensity,
and draw the per-condition mean ± SEM bar with every eye overlaid as a point.

Input CSV (canonical ``erg_metrics_long``): ``condition``, ``intensity_group``,
``b_wave_uv`` (required); ``intensity_log_cd_s_m2``, ``condition_order``, ``qc_excluded``
(optional). One row per eye × intensity.
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
    value_col = str(params.get("value_col", "b_wave_uv"))
    show_points = to_bool(params.get("points", True))

    for col in ("condition", "intensity_group", value_col):
        if col not in df.columns:
            raise ValueError(f"erg_bwave_bar: input missing required column {col!r}")

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

    # Display unit (default µV → byte-identical). Peak = the largest single-eye b-wave (µV).
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
                              title="Scotopic b-wave by condition", unit=unit, factor=factor,
                              show_points=show_points)
    spec["table"] = table(["condition", "n (eyes)", f"mean b-wave ({unit})", f"SEM ({unit})"],
                          tbl_rows, title="ERG b-wave (mean ± SEM)")
    return spec
