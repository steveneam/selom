"""Real forest engine — a DE / model-results table to effect ± CI.

Column detection goes through ``engine.columns`` (the ONE resolver every DE runner shares,
including the user column-override), so a limma/DESeq2/edgeR export drops straight in.

**Where the interval comes from, in strict order — and it is always declared:**

1. explicit bounds — a ``ci_lower``/``ci_upper`` (or ``conf.low``/``conf.high``) pair;
2. a standard error — ``effect ± z·se``;
3. the t-statistic — ``se = effect / t``, then as above. This is the limma/edgeR
   identity (``t = coef / stderr``), so it is a rearrangement of the table's own
   numbers, not a model assumption bolted on.

If none of the three exist the engine RAISES and names the columns it looked for. It
does not fall back to a fabricated interval — the interval is what the reader takes
away, so inventing one would be the worst possible failure of this skill.
"""

from engine.columns import normalize, resolve, resolve_significance
from skills._plotly import jsonable
from skills.forest.run import forest_spec, z_for

# Explicit-bound and standard-error column spellings, lowered. Checked in order.
_CI_LOW = ("ci_lower", "ci.low", "ci_low", "conf.low", "conf_low", "lower", "l95", "ci_l")
_CI_HIGH = ("ci_upper", "ci.high", "ci_high", "conf.high", "conf_high", "upper", "u95", "ci_u")
_SE = ("std_error", "stderror", "stderr", "std.error", "se", "lfcse", "sd")
_T = ("t_stat", "tstat", "t.value", "tvalue", "statistic", "t", "z")


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",")

    cols = normalize(df.columns)
    ov = params.get("_column_override")
    eff_col = resolve("logFC", df.columns, ov, cols=cols)
    if eff_col is None:
        raise ValueError(
            "forest needs an effect-size column (log2 fold-change / coefficient / estimate)"
        )
    label_col = resolve("gene", df.columns, ov, cols=cols)
    labels = (df[label_col].astype(str) if label_col
              else pd.Series(df.index.astype(str), index=df.index))
    p_col, p_adjusted = resolve_significance(ov, df.columns, cols)

    effect = df[eff_col].to_numpy(dtype=float)
    lo, hi, ci_source = _interval(df, cols, effect, params, np)

    p = df[p_col].to_numpy(dtype=float) if p_col is not None else None
    keep = np.isfinite(effect) & np.isfinite(lo) & np.isfinite(hi)
    if not keep.any():
        raise ValueError("forest: no rows with a finite effect and interval")

    idx = np.where(keep)[0]
    idx = _rank(idx, params, effect, p, labels, np)
    idx = idx[: max(2, int(params.get("top_n", 15)))]

    rows = [{"label": str(labels.iloc[i]), "effect": float(effect[i]),
             "lo": float(lo[i]), "hi": float(hi[i]),
             "p": (float(p[i]) if p is not None and np.isfinite(p[i]) else None)}
            for i in idx]

    x_label = str(eff_col)
    sig = "adjusted p" if p_adjusted else "raw p"
    title = f"Effect sizes — top {len(rows)} by {sig}" if _sort(params) == "significance" \
        else f"Effect sizes — top {len(rows)}"
    spec = forest_spec(rows, params, x_label, title, ci_source=ci_source)
    # Same honesty marker the DE runners write: the methods text drops its Benjamini-Hochberg
    # claim when the table only carried a raw p-value (see companions/methods.build_body).
    if p_col is not None and not p_adjusted:
        spec["layout"].setdefault("meta", {})["significance"] = "raw"
    return jsonable(spec)


def _pick(cols: dict, names: tuple) -> str | None:
    """First column whose lowered name EXACTLY matches one of ``names``, in order.

    Exact, not substring: ``se`` as a substring would match ``sequence`` / ``seq_depth``,
    and a mis-picked standard-error column silently rescales every interval on the plot.
    """
    for n in names:
        if n in cols:
            return cols[n]
    return None


def _interval(df, cols, effect, params, np):
    """``(lo, hi, source)`` — explicit bounds, else a standard error, else the t-statistic."""
    lo_col, hi_col = _pick(cols, _CI_LOW), _pick(cols, _CI_HIGH)
    if lo_col is not None and hi_col is not None:
        return (df[lo_col].to_numpy(dtype=float), df[hi_col].to_numpy(dtype=float),
                f"the table's own {lo_col}/{hi_col}")

    z = z_for(float(params.get("conf_level", 0.95)))
    se_col = _pick(cols, _SE)
    if se_col is not None:
        se = df[se_col].to_numpy(dtype=float)
        return effect - z * se, effect + z * se, f"standard error ({se_col})"

    t_col = _pick(cols, _T)
    if t_col is not None:
        t = df[t_col].to_numpy(dtype=float)
        # se = effect / t is exact where t != 0; a zero t means an effect of zero with no
        # information about its spread, so that row's interval is NaN and is filtered out
        # rather than being drawn as a point with no bar.
        with np.errstate(divide="ignore", invalid="ignore"):
            se = np.abs(effect / np.where(t == 0, np.nan, t))
        return effect - z * se, effect + z * se, f"the t-statistic ({t_col}), se = effect / t"

    raise ValueError(
        "forest needs an interval: explicit bounds "
        f"({'/'.join(_CI_LOW[:3])}…), a standard error ({'/'.join(_SE[:3])}…), "
        f"or a t-statistic ({'/'.join(_T[:3])}…) — none of these columns is present"
    )


def _sort(params) -> str:
    return str(params.get("sort_by") or "significance").strip().lower()


def _rank(idx, params, effect, p, labels, np):
    """Order the surviving rows by the requested key (ties keep table order)."""
    how = _sort(params)
    if how == "effect":
        return idx[np.argsort(-np.abs(effect[idx]), kind="stable")]
    if how == "label":
        return idx[np.argsort(labels.to_numpy()[idx], kind="stable")]
    if how == "none" or p is None:
        return idx
    key = np.where(np.isfinite(p[idx]), p[idx], np.inf)
    return idx[np.argsort(key, kind="stable")]
