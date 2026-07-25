"""Shared Statistics-table builder (Pillar 1 — the Statistics node).

A skill that computes a tabular result attaches it to its returned figure dict as
``spec["table"]`` via :func:`table`. ``contract.run_skill_with_table`` then pops it
out — so the Plotly spec the editor renders stays a pure ``{data, layout}`` — and the
API ships it alongside the figure. Decision D7: additive; purely-visual skills attach
nothing (the FE omits the node, D3).
"""

from __future__ import annotations


def _cell(v):
    """Coerce a cell to a JSON-safe primitive (real engines hand us numpy scalars)."""
    if v is None or isinstance(v, (str, bool, int)):
        return v
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return int(f) if f.is_integer() else f


def table(columns, rows, title: str | None = None) -> dict:
    """A StatsTable: column headers, row tuples (str | number), and an optional title.

    Mirrors the FE `StatsTable` (lib/skills-api.ts). Cells are coerced to JSON-safe
    primitives so numpy scalars from the real engines serialize cleanly.
    """
    out: dict = {"columns": list(columns), "rows": [[_cell(c) for c in r] for r in rows]}
    if title:
        out["title"] = title
    return out


def _sig(x: float, digits: int = 3) -> float:
    """A p-value at N significant figures, as a plain float (JSON-friendly)."""
    try:
        return float(f"{float(x):.{digits}g}")
    except (ValueError, TypeError, OverflowError):
        return x


def de_table(genes, log2fc, padj, fc_t: float = 1.0, fdr_t: float = 0.05,
             max_rows: int = 300, title: str = "Differential expression",
             adjusted: bool = True) -> dict:
    """A differential-expression table (gene · log2FC · padj|pvalue · direction), most
    significant first, capped to ``max_rows`` (the title notes truncation). ``genes``
    is a positionally-indexable sequence aligned with the ``log2fc``/``padj`` arrays.

    ``adjusted`` names the significance column honestly: ``padj`` when the values are corrected for
    multiple testing (the default and the usual case), ``pvalue`` when the source table carried only
    a raw p-value — a column headed ``padj`` holding uncorrected values is a printed-vs-computed lie.
    """
    import numpy as np

    lfc = np.asarray(log2fc, dtype=float)
    p = np.asarray(padj, dtype=float)
    order = np.argsort(np.where(np.isfinite(p), p, np.inf))  # smallest padj first
    rows: list = []
    for i in order:
        li, pi = lfc[i], p[i]
        if not (np.isfinite(li) and np.isfinite(pi)):
            continue
        if li >= fc_t and pi <= fdr_t:
            direction = "up"
        elif li <= -fc_t and pi <= fdr_t:
            direction = "down"
        else:
            direction = "n.s."
        rows.append([str(genes[i]), round(float(li), 4), _sig(pi), direction])
        if len(rows) >= max_rows:
            break
    total = int(np.isfinite(lfc).sum())
    sig_label = "padj" if adjusted else "pvalue"
    if total > len(rows):
        title = f"{title} (top {len(rows)} of {total} by {'adjusted' if adjusted else 'raw'} p)"
    return table(["gene", "log2FC", sig_label, "direction"], rows, title)
