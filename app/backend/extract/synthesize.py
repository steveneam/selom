"""L3 — proprietary table synthesis (P2 / the "table joining" moat).

``synthesize_table(skill_id, figure)`` re-shapes a tableless skill's OWN figure output into a
canonical Statistics ``{columns, rows, title, synthesized: True}`` table — **reading, never
recomputing** (S1). A synthesized value is the engine's own number re-shaped, so unlike a
pixel-digitized read it MAY feed the Reproducibility Score (S2), tagged via ``synthesized: True``
(S3). No deterministic synthesizer -> ``None`` -> the L4 Pro-AI tier; never a fabricated table (S4).

The third layer of Selom's extraction stack ([[layered-deterministic-extraction]]): L1 skill-specific
reader · L2 generic reader · **L3 synthesis** · L4 AI. Source shapes: ``docs/reproduction-engine/
skill-table-schemas.md``. Spec + decisions: ``docs/records/table-synthesis/spec.md`` (Tier A 9/9 + the full
Tier-B set; D-t1..D-t4 owner-signed). Tier B = the clean trio (``corr_heatmap``/``sankey``/``upset``)
plus the lossy set (``boxplot``/``heatmap``/``scorecard``/``violin``), each behind a faithfulness gate
(a non-conforming shape -> ``None`` -> L4). ``proteomics_de`` is the one remaining at-source fix
(attach a native ``de_table`` — Codex lane).
"""

from __future__ import annotations

import re
from typing import Any


def synthesize_table(skill_id: str, figure: Any) -> dict | None:
    """A tableless skill's figure -> a canonical synthesized Statistics table, or ``None`` when
    this skill has no deterministic synthesizer (-> L4). Never raises (S4: don't force)."""
    fn = _SYNTHESIZERS.get(skill_id)
    if fn is None or not isinstance(figure, dict):
        return None
    try:
        return fn(figure)
    except Exception:  # a malformed figure must never break the caller — honest None
        return None


# --- shared readers ---------------------------------------------------------------------

def _tbl(columns: list, rows: list, title: str) -> dict:
    return {"columns": columns, "rows": rows, "title": title, "synthesized": True, "source": "figure"}


def _title_text(fig: dict) -> str:
    t = fig.get("layout", {}).get("title", {})
    if isinstance(t, dict):
        return t.get("text", "") or ""
    return str(t or "")


def _subtitle(fig: dict) -> str:
    t = fig.get("layout", {}).get("title", {})
    if isinstance(t, dict):
        sub = t.get("subtitle", {})
        if isinstance(sub, dict):
            return sub.get("text", "") or ""
    return ""


def _title_and_sub(fig: dict) -> str:
    return f"{_title_text(fig)} {_subtitle(fig)}"


def _first_bar(fig: dict) -> dict | None:
    data = fig.get("data", []) or []
    return next((t for t in data if t.get("type") == "bar"), data[0] if data else None)


def _scatter_counts(fig: dict, label_col: str, title: str) -> dict | None:
    """One row per *named* scatter trace -> ``[name, len(x)]``. ``px.scatter(color=…)`` and
    ``scattergl`` emit one trace per categorical level, so the trace length IS that level's member
    count (S1: a real count, read not recomputed). A single continuous-colour trace carries no
    discrete levels (no per-trace ``name``) -> no rows -> ``None`` (-> L4)."""
    rows = []
    for t in fig.get("data", []) or []:
        if t.get("type", "scatter") not in ("scatter", "scattergl"):
            continue
        name, xs = t.get("name"), t.get("x")
        if name and isinstance(xs, (list, tuple)):
            rows.append([str(name), len(xs)])
    return _tbl([label_col, "cells"], rows, title) if rows else None


# --- Tier-A synthesizers ----------------------------------------------------------------

def _pca(fig: dict) -> dict | None:
    layout = fig.get("layout", {})
    rows = []
    for ax in ("xaxis", "yaxis"):
        title = (layout.get(ax, {}) or {}).get("title", {})
        text = title.get("text", "") if isinstance(title, dict) else str(title or "")
        m = re.search(r"\(([\d.]+)\s*%\)", text)
        if m:
            label = text.split(" ")[0] or ax
            rows.append([label, float(m.group(1))])
    return _tbl(["component", "variance %"], rows, "PCA variance explained") if rows else None


