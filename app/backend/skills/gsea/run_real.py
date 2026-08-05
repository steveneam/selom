"""Real GSEA engine — pre-ranked GSEA over a gene set or the GO library.

Ranks genes by a signed metric (log2FC or a statistic) and runs Gene Set Enrichment
Analysis. Engines (``engine`` param):

  * ``gseapy``    — gseapy.prerank (BSD-3). Exposes the running ES + leading-edge hits, so
                    the three-panel figure is drawn straight from the engine's own walk.
  * ``blitzgsea`` — blitzgsea (Apache-2.0). Gamma-distribution-fit p-values (closest to
                    fgsea for tiny q) and scales to thousands of sets; the table is
                    blitzgsea's, the curve is the weighted-KS walk over the same ranking for
                    display. OPT-IN ONLY: its first-import numba JIT was pathologically slow in
                    the dev environment (timed out), so ``auto`` never selects it — gseapy is
                    the validated default. Expected to work on a normal deploy box.
  * ``inhouse``   — the original numpy weighted-KS + permutation (single set only) — the
                    zero-extra-dep fallback when neither library is installed.
  * ``auto`` (default) — gseapy if importable, else blitzgsea, else inhouse.

DECISIONS #9 (corrected 2026-06-16): gseapy is BSD-3 and blitzgsea Apache-2.0 — both are
allowed GSEA *engines*; the only license constraint was MSigDB's *data*, so GSEA runs over
Selom's own license-clean GO library (gene_sets/library.py), never MSigDB. With no explicit
``gene_set``, the skill runs library mode against the ``gene_sets`` source (default ``go``).
Shares the three-panel figure with the stub via ``run._assemble``.
"""

import re
from importlib.util import find_spec

from engine.columns import normalize, resolve
from skills.gsea.run import _assemble

# GSEA ranks by a signed fold-change OR a signed statistic. The fold-change half is the shared DE
# vocabulary (reached through ``resolve("logFC", …)`` — single-sourced, no fork); RANK_EXTRA is
# gsea's own ranking-stat-only extras, passed as ``extra=`` so they are scanned AFTER the FC
# synonyms and a fold-change column still wins when both are present.
RANK_EXTRA = ("stat", "score", "signed_rank", "metric")
# Tokens too SHORT to substring-match safely: a bare "t" (limma's moderated t) is a substring of
# ordinary header words — on a real biomaRt/limma export it matched `entrezgene_id`, so a table with
# no fold-change column ranked genes by their Entrez ID (milestone review 2026-07-25, finding A5).
# These match the WHOLE lowered header only, and are tried last.
RANK_EXACT = ("t", "b", "z", "wald")
_MAX_PLOT = 800   # downsample the curve/metric to keep the spec light
_MIN_SIZE = 5
_MAX_SIZE = 2000
_SOURCE_ALIASES = {"": "go", "go": "go", "wikipathways": "wikipathways", "wiki": "wikipathways",
                   "curated": "curated", "reference": "reference", "all": "all"}


def run(data_path: str, params: dict) -> dict:
    import pandas as pd

    df = pd.read_csv(data_path)
    ranked = _ranked(df, params.get("_column_override"))
    sets, lib_mode = _resolve_sets(params, ranked)

    requested = str(params.get("engine", "auto")).strip().lower()
    engine = requested
    if engine == "auto":
        # gseapy.prerank is the validated default — it exposes the running-ES curve and gives
        # real NES/FDR. blitzgsea (gamma-fit, scales to thousands of sets) is opt-in only: its
        # numba JIT was pathologically slow in this environment (timed out), so `auto` never
        # selects it. For a large library (e.g. full GO ~7.7k sets) gseapy is slow (minutes) —
        # use a smaller `gene_sets` source or fewer `n_perm` for interactive runs.
        engine = "gseapy" if find_spec("gseapy") else ("blitzgsea" if find_spec("blitzgsea") else "inhouse")

    if engine == "gseapy" and find_spec("gseapy"):
        return _run_gseapy(ranked, sets, lib_mode, params)
    if engine == "blitzgsea" and find_spec("blitzgsea"):
        return _run_blitz(ranked, sets, lib_mode, params)
    if lib_mode:
        # The in-house weighted-KS fallback scores ONE set, so it cannot run library mode. Name the
        # cause the caller can act on: when the engine was CHOSEN the environment is not the
        # problem, and the old message ("needs gseapy or blitzgsea installed") blamed a missing
        # dependency that is in fact installed. Reachable from the UI since `engine` gained a
        # control, so a wrong diagnosis here is a wrong diagnosis a user actually sees.
        if requested == "inhouse":
            raise ValueError(
                "gsea: the in-house engine scores a single gene set and cannot run library mode. "
                "Paste your own gene set, or choose the gseapy / blitzgsea engine to score a library."
            )
        raise ValueError("library-mode GSEA needs gseapy or blitzgsea installed (uv sync --extra omics)")
    return _run_inhouse(ranked, sets, params)


