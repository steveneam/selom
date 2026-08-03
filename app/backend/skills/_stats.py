"""Shared significance-annotation engine — the ``pairs=`` feature, for **any** categorical skill.

WHY THIS MODULE EXISTS. Six cnsplots functions take ``pairs=`` (run the pairwise test, draw the
bracket, print the stars) and Selom had it in exactly one shape: ``_charts.sig_brackets``, whose
signature is *bar*-specific — it derives the bracket baseline from ``means``/``his``/``pt_y``, which
a box or violin does not have. So every other categorical skill either went without or would have
hand-rolled it a second time (the ERG work already hand-rolled it once). This module is the one
home: the statistics, the multiple-comparison correction, the bracket geometry, and the ``n=``
labels, all independent of which *kind* of trace sits underneath.

LAYERING. This is a leaf: it imports nothing from ``skills``. ``_charts`` imports *from here* and
re-exports :func:`sig_stars` / :func:`compare_groups` so its own published contract (and
``_erg``'s, which re-exports from ``_charts``) is unchanged — the general module must not depend on
the specific one. ``_charts.sig_brackets`` now delegates here, which is what keeps the ERG figures
byte-identical while every other skill gets the same brackets.

WHAT IS DELIBERATELY *NOT* HERE. ``statannotations`` (BSD-3) is the reference for the statistics and
the bracket geometry, and that is all Selom takes from it — it is a matplotlib/seaborn *artist*, and
Selom emits an editable Plotly spec. A port of the numbers, not a dependency on the drawing.
"""
from __future__ import annotations

import math

# GraphPad star thresholds — the convention every one of these figures is read against.
_STAR_THRESHOLDS = ((0.001, "***"), (0.01, "**"), (0.05, "*"))

# Bracket geometry, as fractions of the data range. These reproduce _charts.sig_brackets exactly,
# which is what keeps the ERG goldens byte-identical after it was moved here.
_STEP_FRAC = 0.12    # vertical gap between stacked brackets
_TICK_FRAC = 0.35    # end-tick length, as a fraction of the step
_LABEL_FRAC = 0.4    # star offset above the bracket line, as a fraction of the tick
_LINE = {"color": "#333333", "width": 1.2}


# --- statistics primitives (pure) --------------------------------------------------------
def sig_stars(p) -> str:
    """p-value → significance stars (GraphPad convention): ``***`` <0.001 · ``**`` <0.01 ·
    ``*`` <0.05 · ``ns`` otherwise. None/non-finite → ``ns``."""
    if p is None:
        return "ns"
    try:
        p = float(p)
    except (TypeError, ValueError):
        return "ns"
    if not math.isfinite(p):
        return "ns"
    for threshold, stars in _STAR_THRESHOLDS:
        if p < threshold:
            return stars
    return "ns"


def compare_groups(a, b, test: str = "welch"):
    """Two-group two-sided p-value, or None when either side has n<2. ``test``: ``welch`` (default,
    unequal-variance t) · ``student`` (equal-variance t) · ``mannwhitney`` (rank). scipy lazy."""
    a = [float(x) for x in a if x is not None and math.isfinite(float(x))]
    b = [float(x) for x in b if x is not None and math.isfinite(float(x))]
    if len(a) < 2 or len(b) < 2:
        return None
    from scipy import stats

    t = str(test or "welch").strip().lower()
    try:
        if t in ("mannwhitney", "mwu", "u"):
            return float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue)
        return float(stats.ttest_ind(a, b, equal_var=(t == "student")).pvalue)
    except (ValueError, ZeroDivisionError):
        return None


TEST_LABEL = {
    "welch": "Welch t",
    "student": "Student t",
    "mannwhitney": "Mann-Whitney U",
    "mwu": "Mann-Whitney U",
    "u": "Mann-Whitney U",
}


