"""Engine spine — the layered data-type *profile* + the dynamic *cleaning plan* (P1/P3).

This is the source of truth for the "what kind of data is this, and what (if anything) do we
clean before analysis?" pane the user sees on drop. Two honest, layered answers:

* :func:`profile_data` — a friendly **data-type label** decided the layered way
  ([[layered-deterministic-extraction]]): **L1 file format** (a ``.iwxdata`` is *certainly* ERG),
  then **L2 high-precision column keywords** (an a-/b-wave + intensity table is ERG — a signature a
  transcriptomics table never carries), then the **L3 modality** from :func:`engine.classify`. The
  user can always override (the third layer is *user input*; ``main.py`` passes ``hint``/``profile``).
  Honesty rule (mirrors :mod:`engine.compat`): only assign a *specific* type on a positively-
  determined signal — anything we can't type stays a neutral "Data table", never a false claim.

* :func:`plan_cleaning` — the **cleaning plan** keyed off the modality: a count matrix (single-cell /
  bulk / proteomics) gets the *real* proposed steps (with cheap, honest before/after deltas where the
  orientation is certain); a results table / a generic measurements table / an ERG table gets an
  **empty plan** ("used as-is") — so the cleaning pane is *dynamic*, never the gene-subset cleaning
  forced onto every file. Cleaning is *proposed, not imposed*; the FE renders this verbatim.

Both functions are pure and fail-soft (never raise — a plan we can't compute degrades to descriptive,
never a crash), because they are surfaced on the best-effort inspect path.
"""

from __future__ import annotations

from pathlib import PurePath
from typing import Any

from pydantic import BaseModel, Field

from engine.databundle import _is_anndata, _is_dataframe
from engine.models import (
    BULK_COUNTS,
    DE_RESULTS,
    GENERIC_TABLE,
    METABOLOMICS,
    PROTEOMICS,
    SC_COUNTS,
    UNKNOWN,
)

# --- data-type profile (the friendly, layered label) ------------------------------------

ERG = "erg"  # not an engine Kind (the taxonomy stays the omics modalities) — a *profile* on top.

# L1: file formats that are certain about the data type regardless of contents.
_ERG_FORMATS = (".iwxdata",)

# L2: high-precision ERG column tokens. An electrophysiology metrics table carries a/b-wave
# amplitudes against flash intensity — tokens no transcriptomics table has, so matching both an
# a-/b-wave AND an intensity column is a near-zero-false-positive signal (the honesty rule).
_ERG_WAVE_TOKENS = ("a_wave", "b_wave", "a-wave", "b-wave", "awave", "bwave", "a wave", "b wave")
_ERG_INTENSITY_TOKENS = ("intensity", "cd_s_m2", "cd.s.m", "cd·s")

# Friendly labels per modality Kind (the L3 fallback). Kept human; the FE shows these verbatim.
_KIND_LABEL: dict[str, str] = {
    SC_COUNTS: "Single-cell RNA-seq",
    BULK_COUNTS: "Bulk RNA-seq counts",
    DE_RESULTS: "Differential-expression results",
    PROTEOMICS: "Proteomics intensities",
    METABOLOMICS: "Metabolomics",
    GENERIC_TABLE: "Data table",
    UNKNOWN: "Unrecognized data",
}
# How confident the label is — drives whether the FE nudges the user to confirm the type.
_KIND_CONFIDENCE: dict[str, str] = {
    SC_COUNTS: "likely",
    BULK_COUNTS: "likely",
    DE_RESULTS: "likely",
    PROTEOMICS: "likely",
    METABOLOMICS: "likely",
    GENERIC_TABLE: "unsure",
    UNKNOWN: "unsure",
}


class DataProfile(BaseModel):
    """The friendly data-type verdict surfaced on drop. ``code`` is the machine key (an engine
    ``Kind`` or the ``erg`` profile); ``label`` is the human name; ``confidence`` is one of
    ``certain | likely | unsure``; ``reason`` is the *why* (the layer that decided), shown so the
    classification is transparent and the user can correct it."""

    code: str = UNKNOWN
    label: str = "Unrecognized data"
    confidence: str = "unsure"
    reason: str = ""
    overridden: bool = False  # the user set the type explicitly (L3) — never second-guess them.


def _columns_lower(df: Any) -> list[str]:
    return [str(c).strip().lower() for c in df.columns]


def _looks_erg(df: Any) -> bool:
    cols = _columns_lower(df)
    has_wave = any(any(tok in c for tok in _ERG_WAVE_TOKENS) for c in cols)
    has_intensity = any(any(tok in c for tok in _ERG_INTENSITY_TOKENS) for c in cols)
    return has_wave and has_intensity