def _perm_count(params: dict) -> int:
    """The permutation count gseapy/blitzgsea are actually given.

    Both floor it at 100, and ``or 1000`` turns an explicit 0 into the default — so the number the
    methods paragraph must quote is this one, never the raw param. `n_perm=50` runs 100 permutations
    and `n_perm=0` runs 1000; a paragraph quoting the param states a resolution the run never used.
    """
    return max(100, int(params.get("n_perm", 1000)) or 1000)


# ---- inputs ------------------------------------------------------------------
def _ranked(df, override=None):
    """A clean, de-duplicated descending rank: DataFrame[gene, metric]. Keeps the row with
    the largest |metric| per gene, then sorts by the signed metric descending. A user column-override
    (the AI map_columns action / a hand-set map) wins over synonym auto-detection, same as volcano."""
    import pandas as pd

    cols = normalize(df.columns)
    metric_col = (resolve("logFC", df.columns, override, extra=RANK_EXTRA, cols=cols)
                  or next((orig for low, orig in cols.items() if low in RANK_EXACT), None))
    if metric_col is None:
        raise ValueError("gsea needs a ranking metric column (log2 fold-change or a signed statistic)")
    # Gene label: EXACT tier first (A10) — a gene-ish annotation/count column is not the label.
    gene_col = resolve("gene", df.columns, override, cols=cols)
    genes = (df[gene_col] if gene_col else df.index.to_series()).astype(str).str.upper()
    metric = pd.to_numeric(df[metric_col], errors="coerce")
    # An honest verdict beats a garbage ranking: if the resolved column isn't really numeric (a gene
    # id / label that matched a synonym), say which column failed instead of silently ranking on
    # whatever coerced. GSEA on a handful of genes is meaningless anyway.
    if int(metric.notna().sum()) < _MIN_SIZE:
        raise ValueError(
            f"gsea: the ranking column {metric_col!r} has fewer than {_MIN_SIZE} numeric values — "
            "it does not look like a ranking metric. Map the ranking column explicitly "
            "(log2 fold-change or a signed statistic such as limma's t)."
        )
    sub = pd.DataFrame({"gene": genes, "metric": metric}).dropna(subset=["metric"])
    sub = sub.assign(_abs=sub["metric"].abs()).sort_values("_abs", ascending=False)
    sub = sub.drop_duplicates("gene", keep="first")
    return sub.sort_values("metric", ascending=False)[["gene", "metric"]].reset_index(drop=True)


def _resolve_sets(params, ranked):
    """The gene sets to test + whether this is library mode. An explicit ``gene_set`` (pasted
    members) → single-set mode; otherwise the ``gene_sets`` source (default GO) → library mode."""
    explicit = _parse_panel(params.get("gene_set", ""))
    if explicit:
        set_name = str(params.get("set_name", "Gene set")) or "Gene set"
        return {set_name: sorted(explicit)}, False
    from gene_sets.library import load_collection

    token = _SOURCE_ALIASES.get(str(params.get("gene_sets", "go")).strip().lower(), "go")
    sets = load_collection(token)
    if not sets:
        raise ValueError(f"gsea: gene-set library '{token}' is empty or unavailable")
    return sets, True


# ---- gseapy ------------------------------------------------------------------
def _run_gseapy(ranked, sets, lib_mode, params):
    import gseapy as gp
    import numpy as np

    from skills._plotly import jsonable

    kw = dict(
        rnk=ranked, gene_sets={k: list(v) for k, v in sets.items()},
        min_size=_MIN_SIZE, max_size=_MAX_SIZE,
        permutation_num=_perm_count(params),
        seed=0, threads=4, no_plot=True, outdir=None, verbose=False,
    )
    weight = float(params.get("weight", 1.0))
    try:  # gseapy 1.2 renamed weighted_score_type -> weight
        pre = gp.prerank(**kw, weight=weight)
    except TypeError:
        pre = gp.prerank(**kw, weighted_score_type=weight)
    res = pre.res2d.copy()
    for c in ("ES", "NES", "NOM p-val", "FDR q-val"):
        if c in res.columns:
            res[c] = _num(res[c])
    if res.empty:
        raise ValueError("gsea: no gene set reached the minimum size against this ranked list")
    term = _pick_term(res, sets, lib_mode)
    r = pre.results[term]

    RES = np.asarray(r["RES"], dtype=float)
    metric = _ranking_values(pre, ranked, len(RES))
    hits = [int(i) for i in r.get("hits", [])]
    es, nes, pval, fdr = float(r["es"]), float(r["nes"]), float(r["pval"]), float(r["fdr"])
    return _figure(RES, metric, hits, es, nes, pval, fdr, _label(term, params, lib_mode),
                   res if lib_mode else None, jsonable,
                   run=_run_meta("gseapy", _perm_count(params), lib_mode))


