"""Real Q-Q engine — a results table's p-value column to observed-vs-expected quantiles.

λ (genomic inflation) is the median observed chi-square over the null median:
``median(qchisq(1 - p, df=1)) / qchisq(0.5, df=1)``. Computed on the RAW p-values —
never on an adjusted column, which is monotone-transformed and would make λ meaningless.
So the resolver is asked for the raw tier explicitly: this is the one skill in the repo
that must NOT take the adjusted-first column every other DE runner wants.

Downsampling, when a table is larger than ``max_points``: the whole significant TAIL is
kept and only the bulk is thinned on a fixed stride. Uniform sampling of a 20 000-gene
table would drop the exact points a Q-Q plot is read for. λ and the reported n are always
computed on ALL finite p-values, before any thinning, so the number never depends on the
plot's resolution.
"""

from engine.columns import normalize, pick_raw_significance, resolve
from skills._plotly import jsonable
from skills.qq.run import qq_spec

# Chi-square(1) median — the λ denominator. Constant, so λ needs no scipy for the divisor.
_CHI2_1DF_MEDIAN = 0.4549364231195728


def run(data_path: str, params: dict) -> dict:
    import numpy as np
    import pandas as pd

    low = str(data_path).lower()
    if low.endswith((".xlsx", ".xls")):
        df = pd.read_excel(data_path)
    else:
        df = pd.read_csv(data_path, sep="\t" if low.endswith(".tsv") else ",")

    cols = normalize(df.columns)
    p_col = _raw_p_column(df, cols, params)
    if p_col is None:
        raise ValueError(
            "qq needs a RAW p-value column (P.Value / pvalue / p_val) — an adjusted column "
            "is monotone-transformed, so its quantiles and λ would be meaningless"
        )
    label_col = _label_column(df, cols, params)
    labels_all = (df[label_col].astype(str).to_numpy() if label_col
                  else df.index.astype(str).to_numpy())

    p_all = pd.to_numeric(df[p_col], errors="coerce").to_numpy(dtype=float)
    ok = np.isfinite(p_all) & (p_all > 0) & (p_all <= 1)
    p = p_all[ok]
    labels = labels_all[ok]
    n = int(p.size)
    if n < 2:
        raise ValueError(f"qq: column {p_col!r} holds fewer than 2 usable p-values in (0, 1]")

    order = np.argsort(p)                       # most significant first
    p, labels = p[order], labels[order]
    lam = _lambda_gc(p, np)

    ranks = np.arange(1, n + 1)
    expected = -np.log10((ranks - 0.5) / n)     # descending
    observed = -np.log10(p)

    band = _band(ranks, n, np)
    keep = _thin(n, int(params.get("max_points", 6000)), np)

    spec = qq_spec(
        [round(float(v), 4) for v in observed[keep]],
        [round(float(v), 4) for v in expected[keep]],
        [str(v) for v in labels[keep]],
        params, n_total=n, lam=lam,
        band=([round(float(v), 4) for v in band[0][keep]],
              [round(float(v), 4) for v in band[1][keep]]) if band else None,
        title=f"P-value Q-Q — {p_col}",
    )
    return jsonable(spec)


def _raw_p_column(df, cols: dict, params: dict):
    """The RAW p-value column: an explicit ``p_col`` if given, else the shared resolver.

    Deliberately NOT ``resolve_significance`` — that one is adjusted-tier-first by design, because
    every other DE runner wants the corrected column. The raw-first read lives in
    ``engine.columns.pick_raw_significance`` (the same one home, not a copy here), and the reason
    it has to exist is documented there.

    An explicitly named column is taken as-is, adjusted or not: the user overriding the resolver is
    a stated intent, and the λ caveat is already printed in the Statistics table title.
    """
    named = str(params.get("p_col") or "").strip()
    if named:
        if named in df.columns:
            return named
        if named.lower() in cols:
            return cols[named.lower()]
        raise ValueError(
            f"qq: no such column {named!r} (available: {', '.join(map(str, df.columns))})"
        )
    return pick_raw_significance(cols)


def _label_column(df, cols: dict, params: dict):
    return resolve("gene", df.columns, params.get("_column_override"), cols=cols)


def _lambda_gc(p_sorted, np) -> float:
    """Median chi-square(1) inflation factor from sorted p-values."""
    from scipy.stats import chi2

    chi = chi2.isf(p_sorted, 1)
    chi = chi[np.isfinite(chi)]
    if chi.size == 0:
        return 1.0
    return float(np.median(chi) / _CHI2_1DF_MEDIAN)


def _band(ranks, n: int, np):
    """Pointwise 95% band from the Beta(i, n−i+1) order-statistic distribution, on −log10.

    Returns ``(lo, hi)`` aligned to ``ranks``; ``None`` if scipy is unavailable, in which
    case the figure simply omits the band rather than drawing an approximate one.
    """
    try:
        from scipy.stats import beta
    except ImportError:  # pragma: no cover — scipy is a core dep; guarded, not assumed
        return None
    a = ranks
    b = n - ranks + 1
    # A p-value's UPPER confidence bound is the LOWER -log10 bound, hence the swap.
    lo = -np.log10(beta.ppf(0.975, a, b))
    hi = -np.log10(beta.ppf(0.025, a, b))
    return lo, hi


def _thin(n: int, max_points: int, np):
    """Index mask: every point in the tail, a fixed stride through the bulk."""
    if max_points <= 0 or n <= max_points:
        return np.arange(n)
    tail = max(1, max_points // 2)             # the most significant half of the budget
    stride = max(2, int(np.ceil((n - tail) / max(1, max_points - tail))))
    bulk = np.arange(tail, n, stride)
    return np.concatenate([np.arange(tail), bulk])