def _composition(fig: dict) -> dict | None:
    bars = [t for t in (fig.get("data", []) or []) if t.get("name") and (t.get("y") or t.get("x"))]
    if not bars:
        return None
    cats = list(bars[0].get("x") or [])
    if not cats:
        return None
    conds = [t.get("name", "") for t in bars]
    rows = []
    for i, cat in enumerate(cats):
        row: list = [cat]
        for t in bars:
            ys = t.get("y") or []
            row.append(round(float(ys[i]), 2) if i < len(ys) else None)
        rows.append(row)
    return _tbl(["category", *conds], rows, "Composition (%)")


def _cluster(fig: dict) -> dict | None:
    bar = _first_bar(fig)
    rows = []
    if bar:
        xs = list(bar.get("x") or [])
        ys = [float(y) for y in (bar.get("y") or [])]
        total = sum(ys) or 1.0
        for i, y in enumerate(ys):
            label = xs[i] if i < len(xs) else f"cluster {i}"
            rows.append([label, int(y), round(100.0 * y / total, 1)])
    if not rows:
        return None
    title = "Cluster sizes"
    m = re.search(r"silhouette\s+([\d.]+)", _title_and_sub(fig))
    if m:
        title += f" (silhouette {m.group(1)})"
    return _tbl(["cluster", "cells", "%"], rows, title)


def _pvca(fig: dict) -> dict | None:
    bar = _first_bar(fig)
    if not bar:
        return None
    xs = list(bar.get("x") or [])
    ys = [float(y) for y in (bar.get("y") or [])]
    rows = [[xs[i] if i < len(xs) else f"factor {i}", round(y * 100.0, 2)] for i, y in enumerate(ys)]
    return _tbl(["factor", "variance %"], rows, "Variance partition (PVCA)") if rows else None


def _regression(fig: dict) -> dict | None:
    anns = fig.get("layout", {}).get("annotations", []) or []
    text = anns[0].get("text", "") if anns else ""
    rows = []
    for label, pat in (("R²", r"R²\s*=\s*([-\d.eE+]+)"),
                       ("slope", r"slope\s*=\s*([-\d.eE+]+)"),
                       ("p", r"\bp\s*=\s*([-\d.eE+]+)")):
        m = re.search(pat, text)
        if m:
            rows.append([label, m.group(1)])
    return _tbl(["statistic", "value"], rows, "Regression fit") if rows else None


def _integration(fig: dict) -> dict | None:
    m = re.search(r"batch mixing\s+([\d.]+)\s*(?:→|->)\s*([\d.]+)", _title_and_sub(fig))
    if not m:
        return None
    return _tbl(["metric", "before", "after"],
                [["batch mixing (kNN entropy)", float(m.group(1)), float(m.group(2))]],
                "Batch integration")


def _umap_scrna(fig: dict) -> dict | None:
    # ``px.scatter(color=color_by)`` -> one named scatter trace per cluster level; the real
    # n_clusters is ``len(fig.data)`` (schema doc), per-cluster cells = the trace length.
    return _scatter_counts(fig, "cluster", "Cluster sizes (UMAP)")


def _annotate(fig: dict) -> dict | None:
    # ``_umap_by_type_spec`` -> one scattergl trace per assigned cell type; cells = trace length.
    # Per-type *cluster* counts are NOT in the figure (the cluster->type map is aggregated away) ->
    # don't fabricate them (S4); fold the subtitle's totals into the title instead.
    tbl = _scatter_counts(fig, "cell type", "Cell-type composition")
    if tbl is None:
        return None
    m = re.search(r"(\d+)\s+types?\s+assigned across\s+(\d+)\s+clusters", _subtitle(fig))
    if m:
        tbl["title"] += f" ({m.group(1)} types across {m.group(2)} clusters)"
    return tbl


