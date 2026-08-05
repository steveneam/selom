"""Confusion / agreement matrix — how two labellings of the SAME rows line up.

The classifier reading (predicted vs true) is one use. The one that earns this skill a place in an
omics tool is the other: **two annotations of the same cells** — Leiden clusters vs a reference
cell-type call, a transferred label vs a manual one, this run's clustering vs last run's. Validating
an annotation is a cross-tabulation, and Selom had no way to draw one.

Deliberately NOT a `heatmap` param. `heatmap` is a z-scored expression matrix — genes x samples,
diverging around zero, clustered. A contingency table is counts: it has a floor at zero, no
meaningful midpoint, and its rows and columns are two *label vocabularies* rather than features and
observations. Sharing the spec would mean a `mode` flag that swapped the colour scale, the
normalization, the text layer and the statistics — everything except the word "heatmap".

The honesty line this skill has to hold: **diagonal metrics only when a diagonal exists.** Accuracy
and Cohen's κ are defined against a shared label vocabulary. Leiden ids against cell-type names have
no diagonal at all, so an "accuracy" there would be a number computed from an alignment nobody
declared. When the vocabularies do not match, the matrix and its marginals are reported and the
metrics are refused by name — see :func:`_agreement`.
"""

from skills._engine import to_bool, use_real_engine
from skills._plotly import jsonable
from skills._stats import parse_list
from skills._table import table

# Cell text is dropped above this many cells — past ~400 the numbers are unreadable anyway and the
# annotation layer is what makes a large matrix slow to edit in the browser.
_MAX_ANNOTATED_CELLS = 400
_MAX_LABELS = 60


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("pandas"):
        from skills.confusion.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


def _stub_figure(params: dict) -> dict:
    """Deterministic 3x3 annotation-agreement matrix (shared vocabulary, so metrics apply)."""
    rows = ["Rods", "Cones", "Muller glia"]
    cols = ["Rods", "Cones", "Muller glia"]
    counts = [[812, 24, 9],
              [31, 402, 12],
              [14, 7, 265]]
    return confusion_spec(counts, rows, cols, params,
                          "reference annotation", "predicted annotation",
                          "Annotation agreement (stub)")


def _normalize(counts, mode: str):
    """Counts → the displayed value + how to label it. ``mode``: none | row | column | all.

    Row-normalized is the standard confusion reading (per-true-class recall). A row or column that
    is entirely zero stays zero rather than becoming NaN — an unobserved label is a real fact about
    the data, and a NaN would punch a hole in the colour scale.
    """
    m = str(mode or "none").strip().lower()
    if m in ("", "none", "off", "count", "counts"):
        return [list(map(float, r)) for r in counts], "count", False
    if m in ("row", "rows", "true", "recall"):
        out = []
        for r in counts:
            total = float(sum(r))
            out.append([(v / total * 100.0 if total else 0.0) for v in r])
        return out, "row %", True
    if m in ("column", "col", "columns", "predicted", "precision"):
        totals = [float(sum(col)) for col in zip(*counts)] if counts else []
        out = [[(v / totals[j] * 100.0 if totals[j] else 0.0) for j, v in enumerate(r)]
               for r in counts]
        return out, "column %", True
    total = float(sum(sum(r) for r in counts))
    out = [[(v / total * 100.0 if total else 0.0) for v in r] for r in counts]
    return out, "% of all", True


def _agreement(counts, row_labels, col_labels) -> tuple[float, float | None, int] | str:
    """Overall agreement + Cohen's κ as ``(agreement, kappa, n)`` — or a **string naming why they
    do not apply**.

    Requires the two label vocabularies to be the SAME SET. That is the whole guard: with different
    vocabularies (clusters vs cell types) the matrix has no diagonal, and any "accuracy" would be
    reporting an alignment that was never declared — the cell at (Rods, cluster 3) is not a
    'correct' cell.

    It returns the reason rather than a bare ``None`` because the refusal is a **finding** that now
    has to reach a table CELL (spec decided-question 1), not merely a caller's decision to print
    something. The alternative — ``None`` here and a re-test of ``set(row) != set(col)`` at the
    table builder — puts the same condition in two places, free to drift; this keeps one site.
    """
    if not row_labels or set(row_labels) != set(col_labels):
        return "not defined — the two label sets differ, so the matrix has no diagonal"
    n = float(sum(sum(r) for r in counts))
    if n <= 0:
        return "not defined — the matrix holds no observations"
    col_index = {c: j for j, c in enumerate(col_labels)}
    observed = sum(counts[i][col_index[label]] for i, label in enumerate(row_labels))
    po = observed / n
    row_totals = [float(sum(r)) for r in counts]
    col_totals = [float(sum(col)) for col in zip(*counts)]
    pe = sum(row_totals[i] * col_totals[col_index[label]] for i, label in enumerate(row_labels))
    pe /= n * n
    # κ is undefined at perfect chance agreement (pe == 1) — every rating identical. Report the
    # raw agreement and say κ does not exist, rather than dividing by zero.
    kappa = ((po - pe) / (1.0 - pe)) if pe < 1.0 else None
    return po, kappa, int(n)