def profile_data(bundle: Any, *, override: str | None = None) -> DataProfile:
    """Layered, honest data-type label for an ingested ``DataBundle``. ``override`` (the user's
    L3 choice — an engine ``Kind`` or ``erg``) wins outright. Otherwise: L1 format → L2 ERG
    columns → L3 modality. Never raises."""
    if override:
        code = override.strip().lower()
        if code == ERG:
            return DataProfile(code=ERG, label="ERG / electrophysiology", confidence="certain",
                               reason="You set the data type.", overridden=True)
        return DataProfile(code=code, label=_KIND_LABEL.get(code, code), confidence="certain",
                           reason="You set the data type.", overridden=True)

    # L1 — file format is certain about the type.
    fname = getattr(getattr(bundle, "source", None), "filename", "") or ""
    if PurePath(fname).suffix.lower() in _ERG_FORMATS:
        return DataProfile(code=ERG, label="ERG / electrophysiology", confidence="certain",
                           reason=f"{PurePath(fname).suffix} is a native electrophysiology format.")

    # L2 — high-precision ERG column signature on a tabular payload.
    payload = getattr(bundle, "payload", None)
    if _is_dataframe(payload) and _looks_erg(payload):
        return DataProfile(code=ERG, label="ERG / electrophysiology", confidence="likely",
                           reason="a-/b-wave amplitude and flash-intensity columns recognized.")

    # L3 — the engine modality, as a friendly label.
    kind = getattr(bundle, "kind", UNKNOWN)
    label = _KIND_LABEL.get(kind, _KIND_LABEL[UNKNOWN])
    conf = _KIND_CONFIDENCE.get(kind, "unsure")
    reason = ("Modality not recognized — usable as a plain table."
              if kind in (GENERIC_TABLE, UNKNOWN) else "Recognized from the data's columns/shape.")
    return DataProfile(code=kind, label=label, confidence=conf, reason=reason)


# --- cleaning plan (the dynamic pane) ---------------------------------------------------

class CleaningStep(BaseModel):
    """One proposed cleaning operation + the effect it has on the matrix shape (negative =
    removed; ``None`` = a transform that changes values, not shape)."""

    id: str
    label: str
    detail: str = ""
    kind: str = "filter"  # filter (drops rows/cols) | transform (rescales) | selection (flags)
    obs_delta: int | None = None
    var_delta: int | None = None


class CleaningPlan(BaseModel):
    """The proposed cleaning for a dropped dataset — the dynamic "Before & after cleaning" pane.

    ``applies`` is False for a results / generic / ERG table (nothing to clean → an honest empty
    state, NOT the gene-subset cleaning). ``obs_label``/``var_label`` name the two axes for the
    detected type (cells/genes, samples/genes, rows/columns…). ``n_obs``/``n_var`` are the *raw*
    shape as dropped; the FE applies the (toggleable) step deltas for the "after" view."""

    kind: str
    profile: str = ""
    applies: bool = False
    obs_label: str = "rows"
    var_label: str = "columns"
    n_obs: int = 0
    n_var: int = 0
    steps: list[CleaningStep] = Field(default_factory=list)
    note: str = ""


def _empty_plan(kind: str, profile: str, n_obs: int, n_var: int, note: str,
                obs_label: str = "rows", var_label: str = "columns") -> CleaningPlan:
    return CleaningPlan(kind=kind, profile=profile, applies=False, obs_label=obs_label,
                        var_label=var_label, n_obs=n_obs, n_var=n_var, steps=[], note=note)


def _frame_shape(df: Any) -> tuple[int, int]:
    try:
        r, c = df.shape
        return int(r), int(c)
    except Exception:  # noqa: BLE001
        return 0, 0


def _sc_plan(adata: Any, profile: str) -> CleaningPlan:
    """Single-cell cleaning: drop rarely-detected genes + normalize. The gene-filter delta is
    the REAL count of genes seen in < 3 cells (cheap on the payload), so the before/after is
    honest — never a fabricated number."""
    n_cells, n_genes = int(adata.n_obs), int(adata.n_vars)
    var_delta: int | None = None
    try:
        import numpy as np
        from scipy.sparse import issparse

        X = adata.X
        if issparse(X):
            per_gene_cells = np.asarray((X > 0).sum(axis=0)).ravel()
        else:
            per_gene_cells = (np.asarray(X) > 0).sum(axis=0)
        kept = int((per_gene_cells >= 3).sum())
        var_delta = -(n_genes - kept)
    except Exception:  # noqa: BLE001 — degrade to a described step without a fabricated delta
        var_delta = None
    steps = [
        CleaningStep(id="filter_genes", label="Filter rarely-detected genes",
                     detail="Drop genes seen in fewer than 3 cells.", kind="filter",
                     var_delta=var_delta),
        CleaningStep(id="normalize", label="Normalize + log1p",
                     detail="Library-size normalize to 10,000 counts, then log1p.", kind="transform"),
    ]
    return CleaningPlan(kind=SC_COUNTS, profile=profile, applies=True, obs_label="cells",
                        var_label="genes", n_obs=n_cells, n_var=n_genes, steps=steps,
                        note="Standard single-cell cleaning before analysis.")