def _trajectory(fig: dict) -> dict | None:
    sub = _title_and_sub(fig)
    rows = []
    for label, pat in (("clusters", r"(\d+)\s+clusters"),
                       ("edges", r"(\d+)\s+edges"),
                       ("lineages", r"(\d+)\s+lineage")):
        m = re.search(pat, sub)
        if m:
            rows.append([label, int(m.group(1))])
    return _tbl(["metric", "value"], rows, "Trajectory structure") if rows else None


# --- Tier-B synthesizers (each behind a faithfulness gate -> None on a non-conforming shape) ---

# UpSet's "present" membership dots carry this colour (``skills/upset/run.py`` ``_DOT_ON``); it is the
# figure's own present/absent channel, so reading it back is faithful (S1). Absent dots use a paler
# token, connectors are lines -> filtered out by the mode/colour checks.
_UPSET_DOT_ON = "#33404d"


def _is_square_symmetric(z: list, tol: float = 1e-9) -> bool:
    """True when ``z`` is a square matrix equal to its transpose within ``tol`` — the shape that lets
    a correlation table drop the redundant lower triangle + unit diagonal without losing a value."""
    n = len(z)
    for i in range(n):
        if not isinstance(z[i], (list, tuple)) or len(z[i]) != n:
            return False
        for j in range(i + 1, n):
            a, b = z[i][j], z[j][i]
            if a is None or b is None or abs(float(a) - float(b)) > tol:
                return False
    return True


def _heatmap_grid(fig: dict) -> tuple[list, list, list] | None:
    """The first ``heatmap`` trace's ``(z, x, y)`` when ``z`` is a rectangular numeric grid matching
    both label axes (clustering reorders, so the emitted label order IS the truth) — else ``None``.
    Shared gate for the correlation (long-form), expression (wide-form), and scorecard synthesizers;
    any extra trace (a dendrogram ``scatter``) is ignored — we read the ``heatmap`` trace."""
    tr = next((t for t in (fig.get("data", []) or []) if t.get("type") == "heatmap"), None)
    if not tr:
        return None
    z = tr.get("z")
    xs, ys = list(tr.get("x") or []), list(tr.get("y") or [])
    if not isinstance(z, list) or not z or not xs or not ys or len(z) != len(ys):
        return None
    if any(not isinstance(r, (list, tuple)) or len(r) != len(xs) for r in z):
        return None
    return z, xs, ys


def _corr_heatmap(fig: dict) -> dict | None:
    # Read the heatmap ``z`` matrix against its emitted ``x``/``y`` labels. Gate: rectangular numeric
    # ``z`` matching both label axes.
    grid = _heatmap_grid(fig)
    if grid is None:
        return None
    z, xs, ys = grid
    # symmetric corr matrix -> upper triangle only (drop the mirrored half + the r=1 diagonal); a
    # non-symmetric / non-square grid -> every cell (still faithful, just denser).
    upper_only = xs == ys and _is_square_symmetric(z)
    rows = []
    for i, rlab in enumerate(ys):
        for j, clab in enumerate(xs):
            if upper_only and j <= i:
                continue
            val = z[i][j]
            if val is None:
                continue
            rows.append([str(rlab), str(clab), round(float(val), 4)])
    return _tbl(["row", "col", "r"], rows, "Correlation matrix") if rows else None


def _sankey(fig: dict) -> dict | None:
    # Resolve each integer link index back to its node label. Gate: aligned source/target/value link
    # arrays + every index in range (an out-of-range index can't be faithfully resolved -> None).
    tr = next((t for t in (fig.get("data", []) or []) if t.get("type") == "sankey"), None)
    if not tr:
        return None
    labels = list((tr.get("node", {}) or {}).get("label") or [])
    link = tr.get("link", {}) or {}
    src, tgt, val = list(link.get("source") or []), list(link.get("target") or []), list(link.get("value") or [])
    if not labels or not src or not (len(src) == len(tgt) == len(val)):
        return None
    rows = []
    for s, t, v in zip(src, tgt, val):
        si, ti = int(s), int(t)
        if not (0 <= si < len(labels) and 0 <= ti < len(labels)):
            return None
        rows.append([labels[si], labels[ti], round(float(v), 4)])
    return _tbl(["source", "target", "value"], rows, "Sankey flows")