def confusion_spec(counts, row_labels, col_labels, params: dict,
                   row_title: str, col_title: str, title: str) -> dict:
    """Editable Plotly confusion-matrix spec (shared by stub + real engine).

    ``counts[i][j]`` = rows labelled ``row_labels[i]`` that carry ``col_labels[j]``. Rows run down
    the y axis (true / reference) and columns across x (predicted / compared), the convention every
    confusion matrix is read against.
    """
    row_labels = [str(r) for r in row_labels][:_MAX_LABELS]
    col_labels = [str(c) for c in col_labels][:_MAX_LABELS]
    counts = [[float(v) for v in row[:len(col_labels)]] for row in counts[:len(row_labels)]]

    z, scale_label, is_pct = _normalize(counts, params.get("normalize", "none"))
    annotate = to_bool(params.get("annotate", True))

    heat = {
        "type": "heatmap",
        "z": z,
        "x": col_labels,
        "y": row_labels,
        # Sequential, NOT the diverging expression scale: a count has a floor at zero and no
        # midpoint to diverge around. Declared rather than inferred — `theme._style_matrix` reads
        # this tag, because "has zmin, no zmid" also describes the clustermap's categorical
        # annotation strips, which must keep their stepwise scale.
        "meta": {"selom": {"scale": "sequential"}},
        "zmin": 0,
        "colorscale": "Blues",
        "colorbar": {"title": {"text": scale_label}},
        "hovertemplate": (f"{row_title}: %{{y}}<br>{col_title}: %{{x}}<br>"
                          f"{scale_label}: %{{z}}<extra></extra>"),
        "customdata": counts,
    }
    if is_pct:
        heat["zmax"] = 100
        # The colour now encodes a percentage, so the raw count has to stay reachable somewhere or
        # normalizing would hide the n behind it — a 100% row of ONE observation looks identical to
        # a 100% row of a thousand.
        heat["hovertemplate"] = (f"{row_title}: %{{y}}<br>{col_title}: %{{x}}<br>"
                                 f"{scale_label}: %{{z:.1f}}<br>count: %{{customdata}}<extra></extra>")

    spec = {"data": [heat], "layout": {
        "title": {"text": title},
        # Both axes are forced categorical. Cluster ids arrive as numeric-looking STRINGS on every
        # scRNA path, and an inferred linear axis lays "10" between "1" and "11" — the D2 class
        # `smoke.check_figure` now fails every run.
        "xaxis": {"title": {"text": col_title}, "type": "category", "side": "bottom"},
        "yaxis": {"title": {"text": row_title}, "type": "category", "autorange": "reversed"},
        "plot_bgcolor": "white",
        "showlegend": False,
    }}
    if annotate and len(row_labels) * len(col_labels) <= _MAX_ANNOTATED_CELLS:
        spec["layout"]["annotations"] = _cell_text(z, counts, row_labels, col_labels, is_pct)

    spec["table"] = _confusion_table(counts, row_labels, col_labels, row_title, col_title,
                                     scale_label)
    return jsonable(spec)


def _cell_text(z, counts, row_labels, col_labels, is_pct: bool) -> list:
    """Per-cell value labels, legible on any colour scale.

    Light text on a dark chip rather than a luminance rule, and the reason is a boundary: the SKILL
    does not choose the colour scale — ``theme`` does (§5: no styling in the skill). Deciding the
    text colour from the cell's value therefore requires assuming which end of the ramp is dark, and
    that assumption is wrong half the time: the default style's ``Viridis`` runs dark→light while
    the greyscale style's ``Greys`` runs light→dark. The first cut here keyed off the data maximum
    and rendered dark grey on dark teal — invisible for every low-count cell. A chip is independent
    of the ramp, so it survives a style switch that the skill never sees.
    """
    annotations = []
    for i, _r in enumerate(row_labels):
        for j, _c in enumerate(col_labels):
            value = z[i][j]
            text = f"{value:.1f}%" if is_pct else f"{counts[i][j]:g}"
            annotations.append({
                # Positioned by INDEX, never by category name. On a category axis Plotly coerces a
                # numeric-looking string coordinate to a NUMBER — an annotation at x="7" lands at
                # slot 7 instead of on the category called "7". Cluster ids are numeric strings on
                # every scRNA path, so naming the category scrambled every label and pushed one
                # clean off the plot. Index i is the i-th category by definition, whatever it is
                # called. (The D2 class, in the annotation layer; found by rendering it.)
                "x": j, "y": i, "xref": "x", "yref": "y",
                "text": text, "showarrow": False,
                "font": {"size": 10, "color": "#ffffff"},
                "bgcolor": "rgba(17,24,33,0.55)",
                "borderpad": 2,
            })
    return annotations


