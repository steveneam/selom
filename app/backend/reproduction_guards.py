"""Reproduction Engine — the 14 edge-case guards as a first-class registry (build-plan R1).

These are the traps that make a repro *look* done when it isn't, or make Selom *look*
wrong when the paper is the problem (``docs/reproduction-engine/figure-repro-sop.md``
§Edge cases; spec §Guards). D11: **a panel verdict is invalid until its applicable guards
have run** — :func:`run_guards` returns every guard that fired, and the ids feed
``Validation.guards_fired``.

Each guard declares the loop stage it runs in and what it produces (a blame, an
inconsistency, or a note). A guard returns ``None`` when its inputs aren't in the context
(not applicable) — so the same registry runs over a bulk-DE panel and a scRNA panel and
only the relevant guards fire. The data-logic helpers (filter ceiling, batch purity,
species prefixes, cell-type set delta) are pure and individually testable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from reproduction import (
    DEPOSITED_RAW,
    PAPER_IRREPRODUCIBLE,
    STRUCTURAL_LIMIT,
    WET_LAB,
)


class GuardFinding(BaseModel):
    guard_id: str
    num: int
    stage: str
    fired: bool
    produces: str = ""  # a blame constant, "inconsistency", or "note"
    detail: str = ""
    data: dict = Field(default_factory=dict)


# --- pure data-logic helpers (independently testable) -------------------------


def filter_ceiling_unreachable(n_pass: int, golden: int) -> bool:
    """Guard 4: a count-golden is structurally unreachable if fewer target genes survive
    the expression filter than the printed number (RPGRIP1 Fig 5: 882/1,133 pass CPM<2)."""
    return n_pass < golden


def batch_purity(cluster_labels, batch_labels) -> dict[str, float]:
    """Guards 10/11: per cluster, the share of cells from its single most-represented
    batch. A share near 1.0 means the cluster *is* a batch (RPGRIP1 6D: Rod-2 = 99.2%
    MS-VUS) — an abundance claim over it is a batch artifact until integration is shown."""
    from collections import Counter, defaultdict

    per: dict = defaultdict(Counter)
    for cl, ba in zip(cluster_labels, batch_labels):
        per[cl][ba] += 1
    out: dict[str, float] = {}
    for cl, counts in per.items():
        total = sum(counts.values())
        out[str(cl)] = (max(counts.values()) / total) if total else 0.0
    return out


def species_prefixes(gene_names, sep_candidates=("_", "___")) -> set[str]:
    """Guard 13: distinct genome prefixes in a 10x feature list. >1 means a combined-genome
    deposit (RPGRIP1 scRNA = GRCh38_ + mm10___) → filter to the analysis species before QC."""
    prefixes: set[str] = set()
    for name in gene_names:
        s = str(name)
        for sep in sep_candidates:
            if sep in s:
                prefixes.add(s.split(sep, 1)[0])
                break
    return prefixes


def celltype_set_delta(expected, recovered) -> dict[str, list[str]]:
    """Guard 14: the cell-type *set* difference between the paper and a marker-score
    annotation (the set is the target, the method differs). RPGRIP1 6A: {RGC missing} /
    {tiny RPE spurious}."""
    e, r = set(expected), set(recovered)
    return {"missing": sorted(e - r), "spurious": sorted(r - e)}


# --- the guards ---------------------------------------------------------------

_REGISTRY: list = []


def _guard(num: int, guard_id: str, stage: str):
    def register(fn):
        fn._num, fn._id, fn._stage = num, guard_id, stage
        _REGISTRY.append(fn)
        return fn

    return register


def _fired(fn, produces: str, detail: str, data: dict | None = None) -> GuardFinding:
    return GuardFinding(
        guard_id=fn._id, num=fn._num, stage=fn._stage,
        fired=True, produces=produces, detail=detail, data=data or {},
    )


def _has_inconsistency(ctx, kind) -> bool:
    return any(getattr(i, "kind", None) == kind for i in ctx.get("inconsistencies", []))


@_guard(1, "methods_vs_numbers", "sweep")
def g1(ctx):
    if _has_inconsistency(ctx, "methods_vs_numbers"):
        return _fired(g1, "inconsistency", "printed count not reproducible at the stated threshold")
    return None


@_guard(2, "figures_vs_methods", "extract")
def g2(ctx):
    if _has_inconsistency(ctx, "figures_vs_methods"):
        return _fired(g2, "inconsistency", "figure and methods print different values for the same target")
    return None


@_guard(3, "authors_tool_misses", "oracle")
def g3(ctx):
    oracle = ctx.get("oracle")
    if oracle is not None and oracle.ran_on == DEPOSITED_RAW and not oracle.agrees_with_paper:
        return _fired(g3, PAPER_IRREPRODUCIBLE, "authors' own tool misses the golden on the deposited data")
    return None


@_guard(4, "filter_ceiling", "prepare")
def g4(ctx):
    f = ctx.get("filter")
    if f and "n_pass" in f and "golden" in f:
        if filter_ceiling_unreachable(f["n_pass"], f["golden"]):
            return _fired(
                g4, STRUCTURAL_LIMIT,
                f"only {f['n_pass']} genes pass the filter < golden {f['golden']}",
                {"n_pass": f["n_pass"], "golden": f["golden"]},
            )
    return None


@_guard(5, "mild_contrast_zero_terms", "validate")
def g5(ctx):
    counts = ctx.get("contrast_term_counts")
    if counts and len(counts) > 1:
        vals = list(counts.values())
        if min(vals) == 0 and max(vals) > 0:
            return _fired(g5, "note", "a milder contrast clears 0 terms while another clears >0 — report the asymmetry", {"counts": counts})
    return None


@_guard(6, "deposit_vs_figure", "ingest")
def g6(ctx):
    d = ctx.get("deposit")
    if d and "n_samples_deposited" in d and "n_samples_figure" in d:
        if d["n_samples_deposited"] < d["n_samples_figure"]:
            return _fired(
                g6, STRUCTURAL_LIMIT,
                f"deposit has {d['n_samples_deposited']} samples < the figure's {d['n_samples_figure']}",
                d,
            )
    return None


@_guard(7, "wet_lab_out_of_scope", "extract")
def g7(ctx):
    panel = ctx.get("panel")
    if panel is not None and getattr(panel, "scope", None) == WET_LAB:
        return _fired(g7, "out-of-scope", "wet-lab panel — excluded from the scorecard denominator")
    return None


@_guard(8, "measure_dont_assume", "oracle")
def g8(ctx):
    panel = ctx.get("panel")
    if panel is not None:
        unmeasured = [m for m in getattr(panel, "method_subs", []) if m.delta_measured is None]
        if unmeasured:
            return _fired(
                g8, "note",
                f"{len(unmeasured)} method substitution(s) applied without a measured delta",
                {"tools": [m.selom_tool for m in unmeasured]},
            )
    return None


@_guard(9, "tooling", "env")
def g9(ctx):
    env = ctx.get("env")
    if env is not None and (env.get("pythonioencoding") or "").lower() != "utf-8":
        return _fired(g9, "note", "PYTHONIOENCODING is not utf-8 — Windows console will choke on ∩/−")
    return None


@_guard(10, "batch_genotype_confound", "prepare")
def g10(ctx):
    purity = ctx.get("batch_purity")
    threshold = ctx.get("batch_purity_threshold", 0.9)
    if purity:
        impure = {k: v for k, v in purity.items() if v >= threshold}
        if impure:
            return _fired(
                g10, STRUCTURAL_LIMIT,
                "a cluster is ~one batch — abundance claim is a batch artifact until integration is shown",
                {"clusters": impure, "threshold": threshold},
            )
    return None


@_guard(11, "subclustering_batch_confounded", "prepare")
def g11(ctx):
    if ctx.get("integrated") is False and ctx.get("subclustering"):
        return _fired(g11, "note", "naïve subclustering on merged samples is batch-confounded — integrate (Harmony) before believing subtypes")
    return None


@_guard(12, "gsea_engine_sensitivity", "oracle")
def g12(ctx):
    panel = ctx.get("panel")
    if panel is not None and getattr(panel, "skill_id", None) == "gsea":
        metrics = " ".join(g.metric for g in getattr(panel, "golden", []))
        if any(t in metrics.lower() for t in ("count", "venn", "n_term", "term")):
            return _fired(g12, "note", "GSEA term-count target — run fgsea on the same ranking to split engine-delta from upstream-delta (RISKS #10)")
    return None


@_guard(13, "combined_genome_deposit", "prepare")
def g13(ctx):
    genes = ctx.get("gene_names")
    if genes:
        prefixes = species_prefixes(genes)
        if len(prefixes) > 1:
            return _fired(g13, "note", "combined-genome deposit — filter to the analysis species before gene-count QC", {"prefixes": sorted(prefixes)})
    return None


@_guard(14, "annotation_set_delta", "validate")
def g14(ctx):
    ct = ctx.get("celltypes")
    if ct and "expected" in ct and "recovered" in ct:
        delta = celltype_set_delta(ct["expected"], ct["recovered"])
        if delta["missing"] or delta["spurious"]:
            return _fired(g14, "note", "annotation-substitution cell-type set delta (the set is the target, the method differs)", delta)
    return None


def run_guards(ctx: dict) -> list[GuardFinding]:
    """Run every applicable guard over the context; return the ones that fired.

    ``ctx`` is a loose bag of optional signals (panel, inconsistencies, filter,
    batch_purity, gene_names, celltypes, oracle, env, …). Each guard ignores a context
    that lacks its inputs, so this is safe to call at any loop stage with whatever is known.
    """
    return [f for f in (guard(ctx) for guard in _REGISTRY) if f is not None]


def registry() -> list[dict]:
    """The full catalog of 14 guards (id, num, stage) — complete even when none fire."""
    return [{"num": g._num, "id": g._id, "stage": g._stage} for g in sorted(_REGISTRY, key=lambda g: g._num)]
