"""Engine spine — role→column resolution, with an honest user override (P1 ingest hook).

The single source of truth for "which column plays role R" (R ∈ logFC / pval / gene). It composes
the shared classifier synonym sets (:data:`engine.vocab.DE_LOGFC_SYNONYMS` / ``DE_PVAL_SYNONYMS``) +
a gene-label synonym set, and adds the **user column-override** the AI ``map_columns`` action stages:
a ``{role: column}``
map that **wins over synonym auto-detection** — but only ever points at an *existing* column
(override-only, never fabricate; the honesty rule shared with :mod:`engine.compat`).

Why a shared module rather than per-skill: the override has to be honoured at every resolution site
at once — the D1 schema gate (:mod:`engine.compat`), the D2 usability gate
(:mod:`engine.frame_schema`), and the figure runner — or a mis-named DE table is blocked before the
runner ever reads the override. One resolver, consulted everywhere.
See ``docs/p1-ingest-engine-hooks/spec.md``.

:func:`resolve` is that one resolver and is the entry point runners call. WS3.1 single-sourced the
VOCABULARY but left the MATCHER forked into six byte-identical ``skills/*/run_real.py::_pick``
copies; those are gone (A19) and ``engine/test_vocab_drift_guard.py`` fails on exit code if a new
one appears.
"""

from __future__ import annotations

import re
from typing import Any

from engine.vocab import DE_LOGFC_SYNONYMS as _LOGFC
from engine.vocab import DE_PADJ_SYNONYMS as _PADJ
from engine.vocab import DE_PVAL_RAW_SYNONYMS as _PRAW
from engine.vocab import DE_PVAL_SYNONYMS as _PVAL

# Gene/feature label-column synonyms — the row key a DE / ranked table carries. Canonical here so
# :mod:`engine.compat` (D1) and the six DE runners (``skills/*/run_real.py``) read the SAME set (no
# drift — restructure WS3.1). Substring-matched like the DE vocabulary: a column matches when its
# lower-cased name *contains* a member. Ordered by runner-selection priority — a clean symbol/name
# label (``external_gene_name``, ``gene_symbol``, ``gene_name``) before the generic ``gene`` before
# an id column (a composite ``GeneID`` / ``ensembl_gene_id``), so a mappable symbol wins over an
# unmappable composite id; ``names`` (scanpy ``rank_genes_groups``) is the weakest fallback. The
# order is *selection*-only — every engine consumer reads GENE for column *presence*
# (``compat._GENE_G``, ``classify`` doesn't use it at all), which is order-independent.
GENE = ("symbol", "gene_name", "protein", "gene", "feature", "gene_id", "geneid", "ensembl", "names")

# --- gene-label SELECTION (A10) -------------------------------------------------------------
# PRESENCE ("does a gene-ish column exist", :data:`GENE` above) and SELECTION ("which column IS the
# row label") are different questions and WS3.1 collapsed them onto one substring set. Substring is
# right for presence and wrong for selection: ``GENE`` carries the bare tokens ``gene`` / ``feature``
# / ``names``, so ``gene_biotype`` (a per-gene ANNOTATION), ``n_features`` / ``feature_count`` (a
# COUNT) and ``colnames`` all won the label slot — verified live, a ``gene_biotype,logFC,FDR`` table
# put ``protein_coding`` / ``lncRNA`` on the figure, in the top-N callouts and in the statistics
# table. Selection is therefore TIERED, the same discipline :func:`pick_significance` uses:
#
#   1. EXACT match against :data:`GENE_EXACT` — the concrete headers real exports actually write,
#      in priority order (clean symbol/name → generic ``gene`` → id → scanpy's ``names``).
#   2. SUBSTRING match against :data:`GENE_STRONG` only — tokens specific enough that ANY header
#      containing them is a label (``…gene_symbol``, ``ensembl_gene_id``). The bare tokens are
#      deliberately absent from this tier, which is what makes ``gene_biotype`` resolve to ``None``
#      (→ the runner's honest frame-index fallback) instead of to a biotype string.
#
# Presence keeps reading :data:`GENE` unchanged, so the D1 fit gate (:mod:`engine.compat`) is not
# narrowed by this split.

_CANON_SEP = re.compile(r"[^a-z0-9]+")


def canon(name: Any) -> str:
    """A header's canonical form for EXACT comparison: lower-cased, every run of non-alphanumerics
    collapsed to a single ``_``, and leading/trailing ``_`` stripped.

    So ``"Gene Symbol"``, ``"gene.symbol"`` and ``"GENE-SYMBOL"`` all canonicalise to
    ``gene_symbol`` — one spelling to list — and a UTF-8 BOM left on the first header by an Excel
    export (``"\\ufeffexternal_gene_name"``, live in the ALPK1 exports) stops hiding the column.
    """
    return _CANON_SEP.sub("_", str(name or "").strip().lower()).strip("_")


