"""Engine spine — data-fit scoring (the "is this dropped data good?" filter, P2/P3).

Answers the owner's question — *is this file the right, clean data for this analysis?* — with one
rankable **fit score (0-100)** per (file, skill). It is not new science: it **composes the two
filters the engine already has** — :func:`engine.databundle.classify` (what modality is the file)
and :func:`engine.qc.run_qc` (is the file clean) — against what a panel's skill actually needs.

Used three ways, one source of truth:

* **before a run** — a pre-run assessment so the user sees a wrong/dirty file as visibly poor and
  can drop a different one (``main.py`` exposes it; ``DataFit`` is the wire shape);
* **inside the matcher** — :func:`engine.match.match_data` calls :func:`best_match` to stop
  force-feeding an incompatible supplement onto a skill (Slice 2 *matcher honesty*); and
* **after a run** — the gap report + run contract carry the same fits.

**The honesty rule (load-bearing).** A fit only *gates* (blocks a run → ``data_unmatched``) on a
**positively-determined** incompatibility: the file loads AND its payload *class* conflicts with the
skill (a flat table can never be a single-cell matrix — ``sc_counts`` needs AnnData/10x; a matrix can
never be the per-gene DE table a volcano reads). An unloadable or modality-unclear file stays
*optimistic* (scored low, but never gated on a guess) — so a hard file is honest, never a false
block, and every fake-path drive test is unaffected. Mirrors the reproduction "no silent caps" /
"never a Selom defect for a data gap" invariant. See ``docs/records/reproduction-dogfood/spec.md`` Slice 2.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, computed_field

from engine.models import (
    BULK_COUNTS,
    DE_RESULTS,
    GENERIC_TABLE,
    METABOLOMICS,
    PROTEOMICS,
    QC_BLOCK,
    QC_WARN,
    SC_COUNTS,
    UNKNOWN,
    QCFlag,
    QCReport,
)

# --- what each skill's modality needs -------------------------------------------------------
# Only skills where the modality genuinely gates are listed; a skill absent here has *no*
# requirement, so it is never gated (optimistic — the honesty rule). Kinds are the closed
# ``engine.models`` taxonomy. The single-cell skills need a *matrix* payload (AnnData/10x) that
# a flat tabular supplement can never be — that is the certain gate the dogfood meta-finding hits.
_SC_MATRIX = frozenset({SC_COUNTS})
_TABLE_OR_DE = frozenset({DE_RESULTS, BULK_COUNTS, PROTEOMICS})
_REQS: dict[str, frozenset[str]] = {
    # single-cell matrix skills — a flat table is a certain mismatch
    "umap_scrna": _SC_MATRIX,
    "normalization_qc": _SC_MATRIX,
    "markers": _SC_MATRIX,
    "composition": _SC_MATRIX,
    "trajectory": _SC_MATRIX,
    "pseudotime_genes": _SC_MATRIX,
    "diff_abundance": _SC_MATRIX,
    "cluster": _SC_MATRIX,
    "annotate": _SC_MATRIX,
    "integration": _SC_MATRIX,
    "violin": _SC_MATRIX,
    # count-matrix / DE-table consumers — accept the table modalities they can be drawn from
    "deg": frozenset({BULK_COUNTS, SC_COUNTS}),
    "proteomics_de": frozenset({PROTEOMICS, BULK_COUNTS}),
    "volcano": _TABLE_OR_DE,
    "enrichment": _TABLE_OR_DE,
    "gsea": _TABLE_OR_DE,
    "ssgsea": _TABLE_OR_DE,
}

# The two payload *classes*. ``sc_counts`` is the only matrix kind (an AnnData payload); every other
# kind is a flat table (a DataFrame). The class gate is *certain* — a DataFrame is never an AnnData,
# so it is never sc_counts — whereas a within-class sub-kind miss (e.g. a real DE table that the
# classifier failed to recognize) is uncertain, so it stays optimistic.
_MATRIX_KINDS = frozenset({SC_COUNTS})


def _kind_class(kind: str) -> str:
    return "matrix" if kind in _MATRIX_KINDS else "table"


# --- per-file assessment (skill-agnostic: "is this good data?") -----------------------------


class FileAssessment(BaseModel):
    """One dropped file inspected on its own — *what is it, and is it clean* — independent of any
    skill. ``quality`` (0-100) is the data-cleanliness half of the fit score (from QC alone).
    ``columns``/``n_numeric_cols`` capture the table *shape* so the per-skill schema layer can check
    the actual columns (not just the coarse modality) — the layered check the owner asked for."""

    path: str
    filename: str = ""
    loadable: bool = False
    kind: str = UNKNOWN
    quality: int = 0
    qc_ok: bool = True
    qc_flags: list[QCFlag] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)   # original column names (tables only)
    n_numeric_cols: int = 0
    note: str = ""


def _quality_from_qc(qc: QCReport) -> int:
    """0-100 cleanliness from the QC flags: a ``block`` problem is serious (−45), a ``warn`` is a
    caveat (−12 each, capped), ``info`` is free. A clean report is 100."""
    score = 100
    if any(f.severity == QC_BLOCK for f in qc.flags):
        score -= 45
    score -= min(36, 12 * sum(1 for f in qc.flags if f.severity == QC_WARN))
    return max(0, score)


def assess_bundle(bundle: Any) -> FileAssessment:
    """Build a :class:`FileAssessment` from an ALREADY-ingested ``DataBundle`` — reuses its classify
    + QC, no second disk read. The Product-A own-data path (``/data/inspect``, ``/skills/{id}/run``)
    already ingests, so this surfaces the same data-fit score there as reproduction gets, free. This
    is why ``compat`` lives in the product-agnostic ``engine`` package: one "is this good data?" check,
    both products."""
    from engine.qc import run_qc

    qc = bundle.qc if getattr(getattr(bundle, "qc", None), "ran", False) else run_qc(bundle)
    columns, n_numeric = _frame_signature(bundle.payload)
    return FileAssessment(
        path=str(getattr(bundle, "path", "") or ""),
        filename=getattr(bundle.source, "filename", "") if getattr(bundle, "source", None) else "",
        loadable=True, kind=bundle.kind, quality=_quality_from_qc(qc), qc_ok=qc.ok,
        qc_flags=qc.flags, columns=columns, n_numeric_cols=n_numeric,
        note=_kind_note(bundle.kind, qc),
    )


def assess_file(path: str) -> FileAssessment:
    """Load + classify + QC one file → a :class:`FileAssessment`. Fail-soft: a path that cannot be
    ingested (missing / unrecognized / unreadable) is ``loadable=False`` with ``kind=UNKNOWN`` — an
    honest "couldn't read this", never a raise (the matcher then stays optimistic on it)."""
    from pathlib import Path

    filename = Path(str(path)).name
    try:
        from engine.ingest import ingest
        from engine.qc import run_qc

        bundle = ingest(path)
        qc = run_qc(bundle)
        columns, n_numeric = _frame_signature(bundle.payload)
        return FileAssessment(
            path=str(path), filename=filename, loadable=True, kind=bundle.kind,
            quality=_quality_from_qc(qc), qc_ok=qc.ok, qc_flags=qc.flags,
            columns=columns, n_numeric_cols=n_numeric, note=_kind_note(bundle.kind, qc),
        )
    except Exception as exc:  # noqa: BLE001 — unreadable here is an honest assessment, not a bug
        return FileAssessment(path=str(path), filename=filename, loadable=False, kind=UNKNOWN,
                              quality=0, qc_ok=False, note=f"couldn't read this file ({exc})")


_KIND_LABEL = {
    SC_COUNTS: "single-cell matrix", BULK_COUNTS: "bulk count matrix",
    DE_RESULTS: "differential-expression table", PROTEOMICS: "proteomics intensities",
    METABOLOMICS: "metabolomics features", GENERIC_TABLE: "a table (modality unclear)",
    UNKNOWN: "unrecognized",
}


def _kind_note(kind: str, qc: QCReport) -> str:
    label = _KIND_LABEL.get(kind, kind)
    if not qc.ok and qc.flags:
        return f"{label} — {qc.flags[0].message}"
    return label


def _frame_signature(payload: Any) -> tuple[list[str], int]:
    """``(column names, #numeric columns)`` for a table payload; ``([], 0)`` for a matrix/other.
    The shape the per-skill schema layer checks the dropped file's columns against."""
    if any(t.__name__ == "DataFrame" for t in type(payload).__mro__):
        cols = [str(c) for c in payload.columns]
        n_num = int(payload.select_dtypes(include="number").shape[1])
        return cols, n_num
    return [], 0


# --- L1 schema layer: does the table carry the COLUMNS a skill needs? -----------------------
# Layered like the extractor ([[layered-deterministic-extraction]]): a per-skill column contract
# (L1, precise + actionable) sits ABOVE the coarse modality class gate (L2). Only the skills whose
# need is about *named columns* have a contract — a fold-change + significance table (volcano /
# enrichment) or a ranked gene list (gsea). Matrix/count skills are checked by modality alone (their
# Kind IS the precise signal). Column groups are matched by case-insensitive substring against the
# shared synonym primitive (``engine.vocab.DE_LOGFC_SYNONYMS`` / ``DE_PVAL_SYNONYMS``) so header
# variants (``avg_log2FC``, ``p_val_adj``, ``adj.P.Val``) all resolve. See
# ``docs/architecture-consistency-gate/skill-input-contract.md`` (D1).
from engine.columns import GENE as _GENE  # noqa: E402 — single-source the gene synonyms
from engine.columns import override_column, role_of_synonyms  # noqa: E402
from engine.vocab import DE_LOGFC_SYNONYMS as _LOGFC  # noqa: E402 — the shared column vocabulary
from engine.vocab import DE_PVAL_SYNONYMS as _PVAL  # noqa: E402
# A named column group: (human label, synonym substrings). A table satisfies it if any column
# name contains any synonym.
_FC = ("a fold-change column", _LOGFC)
_SIG = ("a significance (p / padj) column", _PVAL)
_GENE_G = ("a gene/feature label column", _GENE)

# skill_id -> (list of required named groups, needs_a_numeric_score). ``needs_numeric`` adds a
# "≥1 numeric column" requirement (a ranked list's score) on top of the named groups.
_SCHEMA: dict[str, tuple[list[tuple[str, tuple[str, ...]]], bool]] = {
    "volcano": ([_FC, _SIG], False),       # a DE table to threshold + draw
    "enrichment": ([_FC, _SIG], False),    # a DE table to threshold by fc/fdr
    "gsea": ([_GENE_G], True),             # a ranked gene list: gene + a numeric score
}


def _has_group(columns_lower: list[str], synonyms: tuple[str, ...]) -> bool:
    return any(any(s in c for s in synonyms) for c in columns_lower)


def _group_present(fa: FileAssessment, cols_lower: list[str], label: str, syns: tuple[str, ...],
                   override: dict | None) -> bool:
    """A required column group is present when a user override maps its role to an existing column,
    or a synonym matches. The override (``{role: column}``) wins over synonym detection."""
    role = role_of_synonyms(syns)
    if role is not None and override_column(override, role, fa.columns):
        return True
    return _has_group(cols_lower, syns)


def _check_schema(skill_id: str, fa: FileAssessment, override: dict | None = None
                  ) -> tuple[bool | None, str]:
    """Does ``fa``'s table carry the columns ``skill_id`` needs? → ``(ok, reason)``.

    ``True`` = all required columns/score present (precise fit); ``False`` = a determined miss with
    an actionable reason naming what to add/rename; ``None`` = this skill has no column contract
    (defer to the modality layer). Honest: only a *loaded* table can miss a column — an unloadable
    file never reaches here. ``override`` (the user ``{role: column}`` map, see :mod:`engine.columns`)
    satisfies a group when it points at an existing column — so a non-standard-named fold-change /
    significance / gene column the synonym sets miss still fits once the user maps it."""
    contract = _SCHEMA.get(skill_id)
    if contract is None:
        return None, ""
    groups, needs_numeric = contract
    cols = [c.lower() for c in fa.columns]
    missing = [label for label, syns in groups if not _group_present(fa, cols, label, syns, override)]
    if needs_numeric and fa.n_numeric_cols < 1:
        missing.append("a numeric score column")
    have = [label for label, syns in groups if _group_present(fa, cols, label, syns, override)]
    if not missing:
        found = ", ".join(label for label, _ in groups)
        return True, f"has {found} — fits {skill_id}"
    need = ", ".join(label for label, _ in groups) + (" + a numeric score" if needs_numeric else "")
    got = f" (found {', '.join(have)})" if have else ""
    return False, f"missing {', '.join(missing)}; {skill_id} needs {need}{got}"


# --- per-(file, skill) fit ("does this good data fit THIS analysis?") ------------------------


# What the score *means* — the user-facing confidence band the rank translates into, so a "55/100"
# reads as a decision, not a number. Five bands, worst→best is the reverse: a wrong file is loud,
# a confident one is calm. The FE styles each band; the BE owns the mapping (one source of truth).
CONF_CONFIDENT = "confident"     # right, clean data → trust the run on this file
CONF_USABLE = "usable"           # right data, minor caveats → runs, read the QC note
CONF_UNCERTAIN = "uncertain"     # can't confirm it fits (modality/columns unclear) → check it
CONF_NOT_A_FIT = "not_a_fit"     # wrong data for this analysis → swap it before running
CONF_UNREADABLE = "unreadable"   # couldn't open the file at all

_CONF_LABEL = {
    CONF_CONFIDENT: "Confident — the right, clean data for this analysis",
    CONF_USABLE: "Usable — fits, with minor data caveats",
    CONF_UNCERTAIN: "Uncertain — can't confirm this fits; check it",
    CONF_NOT_A_FIT: "Not a fit — this isn't the data this analysis needs",
    CONF_UNREADABLE: "Unreadable — couldn't open this file",
}


def _confidence(compatible: bool | None, verdict: str, qc_ok: bool) -> str:
    if verdict == "unreadable":
        return CONF_UNREADABLE
    if compatible is False:
        return CONF_NOT_A_FIT
    if compatible is True:
        return CONF_CONFIDENT if qc_ok else CONF_USABLE
    return CONF_UNCERTAIN


class DataFit(BaseModel):
    """How well one file feeds one skill — the rankable number surfaced before/after a run and used
    by the matcher. ``compatible`` is tri-state: ``True`` (right modality), ``False`` (a *certain*
    payload-class mismatch — gated), ``None`` (unclear/unreadable — optimistic, never gated). The
    ``confidence`` band is what the ``score`` *means* to the user (Confident / Usable / …)."""

    path: str
    filename: str = ""
    skill_id: str = ""
    kind: str = UNKNOWN
    score: int = 0                 # 0-100 rank (modality fit × cleanliness)
    compatible: bool | None = None
    verdict: str = "unclear"       # fit | fit_dirty | wrong_modality | missing_columns | unclear | unreadable
    qc_ok: bool = True
    reason: str = ""

    @property
    def gated(self) -> bool:
        """A *certain* incompatibility the matcher must not feed (→ ``data_unmatched``)."""
        return self.compatible is False

    @computed_field
    @property
    def confidence(self) -> str:
        """The user-facing band the score translates into (serialized for the FE)."""
        return _confidence(self.compatible, self.verdict, self.qc_ok)

    @computed_field
    @property
    def confidence_label(self) -> str:
        """The one-line meaning of the band (serialized for the FE)."""
        return _CONF_LABEL[self.confidence]


_FIT, _UNCLEAR, _WRONG = 100, 55, 12  # base score before the cleanliness multiplier


def _mk(fa: FileAssessment, skill_id: str, *, compatible: bool | None, base: int,
        verdict: str, reason: str) -> DataFit:
    score = _WRONG if compatible is False else int(round(base * (fa.quality / 100.0)))
    return DataFit(path=fa.path, filename=fa.filename, skill_id=skill_id, kind=fa.kind,
                   score=max(0, min(100, score)), compatible=compatible, verdict=verdict,
                   qc_ok=fa.qc_ok, reason=reason)


def _fit_ok(fa: FileAssessment, skill_id: str, reason: str) -> DataFit:
    verdict = "fit" if fa.qc_ok else "fit_dirty"
    if not fa.qc_ok and fa.qc_flags:
        reason += f"; {fa.qc_flags[0].message}"
    return _mk(fa, skill_id, compatible=True, base=_FIT, verdict=verdict, reason=reason)


def fit(skill_id: str, fa: FileAssessment, *, column_override: dict | None = None) -> DataFit:
    """Score a file (its :class:`FileAssessment`) against ``skill_id`` → a :class:`DataFit`.

    Layered, most-precise-first ([[layered-deterministic-extraction]]): **L2** payload-class gate (a
    table can never be a single-cell matrix, and vice-versa — a *certain* mismatch) → **L1** column
    schema (does the table carry the columns this skill needs — authoritative + actionable when the
    skill has a contract) → **L3** coarse modality fallback (for skills without a column contract).
    The base score (fit / unclear / wrong) × the file's cleanliness fraction, so the same file reads
    differently per analysis and a dirty-but-right file ranks below a clean-and-right one.

    ``column_override`` (the user ``{role: column}`` map) is honoured at the L1 schema layer so a
    DE table with a non-standard-named fold-change/significance/gene column fits once the user maps
    it; the matcher / ranking callers leave it ``None`` (unchanged)."""
    if not fa.loadable:
        return DataFit(path=fa.path, filename=fa.filename, skill_id=skill_id, kind=fa.kind,
                       score=0, compatible=None, verdict="unreadable", qc_ok=False,
                       reason=fa.note or "couldn't read this file")

    required = _REQS.get(skill_id)
    label = _KIND_LABEL.get(fa.kind, fa.kind)

    # L2 — certain payload-class mismatch (matrix ↔ table). The strongest, always-honest gate.
    if required is not None and _kind_class(fa.kind) not in {_kind_class(k) for k in required}:
        need = " / ".join(sorted(_KIND_LABEL.get(k, k) for k in required))
        return _mk(fa, skill_id, compatible=False, base=_WRONG, verdict="wrong_modality",
                   reason=f"this is {label}, but {skill_id} needs {need}")

    # L1 — precise column schema (authoritative when this skill has a column contract).
    schema_ok, schema_reason = _check_schema(skill_id, fa, column_override)
    if schema_ok is True:
        return _fit_ok(fa, skill_id, schema_reason)
    if schema_ok is False:
        return _mk(fa, skill_id, compatible=False, base=_WRONG, verdict="missing_columns",
                   reason=schema_reason)

    # L3 — coarse modality fallback (no column contract for this skill).
    if required is None:
        return _mk(fa, skill_id, compatible=None, base=_UNCLEAR, verdict="unclear",
                   reason=f"{label} — no modality constraint for {skill_id}")
    if fa.kind in required:
        return _fit_ok(fa, skill_id, f"{label} — fits {skill_id}")
    if fa.kind in (GENERIC_TABLE, UNKNOWN):
        # right class, unclear sub-kind — don't claim incompatible (could be a classifier miss).
        return _mk(fa, skill_id, compatible=None, base=_UNCLEAR, verdict="unclear",
                   reason=f"{label} — may or may not fit {skill_id}")
    need = " / ".join(sorted(_KIND_LABEL.get(k, k) for k in required))
    return _mk(fa, skill_id, compatible=False, base=_WRONG, verdict="wrong_modality",
               reason=f"this is {label}, but {skill_id} needs {need}")


# --- pre-run data-contract gate (D1) --------------------------------------------------------


def contract_message(df: DataFit) -> str:
    """A clear, actionable pre-run message for a data-contract block (D1) — frames the fit verdict's
    reason with a next step. Co-located with the verdict semantics (``fit``/``_check_schema``) so the
    wording stays in sync with what actually gated. Used by ``POST /run`` when a skill is fed a
    certain mismatch (missing required columns / wrong payload class) to surface a 4xx the user can
    act on, instead of a runtime stack trace inside the skill. See ``skill-input-contract.md``."""
    reason = df.reason or f"this file isn't what {df.skill_id} needs"
    return (
        f"This data doesn't fit {df.skill_id}: {reason}. "
        "Swap in a file with what this analysis needs, or pick a skill that matches this data."
    )


# --- ranking + matcher entry points ---------------------------------------------------------


def inventory(paths: list[str]) -> dict[str, FileAssessment]:
    """Assess each path once → ``{path: FileAssessment}`` (the per-run cache the matcher reuses so
    a file is loaded a single time, not once per panel)."""
    return {p: assess_file(p) for p in paths}


def _assessments_for(paths: list[str], assessments: dict[str, FileAssessment] | None
                     ) -> list[FileAssessment]:
    if assessments is None:
        return [assess_file(p) for p in paths]
    return [assessments.get(p) or assess_file(p) for p in paths]


def rank(skill_id: str, paths: list[str], *,
         assessments: dict[str, FileAssessment] | None = None) -> list[DataFit]:
    """Every candidate file scored against ``skill_id``, best fit first. ``assessments`` reuses a
    pre-built :func:`inventory`; omit it to assess on the fly (fail-soft)."""
    fits = [fit(skill_id, fa) for fa in _assessments_for(paths, assessments)]
    # best first: usable (True/None) over gated, then by score; stable for equal scores.
    return sorted(fits, key=lambda f: (f.compatible is False, -f.score))


def best_match(skill_id: str, paths: list[str], *,
               assessments: dict[str, FileAssessment] | None = None
               ) -> tuple[str | None, DataFit | None, str]:
    """Pick the data file that best feeds ``skill_id`` → ``(path | None, fit | None, note)``.

    Honest by the load-bearing rule: a file is fed only when it is *not a certain mismatch*. If every
    loadable candidate is a certain mismatch (the Yoshimura QC-table-to-single-cell case), returns
    ``(None, best_gated_fit, reason)`` so the caller marks ``data_unmatched`` instead of crashing the
    skill. Returns ``(None, None, "")`` when there are no candidates at all (caller falls back)."""
    if not paths:
        return None, None, ""
    ranked = rank(skill_id, paths, assessments=assessments)
    usable = [f for f in ranked if f.compatible is not False]
    if usable:
        chosen = usable[0]
        note = f"fit {chosen.score}/100 — {chosen.reason}"
        if len(usable) > 1:
            note += f" (ambiguous — best of {len(usable)}; pick per panel)"
        return chosen.path, chosen, note
    # all loadable candidates are certain mismatches → honest data_unmatched
    return None, ranked[0], ranked[0].reason


# --- the "rank the dropped data" surface (before + after a run) ------------------------------


class FileFitReport(BaseModel):
    """One dropped supplement ranked against a set of analyses (a run's panels / the routed skills):
    its overall quality + the best-fitting analysis + the full per-skill ranking. This is the wire
    shape the FE shows **before** Run (so a wrong/dirty file is visibly poor and can be swapped) and
    **after** (in the gap report). `` score`` is the headline 0-100 the owner asked for."""

    path: str
    filename: str = ""
    kind: str = UNKNOWN
    quality: int = 0               # cleanliness alone (is-this-good-data)
    qc_ok: bool = True
    loadable: bool = False
    note: str = ""                 # kind + top QC message
    score: int = 0                 # headline fit = the best per-skill score
    best_skill: str = ""
    best_verdict: str = ""
    fits: list[DataFit] = Field(default_factory=list)  # per-skill ranking, best first

    @computed_field
    @property
    def confidence(self) -> str:
        """The headline band for this file = the best-fitting analysis's band (or, with no analyses
        to score against, an unreadable file is ``unreadable`` and a readable one is ``uncertain``)."""
        if self.fits:
            return self.fits[0].confidence
        return CONF_UNREADABLE if not self.loadable else CONF_UNCERTAIN

    @computed_field
    @property
    def confidence_label(self) -> str:
        return _CONF_LABEL[self.confidence]


def report_files(paths: list[str], skill_ids: list[str], *,
                 assessments: dict[str, FileAssessment] | None = None) -> list[FileFitReport]:
    """Rank each dropped file against ``skill_ids`` (the run's panel skills / routed analyses).

    One :class:`FileFitReport` per file: its standalone quality + the best analysis it can feed +
    the full per-skill breakdown. Reuses a pre-built :func:`inventory` so each file loads once. The
    single source of truth for the data-fit panel, used by the pre-run endpoint AND the gap report."""
    inv = assessments or inventory(paths)
    skills = sorted({s for s in skill_ids if s})
    out: list[FileFitReport] = []
    for p in paths:
        fa = inv.get(p) or assess_file(p)
        fits = sorted((fit(s, fa) for s in skills),
                      key=lambda f: (f.compatible is False, -f.score))
        best = fits[0] if fits else None
        out.append(FileFitReport(
            path=p, filename=fa.filename, kind=fa.kind, quality=fa.quality, qc_ok=fa.qc_ok,
            loadable=fa.loadable, note=fa.note, score=best.score if best else fa.quality,
            best_skill=best.skill_id if best else "", best_verdict=best.verdict if best else "",
            fits=fits,
        ))
    return out