def _ranking_values(pre, ranked, n):
    """The signed metric aligned with the engine's walk (gseapy's own ranking if exposed)."""
    import numpy as np

    rk = getattr(pre, "ranking", None)
    if rk is not None and len(rk) == n:
        return np.asarray(getattr(rk, "values", rk), dtype=float)
    return ranked["metric"].to_numpy(dtype=float)[:n]


# ---- blitzgsea ---------------------------------------------------------------
def _run_blitz(ranked, sets, lib_mode, params):
    import blitzgsea as blitz
    import numpy as np

    from skills._plotly import jsonable

    sig = ranked.rename(columns={"gene": 0, "metric": 1})[[0, 1]]
    res = blitz.gsea(sig, {k: list(v) for k, v in sets.items()},
                     permutations=_perm_count(params), seed=0)
    res = res.reset_index().rename(columns={"index": "Term"}) if "Term" not in res.columns else res
    if res.empty:
        raise ValueError("gsea: no gene set reached the minimum size against this ranked list")
    # Normalize blitzgsea's columns to the shared names used by _pick_term / the table.
    ren = {"es": "ES", "nes": "NES", "pval": "NOM p-val", "fdr": "FDR q-val", "sidak": "FDR q-val"}
    res = res.rename(columns={k: v for k, v in ren.items() if k in res.columns and v not in res.columns})
    for c in ("ES", "NES", "NOM p-val", "FDR q-val"):
        if c in res.columns:
            res[c] = _num(res[c])
    term = _pick_term(res, sets, lib_mode)
    row = res[res["Term"] == term].iloc[0]

    # blitzgsea reports the stats; draw the running-ES curve from the weighted-KS walk so the
    # three-panel figure matches (curve shape is method-agnostic; the labels are blitzgsea's).
    m = ranked["metric"].to_numpy(dtype=float)
    g = ranked["gene"].to_numpy()
    panel = {x.upper() for x in sets[term]}
    hit = np.fromiter((x in panel for x in g), dtype=bool, count=g.size)
    RES, es, _peak = _running_es(m, hit, float(params.get("weight", 1.0)), np)
    nes = float(row.get("NES", es))
    pval = float(row.get("NOM p-val", float("nan")))
    fdr = float(row.get("FDR q-val", float("nan")))
    hits = [int(i) for i in np.where(hit)[0]]
    return _figure(RES, m, hits, float(es), nes, pval, fdr, _label(term, params, lib_mode),
                   res if lib_mode else None, jsonable,
                   run=_run_meta("blitzgsea", _perm_count(params), lib_mode))


# ---- in-house fallback (single set) ------------------------------------------
def _run_inhouse(ranked, sets, params):
    import numpy as np

    from skills._plotly import jsonable

    set_name, members = next(iter(sets.items()))
    g = ranked["gene"].to_numpy()
    m = ranked["metric"].to_numpy(dtype=float)
    panel = {x.upper() for x in members}
    hit = np.fromiter((x in panel for x in g), dtype=bool, count=g.size)
    k = int(hit.sum())
    if k < 2:
        raise ValueError(f"only {k} gene_set members found in the ranked list (need >=2)")
    p = float(params.get("weight", 1.0))
    RES, es, _peak = _running_es(m, hit, p, np)
    # NOT `_perm_count`: the in-house path honours the raw value, and <=0 means it runs no
    # permutation test at all (p is left at 1.0). The two engines genuinely differ here, so the
    # recorded fact differs with them rather than quoting one floor for both.
    n_perm = int(params.get("n_perm", 1000))
    nes, pval = _nes_p(m, k, p, es, n_perm, np)
    hits = [int(i) for i in np.where(hit)[0]]
    return _figure(RES, m, hits, es, nes, pval, None, set_name, None, jsonable,
                   run=_run_meta("inhouse", max(0, n_perm), False))


# ---- shared figure assembly --------------------------------------------------
def _run_meta(engine: str, n_perm: int, fdr_corrected: bool) -> dict:
    """What the run RESOLVED — the three facts the parameters cannot answer.

    ``engine`` defaults to ``"auto"``, which picks gseapy / blitzgsea / in-house from what is
    importable at run time, so the params alone never say which statistics were computed. The
    permutation count is floored per engine (see ``_perm_count``). And a Benjamini-Hochberg FDR
    across sets exists only in LIBRARY mode — a pasted single set has nothing to correct across,
    and the in-house engine computes no q at all.

    Lifted by ``methods.build_body`` as ``_gsea_run`` (the ``meta.significance`` pattern), so the
    paragraph states what ran instead of what was asked for.
    """
    return {"engine": engine, "n_perm": int(n_perm), "fdr_corrected": bool(fdr_corrected)}


