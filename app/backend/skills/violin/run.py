"""Marker-gene expression violins, one per cluster.

Stub (dependency-free, deterministic) vs. the real scanpy engine. Picks a marker
gene (param ``gene``, else the highest-variance gene) and draws a violin of its
log1p expression for each ``groupby`` level (Leiden cluster by default).
"""

import math

from skills._engine import use_real_engine


def run(data_path: str, params: dict) -> dict:
    if use_real_engine("scanpy"):
        from skills.violin.run_real import run as run_real

        return run_real(data_path=data_path, params=params)
    return _stub_figure()


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


def _stub_figure() -> dict:
    """Deterministic violins for four clusters (trig spread, no RNG)."""
    means = [0.4, 1.8, 0.9, 2.6]
    traces = []
    for gi, mean in enumerate(means):
        ys = [round(mean + 0.6 * math.sin(gi * 1.7 + j * 0.5), 4) for j in range(24)]
        traces.append(
            {
                "type": "violin",
                "name": f"cluster {gi}",
                "y": ys,
                "box": {"visible": True},
                "meanline": {"visible": True},
                "points": False,
            }
        )
    return {
        "data": traces,
        "layout": {
            "title": {"text": "Marker expression by cluster (stub)"},
            "xaxis": {"title": {"text": "cluster"}},
            "yaxis": {"title": {"text": "expression (log1p)"}},
        },
    }