def _confusion_table(counts, row_labels, col_labels, row_title, col_title,
                     scale_label: str) -> list[dict]:
    """The matrix + its marginals, and the agreement scalars as a SECOND, one-row table.

    The scalars used to ride in this table's TITLE (``…; n=1576, overall agreement 97.2%, Cohen's
    kappa 0.951``). A number inside a title string is prose, not a result: it does not export to
    CSV, does not diff in compare, and no metric reader can reach it — which is what made this a
    defect rather than a preference (spec D4 rank 3, decided question 1). What stays in the title is
    what genuinely IS prose: what the matrix counts and what its colour encodes.

    ⚑ THE ORDER IS LOAD-BEARING, and not because of the caption. ``extract.readers._read_generic``
    tries the tables **in array order** and ``_read_count`` answers ANY count-shaped metric from ANY
    table that has rows, falling back to ``len(rows)``. A one-row scalar table in position 1 would
    therefore answer ``n_*``/``*_total`` with **1**, at confidence 0.5, on a reproducibility score —
    a wrong number where there used to be a right one. The matrix leads, so every generic read is
    exactly what it was before the split. Leading with the detail costs the reader nothing: D2 keeps
    both panels open, so the scalars are on screen in the same glance either way.
    """
    columns = [f"{row_title} \\ {col_title}", *col_labels, "total"]
    rows = []
    for i, label in enumerate(row_labels):
        rows.append([label, *[int(v) if float(v).is_integer() else v for v in counts[i]],
                     int(sum(counts[i]))])
    col_totals = [sum(col) for col in zip(*counts)] if counts else []
    rows.append(["total", *[int(v) for v in col_totals], int(sum(col_totals))])

    matrix = table(columns, rows,
                   f"Confusion matrix (counts of {row_title} x {col_title}); "
                   f"colour shows {scale_label}")
    return [matrix, _agreement_table(counts, row_labels, col_labels, row_title, col_title)]


def _agreement_table(counts, row_labels, col_labels, row_title, col_title) -> dict:
    """The headline scalars as a one-row table — n, overall agreement, Cohen's κ.

    When the metrics do not apply the table still EXISTS and names the reason in a cell. Silence
    would read as "these labels agree perfectly", and the refusal is the finding on the real-corpus
    path (`clusters` x `celltypes` have no diagonal at all), so it must survive the move out of the
    title at least as prominently as a value would.

    **A column appears only when it holds a number; prose goes in ``note``.** Writing "not defined"
    under a header reading *Cohen's kappa* would be the printed-vs-computed lie that ``de_table``'s
    ``adjusted`` flag and ``lollipop``'s withheld "95% CI" header both exist to avoid — a header
    promising a number it never holds.
    """
    title = f"Agreement between {row_title} and {col_title}"
    n = int(sum(sum(r) for r in counts))
    result = _agreement(counts, row_labels, col_labels)
    if isinstance(result, str):
        return table(["n", "note"], [[n, result]], title)
    po, kappa, _n = result
    if kappa is None:
        return table(["n", "overall agreement (%)", "note"],
                     [[n, round(po * 100, 1),
                       "Cohen's kappa is undefined — chance agreement is total"]], title)
    return table(["n", "overall agreement (%)", "Cohen's kappa"],
                 [[n, round(po * 100, 1), round(kappa, 3)]], title)


def resolve_labels(observed, requested, limit: int = _MAX_LABELS) -> list:
    """Display order for one axis: the names given in ``requested`` that were actually observed,
    then the rest in observed order.

    cnsplots RAISES when the order list is not an exact permutation of the observed labels. Here it
    reorders what it can, matching ``_stats.resolve_order``: a saved figure spec carrying a category
    name that this dataset does not have should reorder the ones it does, not fail the run. Nothing
    is ever filtered out — an unnamed label still appears, so the matrix total always equals the
    input row count (the invariant ``run_real`` asserts).
    """
    observed = [str(o) for o in observed]
    seen, out = set(), []
    for name in parse_list(requested):
        if name in observed and name not in seen:
            seen.add(name)
            out.append(name)
    for name in observed:
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out[:limit]