# Tier 1 — EXACT canonical headers, in selection priority order.
GENE_EXACT: tuple[str, ...] = (
    # 1. clean, mappable symbol/name labels — a symbol beats an unmappable composite id.
    "external_gene_name", "gene_symbol", "genesymbol", "hgnc_symbol", "mgi_symbol", "symbol",
    "gene_name", "genename", "gene_names", "feature_name", "featurename", "gene_label",
    # 2. the proteomics row label (the protein half of the same role).
    "protein", "protein_name", "protein_id", "protein_ids", "protein_group", "protein_groups",
    # 3. the bare tokens — a column literally NAMED "gene"/"feature" is the label.
    "gene", "genes", "feature", "features",
    # 4. id columns last: a composite ``ENSG…~SYMBOL`` or an entrez id maps to nothing on a figure.
    "gene_id", "gene_ids", "geneid", "ensembl_gene_id", "ensembl_id", "ensembl", "ensemblid",
    "entrezgene_id", "entrezgene", "entrez_id", "entrez", "feature_id", "featureid",
    # 5. scanpy ``rank_genes_groups``' weakest fallback.
    "names",
)

# Tier 2 — tokens safe to SUBSTRING-match, same priority order. Every member is specific enough that
# a header containing it is a label; the bare ``gene`` / ``feature`` / ``names`` are excluded on
# purpose (that exclusion IS the A10 fix).
GENE_STRONG: tuple[str, ...] = (
    "external_gene_name", "gene_symbol", "genesymbol", "symbol", "gene_name", "genename",
    "protein", "gene_id", "geneid", "ensembl", "entrezgene",
)

# The roles a user may override, → their synonym group. Disjoint from ``set_design`` (condition/
# batch): two AI actions must not own the same effect. ``logFC``/``pval``/``gene`` are the DE-figure
# column roles the volcano/enrichment/gsea family reads.
ROLE_SYNONYMS: dict[str, tuple[str, ...]] = {"logFC": _LOGFC, "pval": _PVAL, "gene": GENE}
OVERRIDABLE_ROLES = frozenset(ROLE_SYNONYMS)

# Reverse map by object identity — the gates hold a synonym tuple (their ``_SCHEMA`` group) and ask
# "which role is this?". Identity is safe because every site imports the SAME tuple objects.
_ROLE_BY_SYNONYMS_ID: dict[int, str] = {id(syns): role for role, syns in ROLE_SYNONYMS.items()}


def role_of_synonyms(synonyms: tuple[str, ...]) -> str | None:
    """The overridable role a synonym group belongs to, or ``None`` (a non-overridable group)."""
    return _ROLE_BY_SYNONYMS_ID.get(id(synonyms))


# Header markers that make a column adjusted-for-multiple-testing regardless of which tier matched
# it — so a header the adjusted tier has no token for (``p_value_adjusted``, ``pval_corrected``) is
# not mislabelled "raw" after the raw tier catches its ``p_val`` substring.
_ADJUSTED_MARKERS: tuple[str, ...] = ("adj", "fdr", "qval", "q.value", "corrected", "bonferroni")


def is_adjusted_column(name: Any) -> bool:
    """True if a column NAME reads as adjusted-for-multiple-testing (``padj``, ``adj.P.Val``, ``FDR``).

    Used for the user-override path, where the runner is told *which* column to read but not what it
    is: a mapped ``pval`` role is only claimed as adjusted when its own name says so.
    """
    low = str(name or "").strip().lower()
    return bool(low) and (
        any(syn in low for syn in _PADJ) or any(m in low for m in _ADJUSTED_MARKERS)
    )


def normalize(df_columns: Any) -> dict[str, Any]:
    """``{lower-stripped: original}`` in column order — the ONE header normalization.

    Every resolution site used to carry its own ``{str(c).strip().lower(): c}`` copy (six runners +
    the gates); a normalization that drifts silently re-points the resolver at a different column.
    Column order is preserved, so a tie between two synonym-matching columns resolves to the earlier
    one (the tie-break :func:`_first_containing` and :func:`pick_gene` both rely on).
    """
    return {str(c).strip().lower(): c for c in df_columns}


def _first_containing(cols: dict, synonyms: tuple[str, ...]) -> tuple[Any | None, str | None]:
    """First ``(original, lowered)`` column whose lowered name contains a synonym, synonyms in order."""
    for syn in synonyms:
        for low, orig in cols.items():
            if syn in low:
                return orig, low
    return None, None