def adjust_pvalues(pvals, method: str = "none"):
    """Correct a family of p-values for multiple comparisons → a list the same length, ``None``
    passed through in place (a pair that could not be tested does not join the family, and must not
    shift anyone else's rank).

    ``method``: ``none`` (default — returns the input unchanged) · ``bonferroni`` (p x m, capped at
    1) · ``bh`` / ``fdr`` (Benjamini-Hochberg step-up, monotonicity enforced). Pure Python, so a
    figure never depends on scipy to be *honest* about its own multiplicity.

    Why this is not optional-in-spirit: drawing six brackets from six uncorrected tests is six shots
    at p<0.05. The default stays ``none`` because that is what the existing figures already do and a
    silent change would move published numbers -- but the caller that asks for correction gets a
    column named for what it actually holds (see :func:`pairs_table`).
    """
    m = str(method or "none").strip().lower()
    vals = list(pvals)
    if m in ("", "none", "off"):
        return vals
    idx = [i for i, p in enumerate(vals) if p is not None and math.isfinite(float(p))]
    n = len(idx)
    if n == 0:
        return vals
    out = list(vals)
    if m in ("bonferroni", "bonf"):
        for i in idx:
            out[i] = min(1.0, float(vals[i]) * n)
        return out
    if m in ("bh", "fdr", "fdr_bh", "benjamini-hochberg"):
        ranked = sorted(idx, key=lambda i: float(vals[i]))
        prev = 1.0
        # Walk largest p first so the step-up monotonicity (an adjusted p never exceeds a
        # larger-p neighbour's) is enforced by construction.
        for rank in range(n, 0, -1):
            i = ranked[rank - 1]
            prev = min(prev, float(vals[i]) * n / rank)
            out[i] = min(1.0, prev)
        return out
    return vals


