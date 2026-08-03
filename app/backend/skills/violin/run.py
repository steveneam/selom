"""Marker-gene expression violins, one per cluster.

Stub (dependency-free, deterministic) vs. the real scanpy engine. Picks a marker
gene (param ``gene``, else the highest-variance gene) and draws a violin of its
log1p expression for each ``groupby`` level (Leiden cluster by default).
"""

import math

from skills._engine import to_bool, use_real_engine
from skills._stats import (
    attach_brackets,
    count_labels,
    pairs_table,
    parse_pairs,
    resolve_order,
    test_pairs,
)


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy"):
        from skills.violin.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure(params)


# --- PubMed known/novel marker annotation (Kim 2023 Fig 3A/B) -------------------------
# A marker's literature support: query PubMed for the gene (optionally ANDed with a domain
# context) and split known (well-published, hits >= known_min) vs novel (few/no hits — the
# discovery). The network call lives in run_real via litsynth.lookup; these helpers are pure
# so the query-building + figure-annotation are unit-testable without a network.

KNOWN_COLOR = "#3a6ea5"   # muted blue — an established marker
NOVEL_COLOR = "#d1495b"   # accent — the novel/under-characterized marker (the discovery)


def pubmed_query(gene: str, context: str = "") -> str:
    """The PubMed term for a marker gene, optionally scoped to a domain context.

    ``RHO[Title/Abstract]`` or ``RHO[Title/Abstract] AND retina[Title/Abstract]``. A blank
    gene yields a blank term (lookup then short-circuits to 0 without a fetch)."""
    gene = (gene or "").strip()
    if not gene:
        return ""
    term = f"{gene}[Title/Abstract]"
    context = (context or "").strip()
    if context:
        term += f" AND {context}[Title/Abstract]"
    return term


def annotate_pubmed(spec: dict, gene: str, count, *, known_min: int = 5, context: str = "") -> dict:
    """Overlay the known/novel marker split onto a violin spec from a PubMed hit count.

    Adds a corner badge (gene, hit count, known/novel) and tints every violin by the bucket
    colour. ``count is None`` (lookup degraded/offline) leaves the spec untouched — the figure
    renders unannotated rather than breaking (honest-empty-over-fabricate)."""
    if count is None:
        return spec
    known = count >= int(known_min)
    color = KNOWN_COLOR if known else NOVEL_COLOR
    label = "known marker" if known else "novel marker"
    scope = f" in {context.strip()}" if (context or "").strip() else ""
    for tr in spec.get("data", []):
        if tr.get("type") == "violin":
            tr.setdefault("line", {})["color"] = color
            tr["fillcolor"] = color
            tr["opacity"] = 0.65
    spec.setdefault("layout", {}).setdefault("annotations", []).append({
        "xref": "paper", "yref": "paper", "x": 0.98, "y": 0.98,
        "xanchor": "right", "yanchor": "top", "showarrow": False,
        "text": f"<b>{gene}</b> — {count:,} PubMed hits{scope}<br>{label}",
        "align": "right", "font": {"size": 12, "color": color},
        "bgcolor": "rgba(255,255,255,0.75)", "bordercolor": color, "borderwidth": 1,
        "borderpad": 4,
    })
    return spec


def _stub_figure(params: dict | None = None) -> dict:
    """Deterministic violins for four clusters (trig spread, no RNG)."""
    params = params or {}
    means = [0.4, 1.8, 0.9, 2.6]
    groups = {
        f"cluster {gi}": [round(mean + 0.6 * math.sin(gi * 1.7 + j * 0.5), 4) for j in range(24)]
        for gi, mean in enumerate(means)
    }
    return violin_spec(groups, params, "expression (log1p)", "cluster",
                       "Marker expression by cluster (stub)")


def violin_spec(groups: dict, params: dict, value_label: str, group_label: str,
                title: str) -> dict:
    """Editable Plotly violin spec (shared by stub + real engine).

    ``groups`` = {label: [values]}. One ``violin`` trace per group, each with its box and mean
    line, so a group stays independently editable and legend-toggleable.

    Same grouping + annotation vocabulary as ``boxplot`` (``skills._stats``): ``order`` ·
    ``add_count`` · ``pairs`` with ``sig_test`` / ``correction``. Values are passed through
    UNROUNDED — the stub rounds its own, and the real engine hands numpy through ``jsonable``;
    rounding here would silently change real-engine output.
    """
    order = resolve_order(list(groups.keys()), params.get("order"))
    values_of = {k: groups[k] for k in order}
    names = (count_labels(order, values_of) if to_bool(params.get("add_count", False))
             else {k: str(k) for k in order})

    data = [{"type": "violin", "name": names[k], "y": values_of[k],
             "box": {"visible": True}, "meanline": {"visible": True}, "points": False}
            for k in order]
    value_axis = {"title": {"text": value_label}}
    spec = {
        "data": data,
        "layout": {
            "title": {"text": title},
            "xaxis": {"title": {"text": group_label}},
            "yaxis": value_axis,
        },
    }

    sig_test = str(params.get("sig_test", "welch"))
    correction = str(params.get("correction", "none"))
    results = test_pairs(parse_pairs(params.get("pairs")), values_of,
                         test=sig_test, correction=correction)
    if results:
        attach_brackets(spec, results, order, values_of, value_axis)
        tbl = pairs_table(results, test=sig_test, correction=correction)
        if tbl:
            spec["table"] = tbl
    return spec