def pick_gene(cols: dict) -> Any | None:
    """The column that IS the gene/feature row label, or ``None`` — EXACT TIER FIRST.

    ``cols`` is ``{lower-stripped: original}`` in column order (see :func:`normalize`). Tier 1 is an
    exact match against :data:`GENE_EXACT` on the canonical header (:func:`canon`); tier 2 falls back
    to a substring match against :data:`GENE_STRONG` only.

    ``None`` is a real, honest outcome: a table whose only gene-ish header is an annotation or a
    count (``gene_biotype``, ``n_features``, ``feature_count``, ``colnames``) has no label column,
    and the caller must fall back to the frame index rather than label the figure with a biotype.
    """
    by_canon: dict[str, Any] = {}
    for low, orig in cols.items():
        by_canon.setdefault(canon(low), orig)  # first occurrence wins → column order is the tie-break
    for want in GENE_EXACT:
        if want in by_canon:
            return by_canon[want]
    for tok in GENE_STRONG:
        for name, orig in by_canon.items():
            if tok in name:
                return orig
    return None


def pick_significance(cols: dict) -> tuple[Any | None, bool]:
    """``(column, adjusted)`` — the significance column a DE runner must read, ADJUSTED TIER FIRST.

    ``cols`` is ``{lower-stripped: original}`` in column order. The adjusted tier
    (:data:`engine.vocab.DE_PADJ_SYNONYMS`) is exhausted before the raw tier, so a limma table
    carrying both ``P.Value`` and ``adj.P.Val`` resolves to the adjusted column — the value the
    ``fdr_threshold`` filter, the volcano y-axis and every "significant genes" set are defined on.

    Why tiers and not one ordered list: substring matching makes the raw token ``pval`` match the
    ADJUSTED header ``pvals_adj``, so no single ordering of the union is safe. Scanning the union in
    order picked raw p for every non-DESeq2 convention (limma/edgeR/scanpy/Seurat) while the figure
    still said "adjusted" — the regression this function exists to make impossible.

    ``adjusted=False`` is a real, honest outcome (a table with only ``P.Value``): the caller must
    label the axis, the table column and the methods sentence accordingly rather than claim BH.
    """
    col, _low = _first_containing(cols, _PADJ)
    if col is not None:
        return col, True
    col, low = _first_containing(cols, _PRAW)
    if col is None:
        return None, False
    return col, is_adjusted_column(low)


def resolve_significance(override: Any, df_columns: Any, cols: dict) -> tuple[Any | None, bool]:
    """``(column, adjusted)`` for the ``pval`` role — user override first, then adjusted-tier-first
    auto-detection. The one resolution site every DE runner calls, so the tier discipline cannot fork.
    """
    col = override_column(override, "pval", df_columns)
    if col is not None:
        return col, is_adjusted_column(col)
    return pick_significance(cols)


def resolve(role: str, df_columns: Any, override: Any = None, *,
            extra: tuple[str, ...] = (), cols: dict | None = None) -> Any | None:
    """**The** column playing ``role`` (``logFC`` / ``pval`` / ``gene``), or ``None`` (A19).

    Owns the whole composition every DE runner used to re-implement: header normalization
    (:func:`normalize`), the user override (:func:`override_column`, which wins but only ever points
    at an existing column), and the role's own selection order — substring for ``logFC``, the
    adjusted-first tiers for ``pval``, the exact-first tiers for ``gene``. Six byte-identical
    ``_pick`` forks lived in ``skills/*/run_real.py``; a forked matcher is invisible to a guard that
    only scans for forked *vocabulary*, so one runner could silently diverge (exact vs substring, a
    different tie-break, a dropped override) with every test still green.

    ``extra`` appends caller-specific synonyms to a SUBSTRING role (gsea's ranking-statistic tokens);
    it is ignored for ``gene``, whose selection is tiered rather than a flat scan. ``cols`` lets a
    caller that already normalized (because it also calls :func:`resolve_significance`, which takes
    ``cols``) pass it in rather than normalize twice.

    ``pval`` returns only the column; a caller that must label an axis/table/methods sentence needs
    :func:`resolve_significance`, which also returns whether the column is multiple-testing adjusted.
    """
    if role not in ROLE_SYNONYMS:
        raise ValueError(f"unknown column role {role!r} — one of {sorted(ROLE_SYNONYMS)}")
    if cols is None:
        cols = normalize(df_columns)
    if role == "pval":
        return resolve_significance(override, df_columns, cols)[0]
    col = override_column(override, role, df_columns)
    if col is not None:
        return col
    if role == "gene":
        return pick_gene(cols)
    return _first_containing(cols, tuple(ROLE_SYNONYMS[role]) + tuple(extra))[0]


def override_column(override: Any, role: str, df_columns: Any) -> str | None:
    """The user-mapped column for ``role`` — **only when it exists** in ``df_columns``.

    Honest: an override that points at a column the frame doesn't carry resolves to ``None`` (never a
    fabricated column); the caller then falls back to synonym detection (or surfaces a clear error).
    ``override`` may be ``None``/falsy (no override) or a ``{role: column}`` mapping.
    """
    if not override or not isinstance(override, dict):
        return None
    col = override.get(role)
    if not col:
        return None
    try:
        present = col in set(str(c) for c in df_columns)
    except TypeError:
        present = False
    return col if present else None