# --- the pairs contract ------------------------------------------------------------------
def parse_pairs(raw):
    """``"A~B, C~D"`` (or ``;``-separated) → ``[(a, b, override|None), …]``.

    An optional ``:`` suffix overrides the stars — ``"A~B:**"`` (literal stars) or ``"A~B:0.003"``
    (a p-value Selom converts) — else Selom computes them. Empty / malformed chunks are skipped, so
    a typo yields a figure with fewer brackets rather than a failed run. Already-structured input
    (a list of tuples, e.g. from a JSON param) passes through normalized."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        out = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                a, b = str(item[0]).strip(), str(item[1]).strip()
                override = str(item[2]).strip() if len(item) > 2 and item[2] else None
                if a and b:
                    out.append((a, b, override or None))
        return out
    out = []
    for chunk in str(raw).replace(";", ",").split(","):
        pair, _, override = chunk.partition(":")
        parts = [p.strip() for p in pair.split("~")]
        if len(parts) == 2 and parts[0] and parts[1]:
            out.append((parts[0], parts[1], override.strip() or None))
    return out


def resolve_stars(override, vals_a, vals_b, test: str = "welch"):
    """Stars for one comparison → ``(stars, p)``. A manual override (``"**"`` / a literal p like
    ``"0.003"``) wins when given, else the test runs on the raw values (the owner's "both
    available" — Selom computes, but every star stays overridable). ``p`` is ``None`` for a literal
    star override, because no p-value was computed and the table must not invent one."""
    if override:
        o = str(override).strip()
        if o in ("*", "**", "***", "ns"):
            return o, None
        try:
            p = float(o)
        except ValueError:
            pass
        else:
            return sig_stars(p), p
    p = compare_groups(vals_a, vals_b, test=test)
    return sig_stars(p), p


def test_pairs(pairs, values_of, *, test: str = "welch", correction: str = "none"):
    """Run every pair → an ordered list of result dicts, the single source both the brackets and the
    Statistics table read from (so the figure and its numbers can never disagree).

    Each result: ``{a, b, n_a, n_b, p, p_adj, stars, override}``. Pairs naming an unknown key are
    dropped. ``stars`` reflects the **adjusted** p when a correction is in force — otherwise the
    correction would change the table and leave the figure claiming the uncorrected result."""
    resolved = []
    for a, b, override in pairs:
        if a not in values_of or b not in values_of:
            continue
        stars, p = resolve_stars(override, values_of.get(a, []), values_of.get(b, []), test)
        resolved.append({"a": a, "b": b, "override": override,
                         "n_a": _n(values_of.get(a, [])), "n_b": _n(values_of.get(b, [])),
                         "p": p, "stars": stars})
    # Only computed p-values join the correction family; a literal star override never had one.
    adj = adjust_pvalues([r["p"] for r in resolved], correction)
    corrected = str(correction or "none").strip().lower() not in ("", "none", "off")
    for r, pa in zip(resolved, adj):
        r["p_adj"] = pa
        if corrected and pa is not None and not r["override"]:
            r["stars"] = sig_stars(pa)
    return resolved


def _n(values) -> int:
    return sum(1 for v in values if v is not None and math.isfinite(float(v)))


# --- geometry ----------------------------------------------------------------------------
def bracket_shapes(results, idx_of, data_top: float, *, orientation: str = "v", span=None):
    """Stacked significance brackets → ``(shapes, annotations, top)``.

    ``results`` is :func:`test_pairs` output; ``idx_of`` maps a category key to its axis position
    (0-based, which is where Plotly puts the i-th category on a ``type: "category"`` axis, so this
    works for bar, box and violin alike); ``data_top`` is the highest drawn ink the brackets must
    clear — the caller knows its own geometry (a bar knows mean+error, a box knows its outliers).
    ``top`` is the new axis ceiling so the caller can grow the range and avoid clipping.

    ``orientation``: ``v`` (categories on x, brackets rise above) or ``h`` (categories on y,
    brackets extend to the right) — a horizontal box plot needs its brackets rotated with it.

    ``span`` sizes the vertical gap between stacked brackets, and defaults to ``data_top``. That
    default is only right for a plot **anchored at zero** — a bar chart, where the top IS the span.
    A box or violin is not anchored: values clustered around 100 have a data_top of ~101 and a span
    of ~1, and sizing the gap off the top would fling the brackets ~12 units off the plot. Any
    caller whose axis does not start at zero passes its real ``max - min``.

    Geometry is otherwise unchanged from the bar-only implementation this replaces, which is what
    keeps the ERG goldens byte-identical.
    """
    step = ((data_top if span is None else span) or 1.0) * _STEP_FRAC
    tick = step * _TICK_FRAC
    horizontal = str(orientation or "v").lower().startswith("h")
    # On a horizontal plot the categories live on y and the value axis is x, so every reference
    # and every coordinate pair swaps. Naming them once here keeps the drawing code single-path.
    cat_ref, val_ref = ("y", "x") if horizontal else ("x", "y")

    shapes, annos = [], []
    level = 0
    for r in results:
        if r["a"] not in idx_of or r["b"] not in idx_of:
            continue
        ia, ib = idx_of[r["a"]], idx_of[r["b"]]
        c0, c1 = min(ia, ib), max(ia, ib)
        v = data_top + step * (level + 1)
        shapes.append(_line(cat_ref, val_ref, c0, c1, v, v))
        for edge in (c0, c1):  # end ticks, pointing back toward the data
            shapes.append(_line(cat_ref, val_ref, edge, edge, v, v - tick))
        stars = r["stars"]
        anno = {"xref": "x", "yref": "y", "text": stars, "showarrow": False,
                "font": {"size": 14 if stars != "ns" else 11, "color": "#333333"}}
        anno[cat_ref] = (c0 + c1) / 2.0
        anno[val_ref] = round(v + tick * _LABEL_FRAC, 4)
        # Anchor the star off the bracket's outer edge, whichever way "outer" points.
        anno["xanchor" if horizontal else "yanchor"] = "left" if horizontal else "bottom"
        annos.append(anno)
        level += 1
    return shapes, annos, (data_top + step * (level + 1) if level else data_top)


def _line(cat_ref, val_ref, c0, c1, v0, v1) -> dict:
    """One bracket segment in category/value space, emitted in Plotly's x/y space."""
    shape = {"type": "line", "xref": "x", "yref": "y", "line": dict(_LINE)}
    shape[f"{cat_ref}0"], shape[f"{cat_ref}1"] = c0, c1
    shape[f"{val_ref}0"], shape[f"{val_ref}1"] = round(v0, 4), round(v1, 4)
    return shape


# --- n= labels (cnsplots' add_count) -----------------------------------------------------
def count_labels(order, values_of, labels=None, *, template: str = "{label}<br>n={n}") -> dict:
    """``{key: "Label<br>n=12"}`` for every key in ``order`` — cnsplots' ``add_count=True``.

    Returned as a label *mapping* rather than as annotations on purpose: a bar skill applies it to
    ``xaxis.ticktext``, a box skill applies it to each trace's ``name``, and both keep the count
    welded to the category label so it cannot drift out of alignment when the axis reorders."""
    labels = labels or {}
    return {k: template.format(label=labels.get(k, str(k)), n=_n(values_of.get(k, [])))
            for k in order}


# --- the hue / order / hue_order grouping contract ---------------------------------------
def parse_list(raw):
    """``"a, b, c"`` → ``["a", "b", "c"]``; a list passes through as strings; blank → ``[]``.
    The shared parser behind ``order`` and ``hue_order``, so every skill spells them the same way."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [s.strip() for s in str(raw).replace(";", ",").split(",") if s.strip()]


def resolve_order(keys, order=None, *, natural=None):
    """The final category order: every key named in ``order`` that actually exists, in the order
    given, then the remaining keys in their ``natural`` order (default: the order ``keys`` arrived).

    Unknown names in ``order`` are ignored rather than raising — a stale category name in a saved
    figure spec should reorder what it can, not fail the run. Deduplicates, so a key repeated in
    ``order`` appears once."""
    keys = list(keys)
    known = set(keys)
    seen, out = set(), []
    for k in parse_list(order):
        if k in known and k not in seen:
            seen.add(k)
            out.append(k)
    for k in (natural if natural is not None else keys):
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


# --- the Statistics table ----------------------------------------------------------------
def pairs_table(results, *, test: str = "welch", correction: str = "none",
                title: str = "Pairwise comparisons") -> dict | None:
    """The pairwise results as a Statistics table (``skills._table.table`` shape), or ``None`` when
    nothing was tested — so a figure with no ``pairs=`` attaches no empty node.

    The p column is named for what it **holds**: ``p`` uncorrected, and a second ``p (<method>)``
    column only when a correction actually ran. A column headed for an adjustment that did not
    happen is the same printed-vs-computed lie ``_table.de_table`` guards against, and it is the
    defect that shipped once already (WS3.1: an axis reading "adjusted" over raw p-values)."""
    from skills._table import _sig, table

    if not results:
        return None
    corrected = str(correction or "none").strip().lower() not in ("", "none", "off")
    label = TEST_LABEL.get(str(test or "welch").strip().lower(), str(test))
    columns = ["group A", "group B", "n A", "n B", "p"]
    if corrected:
        columns.append(f"p ({str(correction).strip().lower()})")
    columns.append("")
    rows = []
    for r in results:
        # An overridden star carries no computed p — print the override, never a fabricated number.
        p_cell = "set by hand" if (r["override"] and r["p"] is None) else (
            _sig(r["p"]) if r["p"] is not None else "n/a")
        row = [r["a"], r["b"], r["n_a"], r["n_b"], p_cell]
        if corrected:
            row.append(_sig(r["p_adj"]) if r["p_adj"] is not None else p_cell)
        row.append(r["stars"])
        rows.append(row)
    note = f"{label}, two-sided"
    if corrected:
        note += f", {str(correction).strip().lower()}-corrected"
    return table(columns, rows, f"{title} ({note})")