def _upset(fig: dict) -> dict | None:
    # Intersection sizes are the reproducible numbers (Venn/UpSet counts) — read from the vertical
    # size-bar trace. Member sets enrich the label, recovered from the "present" dots (S1). Gate: the
    # size bars must be present with aligned x ids / numeric y; members are best-effort.
    data = fig.get("data", []) or []
    bars = next((t for t in data if t.get("type") == "bar" and t.get("orientation") != "h"), None)
    if not bars:
        return None
    ids = list(bars.get("x") or [])
    sizes = list(bars.get("y") or [])
    if not ids or len(sizes) != len(ids):
        return None
    members: dict = {}
    for t in data:
        if t.get("type") not in ("scatter", "scattergl") or "markers" not in (t.get("mode") or ""):
            continue
        if (t.get("marker", {}) or {}).get("color") != _UPSET_DOT_ON:
            continue
        for cid, s in zip(t.get("x") or [], t.get("y") or []):
            members.setdefault(cid, []).append(str(s))
    rows = []
    for cid, size in zip(ids, sizes):
        mem = members.get(cid)
        label = " ∩ ".join(mem) if mem else str(cid)
        rows.append([label, len(mem) if mem else None, int(size)])
    return _tbl(["intersection", "sets", "size"], rows, "Set intersections")


# --- Tier-B synthesizers (lossy set — gated; a non-conforming shape -> None -> L4) -------

def _percentile(sv: list[float], q: float) -> float:
    """The ``q``-th percentile (0–100) of a *sorted* non-empty list by linear interpolation between
    closest ranks — numpy's default method and Plotly's default box ``quartilemethod`` ("linear"), so
    the synthesized quartiles reproduce the box Plotly actually draws."""
    if len(sv) == 1:
        return float(sv[0])
    rank = (q / 100.0) * (len(sv) - 1)
    lo = int(rank)  # floor (rank is non-negative)
    frac = rank - lo
    return float(sv[lo]) if frac == 0 else float(sv[lo]) * (1 - frac) + float(sv[lo + 1]) * frac


def _close(a: Any, b: Any, tol: float = 1e-9) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def _numeric_array(seq: Any) -> list[float] | None:
    """``seq`` as a list of floats when it is a non-empty all-numeric sequence (bools excluded) —
    else ``None``. Lets a synthesizer pick the numeric axis of a trace without guessing."""
    if not isinstance(seq, (list, tuple)) or not seq:
        return None
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) for v in seq):
        return None
    return [float(v) for v in seq]


def _boxplot(fig: dict) -> dict | None:
    # Each group is one ``box`` trace carrying its RAW values (Plotly draws the quartiles client-side);
    # synthesize the five-number summary the box itself encodes — n/min/median/max are exact order
    # statistics, q1/q3 use Plotly's default "linear" quartile method, so the table == the drawn box.
    # The raw values sit on ``y`` (vertical) or ``x`` (horizontal). Gate: >=1 box trace with a numeric
    # value array.
    rows = []
    for t in fig.get("data", []) or []:
        if t.get("type") != "box":
            continue
        vals = _numeric_array(t.get("y")) or _numeric_array(t.get("x"))
        if vals is None:
            continue
        sv = sorted(vals)
        rows.append([str(t.get("name", f"group {len(rows)}")), len(sv),
                     round(sv[0], 4), round(_percentile(sv, 25), 4), round(_percentile(sv, 50), 4),
                     round(_percentile(sv, 75), 4), round(sv[-1], 4)])
    return _tbl(["group", "n", "min", "q1", "median", "q3", "max"], rows,
                "Distribution summary") if rows else None


