"""Engine spine — serializable types (P1).

The product-agnostic vocabulary shared by both products (own-data analysis + paper
reproduction). See ``docs/engine-spine/spec.md`` and ``docs/pillars/plan.md``.

Pydantic for the parts that cross the API to the FE (``SourceRef``, ``Design``,
``QCReport``); the live :class:`~engine.databundle.DataBundle` wrapper — which holds an
AnnData/DataFrame *payload* that must not be serialized — is a dataclass in
``databundle.py`` (D-e1: wrap-don't-coerce).
"""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field

# Kind — the closed modality taxonomy (E2: never None; UNKNOWN is honest). ----------------
# String constants (house style, mirroring reproduction's scope + ingest's SUPP_* literals).
SC_COUNTS = "sc_counts"          # AnnData / 10x-mtx single-cell matrix
BULK_COUNTS = "bulk_counts"      # genes x samples integer matrix (+ a design)
DE_RESULTS = "de_results"        # per-gene logFC + p/padj (no raw counts)
PROTEOMICS = "proteomics"        # proteins x samples intensities (MNAR missing)
METABOLOMICS = "metabolomics"    # features x samples intensities (pre-annotation)
GENERIC_TABLE = "generic_table"  # a table we can read but not yet classify
UNKNOWN = "unknown"              # nothing matched (honest, never a crash)

ALL_KINDS = (
    SC_COUNTS, BULK_COUNTS, DE_RESULTS, PROTEOMICS, METABOLOMICS, GENERIC_TABLE, UNKNOWN,
)

# QC severities (E3) ---------------------------------------------------------------------
QC_INFO = "info"    # annotate, no action needed
QC_WARN = "warn"    # annotate; proceed
QC_BLOCK = "block"  # misleading-analysis risk; warn + require explicit override (D-e5)


class SourceRef(BaseModel):
    """Provenance, not bytes (I5): a ``DataBundle`` is reconstructable from its source,
    it is not the file itself."""

    filename: str = ""
    sheet: str = ""
    n_bytes: int = 0
    sha256: str = ""


class Design(BaseModel):
    """Experimental design discovered or attached: the grouping columns analyses key on."""

    condition: str = ""            # the primary contrast column (obs / colData)
    batch: str = ""               # the batch column, if any
    groups: list[str] = Field(default_factory=list)   # observed condition levels
    confounded: bool = False      # batch ~= condition ([[selom-scrna-batch-genotype-confound]])


class QCFlag(BaseModel):
    """One honest data-problem signal — a verdict the user reads, never a silent filter."""

    severity: str = QC_WARN       # info | warn | block
    code: str = ""                # machine code, e.g. "non_integer_counts"
    message: str = ""             # human-readable
    fix: str = ""                 # the fix hint


class QCReport(BaseModel):
    """Is-my-data-clean verdict (E3). Empty (``ran=False``) means QC has not run yet."""

    ran: bool = False
    ok: bool = True
    flags: list[QCFlag] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)

    @computed_field
    @property
    def blocked(self) -> bool:
        """Any ``block``-severity flag present (D-e5: warn + require override, not hard-refuse).
        Serialized (computed_field) so the FE can gate on it directly."""
        return any(f.severity == QC_BLOCK for f in self.flags)
