"""Real ERG intensity-response: aggregate the long ERG metrics table per
(condition × intensity), fit each condition with a Naka-Rushton curve, and plot the
b-wave-vs-log-intensity points + fit per condition.

Input CSV (canonical ``erg_metrics_long``): ``condition``, ``intensity_group``,
``intensity_log_cd_s_m2``, ``b_wave_uv`` (required); ``condition_order``, ``qc_excluded``
(optional). One row per eye × intensity.
"""
from skills import _erg
from skills._engine import to_bool
from skills._table import table
from skills.proprietary.erg_intensity_response.run import ir_spec

_TRUTHY = {"y", "yes", "true", "1", "t"}
_REQUIRED = {"condition", "intensity_log_cd_s_m2"}


def _filter_stimulus(df, requested):
    """Keep one stimulus mode for the intensity-response curve. Default = scotopic (the canonical
    intensity series); a no-op without a ``stimulus_type`` column (iWorx path unchanged)."""
    if "stimulus_type" not in df.columns:
        return df
    present = [s for s in df["stimulus_type"].dropna().astype(str).unique() if s]
    if not present:
        return df
    pick = str(requested) if requested else next(
        (p for p in ("scotopic_flash", "photopic_flash") if p in present), "")
    if pick:
        sub = df[df["stimulus_type"].astype(str) == pick]
        if not sub.empty:
            return sub
    return df


def _fit_condition(xs, ys, do_fit, nr_slope, min_r2):
    """Per-condition Naka-Rushton fit.

    ``nr_slope`` > 0 fixes that slope (the user-set knob — adjust it in Figure-data to shape the
    curve / compare conditions at one slope). ``nr_slope`` == 0 auto-fits the slope per condition
    and, when the free fit is not supported (an under-constrained slope on a real-but-noisy
    responder, e.g. the 3'UTR rescue), falls back to a fixed physiological slope (n = 1) so the
    responder still gets a curve instead of vanishing. Truly flat/null conditions still fail both
    and stay unfit. The returned dict carries ``fixed`` so the table can flag a fixed-slope fit."""
    if not do_fit:
        return None
    if nr_slope > 0:
        f = _erg.naka_rushton_fit(xs, ys, fixed_n=nr_slope, min_r2=min_r2)
        if f:
            f["fixed"] = True
        return f
    f = _erg.naka_rushton_fit(xs, ys, min_r2=min_r2)  # free slope per condition
    if f:
        return f
    f = _erg.naka_rushton_fit(xs, ys, fixed_n=1.0, min_r2=min_r2)  # physiological fallback
    if f:
        f["fixed"] = True
    return f


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    df = pd.read_csv(data_path)
    value_col = str(params.get("value_col", "b_wave_uv"))
    do_fit = to_bool(params.get("fit", True))
    nr_slope = float(params.get("nr_slope", 0.0) or 0.0)   # 0 = auto (free + fixed fallback)
    min_r2 = float(params.get("min_r2", 0.3))

    missing = (_REQUIRED | {value_col}) - set(df.columns)
    if missing:
        raise ValueError(f"erg_intensity_response: input missing required columns {sorted(missing)}")

    df = _filter_stimulus(df, params.get("stimulus_type", ""))

    if "qc_excluded" in df.columns:
        df = df[~df["qc_excluded"].astype(str).str.strip().str.lower().isin(_TRUTHY)]

    if "condition_order" in df.columns and df["condition_order"].notna().any():
        order = (df.dropna(subset=["condition_order"]).sort_values("condition_order")
                 ["condition"].drop_duplicates().tolist())
    else:
        seen = list(dict.fromkeys(df["condition"].tolist()))
        order = ([c for c in _erg.CONDITION_ORDER if c in seen]
                 + [c for c in seen if c not in _erg.CONDITION_ORDER])

    cond_series, fits = [], {}
    for cond in order:
        cd = df[df["condition"] == cond]
        # Mean ± SEM b-wave at each flash intensity (across eyes), ordered by log intensity.
        xs, ys, sems = [], [], []
        for log_val, grp in cd.groupby("intensity_log_cd_s_m2"):
            st = _erg.summary_stats(grp[value_col].dropna().astype(float).tolist())
            if st["n"]:
                xs.append(float(log_val))
                ys.append(st["mean"])
                sems.append(st["sem"])
        if not xs:
            continue
        order_idx = sorted(range(len(xs)), key=lambda i: xs[i])
        xs = [xs[i] for i in order_idx]
        ys = [ys[i] for i in order_idx]
        sems = [sems[i] for i in order_idx]
        cond_series.append((cond, xs, ys, sems))
        fits[cond] = _fit_condition(xs, ys, do_fit, nr_slope, min_r2)

    if not cond_series:
        raise ValueError("erg_intensity_response: no series to plot after filtering")

    # Display unit (default µV → byte-identical). Peak = the largest mean b-wave (µV).
    peak_uv = max((max(ys) for (_c, _xs, ys, _s) in cond_series), default=0.0)
    unit = _erg.resolve_display_unit(params.get("display_unit", "uV"), peak_uv)
    factor = _erg.unit_factor(unit)
    spec, tbl_rows = ir_spec(cond_series, fits, title="b-wave intensity-response",
                             unit=unit, factor=factor)
    spec["table"] = table(
        ["condition", f"Vmax ({unit})", "log K (cd·s/m²)", "n", "R²"], tbl_rows,
        title="Naka-Rushton fit")
    return spec
