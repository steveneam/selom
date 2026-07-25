"""Engine spine — the shared column-synonym vocabulary (the single named source of truth).

One place defines *what a fold-change / significance / metabolomics column looks like*. The layered
classifier (:func:`engine.databundle.classify`) and every downstream gate that reads the same header
vocabulary — the role resolver (:mod:`engine.columns`), the D1 data-fit / schema gate
(:mod:`engine.compat`), the D2 usability gate (:mod:`engine.frame_schema`), and the DE-column QC
(:mod:`engine.qc`) — import these tuples rather than re-typing their own copy. A drift-guard test
(``engine/test_vocab_drift_guard.py``) fails if a second copy of these sets forks inside the engine
spine, and flags (does not edit) the known out-of-lane forks in ``skills/*/run_real.py`` that a later
coordinated step (restructure WS3.1) is to converge onto this primitive.

These are *substring* synonym sets: a header matches a role when its lower-cased, stripped form
*contains* any member (so ``avg_log2FC``, ``p_val_adj``, ``adj.P.Val`` all resolve). They are matched
by object identity in a few places (``engine.columns._ROLE_BY_SYNONYMS_ID`` keys on ``id(...)``;
``engine.frame_schema._NUMERIC_SYNONYM_SETS`` holds the tuple objects), so every consumer must import
*these* objects — never an equal copy. Kept as plain module-level tuples (immutable, zero deps) so
importing the vocabulary never pulls the numeric/omics stack.
"""

from __future__ import annotations

# A fold-change column: log2 fold-change under the DESeq2 / edgeR / Seurat header conventions.
DE_LOGFC_SYNONYMS: tuple[str, ...] = (
    "log2foldchange", "logfoldchange", "logfc", "log2fc", "avg_log2fc", "log fold change",
)

# A significance column, ADJUSTED for multiple testing (DESeq2 ``padj``, limma ``adj.P.Val``,
# edgeR ``FDR``, scanpy ``pvals_adj``, Seurat ``p_val_adj``, a ``qvalue``). This tier is tried FIRST
# at selection time — a volcano's y-axis, the ``fdr_threshold`` filter and every "significant genes"
# query set are defined on the adjusted value, so a table carrying both must resolve here.
DE_PADJ_SYNONYMS: tuple[str, ...] = (
    "padj", "p_val_adj", "pvals_adj", "adj.p.val", "adj.pval", "fdr", "qvalue", "q.value",
)

# A RAW, uncorrected p-value column. A legitimate *fallback* when a table carries no adjusted column
# — never a substitute for one, and never silently labelled "adjusted": selection returns which tier
# it came from so the axis title, the table column name, the methods sentence and QC can say so.
DE_PVAL_RAW_SYNONYMS: tuple[str, ...] = ("pvalue", "p_val", "p.value", "pval")

# A significance column of EITHER kind — the PRESENCE union ("does this frame carry a significance
# column at all?"), which is what the D1 schema gate, the D2 usability gate, QC and the compat scorer
# ask. Order here is presence-only and must not be read as selection priority: substring matching
# makes "pval" match "pvals_adj", so an ordered scan of this union picks a raw column over an
# adjusted one. **SELECTION goes through :func:`engine.columns.resolve_significance`** (adjusted tier
# first, with the tier reported back). Enforced by engine/test_vocab_drift_guard.py.
DE_PVAL_SYNONYMS: tuple[str, ...] = DE_PADJ_SYNONYMS + DE_PVAL_RAW_SYNONYMS

# Metabolomics feature labels (m/z values or database tokens) — a conservative, honest signal.
METABOLOMICS_TOKENS: tuple[str, ...] = ("m/z", "hmdb", "metabolite", "kegg c")

__all__ = [
    "DE_LOGFC_SYNONYMS", "DE_PADJ_SYNONYMS", "DE_PVAL_RAW_SYNONYMS", "DE_PVAL_SYNONYMS",
    "METABOLOMICS_TOKENS",
]
