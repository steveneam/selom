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

# A significance column: an adjusted or raw p-value / FDR / q-value.
DE_PVAL_SYNONYMS: tuple[str, ...] = (
    "padj", "pvalue", "p_val", "p.value", "pval", "adj.p.val", "fdr", "qvalue",
)

# Metabolomics feature labels (m/z values or database tokens) — a conservative, honest signal.
METABOLOMICS_TOKENS: tuple[str, ...] = ("m/z", "hmdb", "metabolite", "kegg c")

__all__ = ["DE_LOGFC_SYNONYMS", "DE_PVAL_SYNONYMS", "METABOLOMICS_TOKENS"]
