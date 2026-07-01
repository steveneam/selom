"""Deterministic statistics-advisory cards for the grade stage (Layer A Phase 3).

The grade advisory answers "which statistical test / correction does this figure use, and what does
it assume?" — grounded in the figure's SKILL (and, for ``deg``, its ``mode``), never fabricated. This
is the deterministic fallback for ``POST /ai/explain`` ``request="grade_advice"``: it is fully useful
with the gateway OFF (``source="deterministic"``), and the live gateway may enrich the SAME grounded
facts (``build_explain_prompt`` grade_advice branch).

Advisory only (spine invariant #4: Statistics is advisory-only) — it NEVER mutates a param or switches
a test; it explains the test and suggests when a different one would be more appropriate. Every card
states a fact about the shipped runner (``skills/deg/run_real.py`` etc.), so DETECTED == EXPLAINED.
"""

from __future__ import annotations

# ``deg`` runs genuinely different tests per mode (bulk / pseudobulk / time-course / scRNA), so its
# cards are keyed by mode; other stat skills key by skill id alone.
_DEG_MODE_CARDS: dict[str, dict] = {
    "bulk": {
        "test": "pyDESeq2 negative-binomial GLM with a Wald test on the condition coefficient",
        "correction": "Benjamini-Hochberg FDR (padj)",
        "assumes": [
            "raw integer counts as input (not normalized or logged)",
            ">=2 biological replicates per group (3+ is safer)",
            "samples are independent",
        ],
        "switch": (
            "with many samples or a complex design limma-voom is faster; add a covariate (e.g. batch) "
            "when replicates span batches"
        ),
    },
    "pseudobulk": {
        "test": "pseudobulk (per-sample summed counts) then the same pyDESeq2 Wald test",
        "correction": "Benjamini-Hochberg FDR (padj)",
        "assumes": [
            "cells aggregate to biological replicates by the sample column (not per-cell tests)",
            ">=2 samples per condition",
        ],
        "switch": (
            "a per-cell Wilcoxon over-calls DE (pseudoreplication) — pseudobulk is the correct "
            "condition-level test, so keep it"
        ),
    },
    "timecourse": {
        "test": (
            "pyDESeq2 with time as a continuous covariate, Wald-tested on the time coefficient "
            "(a linear-trend test)"
        ),
        "correction": "Benjamini-Hochberg FDR (padj)",
        "assumes": [
            "a monotone (linear-on-log) trend across >=3 ordered timepoints",
            ">=4 samples spanning the timepoints",
        ],
        "switch": (
            "for a non-linear trajectory an LRT/spline fits better (not available in pyDESeq2 0.5.4); "
            "add a covariate to adjust for a known confounder such as genotype"
        ),
    },
    "scrna": {
        "test": "a Wilcoxon rank-sum test per gene between clusters/groups (scanpy rank_genes_groups)",
        "correction": "Benjamini-Hochberg FDR",
        "assumes": ["it compares cluster markers, treating cells as the unit"],
        "switch": (
            "to compare CONDITIONS across samples use pseudobulk mode — per-cell tests inflate false "
            "positives"
        ),
    },
}

_SKILL_CARDS: dict[str, dict] = {
    "enrichment": {
        "test": "over-representation analysis (a hypergeometric / Fisher's exact test) against annotated gene sets",
        "correction": "Benjamini-Hochberg FDR",
        "assumes": ["a defined gene universe (background) and a threshold-selected gene list"],
        "switch": "use GSEA (ranked, no hard cutoff) when you have a full ranked statistic rather than a cut list",
    },
    "gsea": {
        "test": "GSEA pre-ranked (a Kolmogorov-Smirnov-style enrichment score over the ranked gene list)",
        "correction": "permutation FDR (q-value)",
        "assumes": ["a full ranked statistic for every gene (e.g. a signed -log10 p)"],
        "switch": (
            "over-representation (enrichment) is simpler when you only have a cut gene list; blitzgsea "
            "gives better GO-term recall than the prerank default"
        ),
    },
    "volcano": {
        "test": "no test of its own — it VISUALIZES an existing differential-expression table (log2FC vs -log10 p)",
        "correction": "the thresholds come from your DE table's p / padj columns",
        "assumes": ["the plotted p-values already carry whatever correction the upstream DE run applied"],
        "switch": "for significance, trust the adjusted p (padj/FDR) column over the raw p when choosing the cutoff",
    },
}

# Map the deg runner's mode aliases (run_real.run's dispatch) → our card keys, so DETECTED == EXPLAINED.
_DEG_MODE_ALIASES: dict[str, str] = {
    "pseudobulk": "pseudobulk", "pseudo-bulk": "pseudobulk", "pseudo_bulk": "pseudobulk",
    "timecourse": "timecourse", "time-course": "timecourse", "time_course": "timecourse",
    "scrna": "scrna", "sc": "scrna", "single-cell": "scrna",
    "bulk": "bulk", "auto": "bulk",
}


def grade_card(stats: dict | None) -> str | None:
    """A grounded statistics-advisory paragraph for a figure's skill, or None when the skill is
    unmapped (the caller then gives an honest generic note). ``stats`` = ``{skill_id, mode?}``; a
    ``selom.``-prefixed id is tolerated."""
    if not isinstance(stats, dict):
        return None
    skill_id = str(stats.get("skill_id") or "").split(".")[-1].strip().lower()
    if not skill_id:
        return None
    if skill_id == "deg":
        mode = str(stats.get("mode") or "bulk").strip().lower()
        card = _DEG_MODE_CARDS[_DEG_MODE_ALIASES.get(mode, "bulk")]
    else:
        card = _SKILL_CARDS.get(skill_id)
    if card is None:
        return None
    assumes = "; ".join(card["assumes"])
    return (
        f"Test: {card['test']}. Correction: {card['correction']}. "
        f"Assumes: {assumes}. When to switch: {card['switch']}."
    )
