"""L3 — proprietary table synthesis (P2 / the "table joining" moat).

``synthesize_table(skill_id, figure)`` re-shapes a tableless skill's OWN figure output into a
canonical Statistics ``{columns, rows, title, synthesized: True}`` table — **reading, never
recomputing** (S1). A synthesized value is the engine's own number re-shaped, so unlike a
pixel-digitized read it MAY feed the Reproducibility Score (S2), tagged via ``synthesized: True``
(S3). No deterministic synthesizer -> ``None`` -> the L4 Pro-AI tier; never a fabricated table (S4).

The third layer of Selom's extraction stack ([[layered-deterministic-extraction]]): L1 skill-specific
reader · L2 generic reader · **L3 synthesis** · L4 AI. Source shapes: ``docs/reproduction-engine/
skill-table-schemas.md``. Spec + decisions: ``docs/table-synthesis/spec.md`` (Tier A, D-t1..D-t4 owner-signed).
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
}
