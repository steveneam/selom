"""Engine spine — role→column resolution, with an honest user override (P1 ingest hook).

The single source of truth for "which column plays role R" (R ∈ logFC / pval / gene). It composes
the shared classifier synonym sets (:data:`engine.vocab.DE_LOGFC_SYNONYMS` / ``DE_PVAL_SYNONYMS``) +
a gene-label synonym set, and adds the **user column-override** the AI ``map_columns`` action stages:
a ``{role: column}``
map that **wins over synonym auto-detection** — but only ever points at an *existing* column
(override-only, never fabricate; the honesty rule shared with :mod:`engine.compat`).

Why a shared module rather than per-skill: column-picking is duplicated in each runner's ``_pick``
and the override has to be honoured at every resolution site at once — the D1 schema gate
(:mod:`engine.compat`), the D2 usability gate (:mod:`engine.frame_schema`), and the figure runner —
or a mis-named DE table is blocked before the runner ever reads the override. One resolver, consulted
everywhere. See ``docs/p1-ingest-engine-hooks/spec.md``.
"""

from __future__ import annotations

from typing import Any

from engine.vocab import DE_LOGFC_SYNONYMS as _LOGFC
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