def _heatmap(fig: dict) -> dict | None:
    # Expression z-score grid: rows = genes (``y``), columns = groups (``x``), values = ``z`` (the
    # z-scores the figure draws — faithful; absolute expression isn't recoverable, S4 honest). Wide
    # form, one row per gene. Gate: rectangular numeric ``z`` matching both axes (``_heatmap_grid``).
    grid = _heatmap_grid(fig)
    if grid is None:
        return None
    z, xs, ys = grid
    rows = []
    for i, gene in enumerate(ys):
        row: list = [str(gene)]
        for j in range(len(xs)):
            v = z[i][j]
            row.append(round(float(v), 4) if isinstance(v, (int, float)) and not isinstance(v, bool) else None)
        rows.append(row)
    return _tbl(["gene", *[str(x) for x in xs]], rows, "Expression (row z-score)")


def _scorecard(fig: dict) -> dict | None:
    # Long-form ``[condition, metric, score]`` from either layout of the same benchmark: the radar
    # (one ``scatterpolar`` per condition — ``theta`` = metrics, ``r`` = scores, polygon closed by a
    # repeated first point, dropped) or the heatmap (``x`` = conditions, ``y`` = metrics, ``z`` =
    # scores). Scores are the normalized values the figure draws (raw not recoverable — faithful to the
    # panel, S2). Gate: aligned theta/r per polar trace, or a rectangular heatmap ``z``.
    polar = [t for t in (fig.get("data", []) or []) if t.get("type") == "scatterpolar"]
    if polar:
        rows = []
        for t in polar:
            cond = str(t.get("name", ""))
            theta, r = list(t.get("theta") or []), list(t.get("r") or [])
            if not theta or len(theta) != len(r):
                return None
            if len(theta) >= 2 and theta[0] == theta[-1] and _close(r[0], r[-1]):
                theta, r = theta[:-1], r[:-1]  # drop the repeated closing point
            rows.extend([cond, str(metric), round(float(score), 4)] for metric, score in zip(theta, r))
        return _tbl(["condition", "metric", "score"], rows, "Benchmark scorecard") if rows else None
    grid = _heatmap_grid(fig)
    if grid is None:
        return None
    z, conds, metrics = grid
    rows = [[str(cond), str(metric), round(float(z[i][j]), 4)]
            for i, metric in enumerate(metrics) for j, cond in enumerate(conds)]
    return _tbl(["condition", "metric", "score"], rows, "Benchmark scorecard")


# violin's one faithful single-statistic is the PubMed known/novel marker call (``annotate=pubmed``),
# formatted into a corner annotation by ``violin.annotate_pubmed`` as
# ``<b>{gene}</b> — {n:,} PubMed hits[ in {context}]<br>{known|novel} marker``.
_VIOLIN_PUBMED_RE = re.compile(
    r"<b>(?P<gene>[^<]+)</b>\s*[-—]\s*(?P<hits>[\d,]+)\s+PubMed hits.*?(?P<verdict>known|novel)\s+marker",
    re.I | re.S,
)


def _violin(fig: dict) -> dict | None:
    # Read the literature-support call back from the annotation. No annotation (the common,
    # un-annotated case — raw per-cluster distributions only) -> None (-> L4); the distributions are
    # not tabulated here (S4: don't force).
    for ann in reversed(fig.get("layout", {}).get("annotations", []) or []):
        text = ann.get("text", "") if isinstance(ann, dict) else ""
        m = _VIOLIN_PUBMED_RE.search(text or "")
        if m:
            hits = int(m.group("hits").replace(",", ""))
            return _tbl(["gene", "pubmed hits", "verdict"],
                        [[m.group("gene").strip(), hits, f"{m.group('verdict').lower()} marker"]],
                        "Marker literature support")
    return None


_SYNTHESIZERS = {
    "pca": _pca,
    "composition": _composition,
    "cluster": _cluster,
    "umap_scrna": _umap_scrna,
    "annotate": _annotate,
    "pvca": _pvca,
    "regression": _regression,
    "integration": _integration,
    "trajectory": _trajectory,
    # Tier B (clean trio):
    "corr_heatmap": _corr_heatmap,
    "sankey": _sankey,
    "upset": _upset,
    # Tier B (lossy set — each gated):
    "boxplot": _boxplot,
    "heatmap": _heatmap,
    "scorecard": _scorecard,
    "violin": _violin,
}