def _bulk_plan(df: Any, profile: str) -> CleaningPlan:
    """Bulk RNA-seq cleaning: drop low-count genes (rows) + size-factor normalize. Reports the
    table as genes × samples (the count-matrix convention) and computes the real low-count-gene
    delta over the numeric (sample) columns."""
    n_rows, _ = _frame_shape(df)            # genes × samples convention: rows = genes
    n_samples = n_rows  # safe default if no numeric columns resolve
    var_delta: int | None = None
    try:
        num = df.select_dtypes(include="number")
        n_samples = int(num.shape[1]) or n_rows
        if num.shape[1]:
            totals = num.to_numpy(dtype="float64", na_value=0.0).sum(axis=1)
            var_delta = -int((totals < 10).sum())
    except Exception:  # noqa: BLE001
        var_delta = None
    steps = [
        CleaningStep(id="drop_low", label="Drop low-count genes",
                     detail="Remove genes with fewer than 10 reads across all samples.",
                     kind="filter", var_delta=var_delta),
        CleaningStep(id="size_factor", label="Size-factor normalization",
                     detail="Library-size normalization before differential expression.",
                     kind="transform"),
    ]
    return CleaningPlan(kind=BULK_COUNTS, profile=profile, applies=True, obs_label="samples",
                        var_label="genes", n_obs=n_samples, n_var=n_rows, steps=steps,
                        note="Standard bulk RNA-seq cleaning before differential expression.")


def _proteomics_plan(df: Any, profile: str) -> CleaningPlan:
    """Proteomics cleaning: drop never-detected proteins + log2 + median-normalize + MNAR-aware
    impute. Reports proteins × samples; the never-detected delta is the real all-missing-row count."""
    n_rows, _ = _frame_shape(df)            # proteins × samples convention: rows = proteins
    n_samples = n_rows
    var_delta: int | None = None
    try:
        import numpy as np

        num = df.select_dtypes(include="number")
        n_samples = int(num.shape[1]) or n_rows
        if num.shape[1]:
            arr = num.to_numpy(dtype="float64", na_value=np.nan)
            var_delta = -int(np.isnan(arr).all(axis=1).sum())
    except Exception:  # noqa: BLE001
        var_delta = None
    steps = [
        CleaningStep(id="drop_undetected", label="Drop never-detected proteins",
                     detail="Remove proteins missing in every sample.", kind="filter",
                     var_delta=var_delta),
        CleaningStep(id="log2", label="Log2 transform", kind="transform"),
        CleaningStep(id="median_norm", label="Median normalization",
                     detail="Centre each sample to a common median.", kind="transform"),
        CleaningStep(id="impute", label="Impute missing (MNAR-aware)",
                     detail="Left-censored imputation for missing intensities.", kind="transform"),
    ]
    return CleaningPlan(kind=PROTEOMICS, profile=profile, applies=True, obs_label="samples",
                        var_label="proteins", n_obs=n_samples, n_var=n_rows, steps=steps,
                        note="Standard proteomics cleaning before differential abundance.")


def plan_cleaning(bundle: Any, *, profile: DataProfile | None = None) -> CleaningPlan:
    """The proposed cleaning for a classified ``DataBundle`` — the dynamic cleaning pane. Pass the
    already-computed ``profile`` to keep it consistent with the surfaced label (else it is derived).
    Never raises; an uncomputable plan degrades to an honest empty state."""
    prof = profile or profile_data(bundle)
    payload = getattr(bundle, "payload", None)
    kind = getattr(bundle, "kind", UNKNOWN)

    # An ERG / electrophysiology table is a tidy measurements table — used as-is. The gene-subset
    # cleaning that suits a count matrix would corrupt it, so the pane is honestly empty.
    if prof.code == ERG:
        n_obs, n_var = _frame_shape(payload) if _is_dataframe(payload) else (0, 0)
        return _empty_plan(kind, prof.code, n_obs, n_var,
                           "ERG measurements table — used as-is. No matrix cleaning "
                           "(gene filtering / normalization) applies.")

    try:
        if _is_anndata(payload):
            return _sc_plan(payload, prof.code)
        if _is_dataframe(payload):
            if kind == BULK_COUNTS:
                return _bulk_plan(payload, prof.code)
            if kind == PROTEOMICS:
                return _proteomics_plan(payload, prof.code)
            n_obs, n_var = _frame_shape(payload)
            if kind == DE_RESULTS:
                return _empty_plan(kind, prof.code, n_obs, n_var,
                                   "Pre-computed results table — used as-is. No cleaning needed.",
                                   obs_label="rows", var_label="columns")
            return _empty_plan(kind, prof.code, n_obs, n_var,
                               "Used as-is. No matrix cleaning applies to this table.",
                               obs_label="rows", var_label="columns")
    except Exception:  # noqa: BLE001 — the pane is best-effort; never break a valid inspect
        pass
    return _empty_plan(kind, prof.code, 0, 0, "Used as-is. No cleaning could be determined.")