def _figure(RES, metric, hits, es, nes, pval, fdr, label, res_table, jsonable, run=None):
    import numpy as np

    RES = np.asarray(RES, dtype=float)
    metric = np.asarray(metric, dtype=float)
    n = RES.size
    peak = int(np.argmax(np.abs(RES))) if n else 0
    step = max(1, n // _MAX_PLOT)
    idx = list(range(0, n, step))
    if n and idx[-1] != n - 1:
        idx.append(n - 1)
    x_plot = [i + 1 for i in idx]
    y_es = [round(float(RES[i]), 4) for i in idx]
    y_m = [round(float(metric[i]), 4) for i in idx]
    hit_x = [i + 1 for i in hits]
    table = _results_table(res_table) if res_table is not None else None
    spec = _assemble(
        x_plot, y_es, peak + 1, round(float(es), 4), hit_x, x_plot, y_m,
        round(float(nes), 4), _safe(pval), label, fdr=_safe(fdr), table=table,
    )
    if run is not None:
        spec["layout"].setdefault("meta", {})["gsea"] = run
    return jsonable(spec)


def _results_table(res):
    """Top enriched sets as a Statistics table (most significant first)."""
    from skills._table import table

    sort_cols = [c for c in ("FDR q-val", "NOM p-val") if c in res.columns]
    ordered = res.sort_values(sort_cols, ascending=True) if sort_cols else res
    rows = []
    for _, r in ordered.head(25).iterrows():
        rows.append([
            str(r.get("Term", "")),
            round(float(r["NES"]), 3) if "NES" in res.columns and _isnum(r.get("NES")) else None,
            _sig(r.get("NOM p-val")), _sig(r.get("FDR q-val")),
        ])
    n_sig = int((res["FDR q-val"] <= 0.25).sum()) if "FDR q-val" in res.columns else len(res)
    title = f"GSEA — {len(res)} sets tested, {n_sig} at FDR<=0.25 (top {min(25, len(res))})"
    return table(["gene set", "NES", "NOM p", "FDR q"], rows, title)


# ---- helpers -----------------------------------------------------------------
def _pick_term(res, sets, lib_mode):
    if not lib_mode:
        return next(iter(sets))  # the single requested set
    sort_cols = [c for c in ("FDR q-val", "NOM p-val") if c in res.columns]
    ordered = res.sort_values(sort_cols, ascending=True) if sort_cols else res
    return str(ordered.iloc[0]["Term"])


def _label(term, params, lib_mode):
    if lib_mode:
        return str(term)
    return str(params.get("set_name", "Gene set")) or "Gene set"


def _running_es(metric, hit, p, np):
    w = np.abs(metric) ** p
    hit_w = w * hit
    tot = hit_w.sum() or 1.0
    p_hit = np.cumsum(hit_w) / tot
    n_miss = max(int((~hit).sum()), 1)
    p_miss = np.cumsum((~hit).astype(float)) / n_miss
    running = p_hit - p_miss
    peak = int(np.argmax(np.abs(running)))
    return running, float(running[peak]), peak


def _nes_p(metric, k, p, es, n_perm, np):
    if n_perm <= 0:
        return (es, 1.0)
    w = np.abs(metric) ** p
    n = metric.size
    rng = np.random.default_rng(0)
    null = np.empty(n_perm)
    for i in range(n_perm):
        h = np.zeros(n, dtype=bool)
        h[rng.choice(n, size=k, replace=False)] = True
        hit_w = w * h
        tot = hit_w.sum() or 1.0
        r = np.cumsum(hit_w) / tot - np.cumsum((~h).astype(float)) / (n - k)
        null[i] = r[np.argmax(np.abs(r))]
    same = null[(null >= 0) == (es >= 0)]
    denom = float(np.abs(same).mean()) if same.size else (float(np.abs(null).mean()) or 1.0)
    nes = es / denom if denom else 0.0
    if es >= 0:
        pval = (int(np.sum(null >= es)) + 1) / (n_perm + 1)
    else:
        pval = (int(np.sum(null <= es)) + 1) / (n_perm + 1)
    return float(nes), float(pval)


def _num(series):
    import pandas as pd
    return pd.to_numeric(series, errors="coerce")


def _isnum(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _safe(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    import math
    return None if math.isnan(f) else f


def _sig(v, digits=3):
    f = _safe(v)
    if f is None:
        return None
    return float(f"{f:.{digits}g}")


def _parse_panel(raw) -> set:
    return {tok.upper() for tok in re.split(r"[,\s]+", str(raw or "").strip()) if tok}

