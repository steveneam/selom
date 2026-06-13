"""Statistical / data-quality guardrails (charter B4 — publish-confidence).

The third leg of the publish-confidence bundle: alongside the reproducibility record
(``provenance.py``) and the methods prose (``methods.py``), this surfaces the *caveats*
a reader needs to trust a figure — was multiple-testing correction applied, is the FDR
threshold sane, are there too few cells, does the input look already normalized, is
there an uncorrected batch?

Two kinds of check:

  * method/param guardrails — derived from the skill + its resolved parameters; always
    available, deterministic, no data read.
  * data guardrails — derived from a light profile of the input (cell count, value
    scale, candidate batch columns). Best-effort: built only for ``.h5ad`` inputs when
    ``anndata`` is importable (the real-engine path); silently skipped otherwise so the
    light/stub path and CSV inputs never error.

Cluster-separation quality (silhouette) is emitted separately by the cluster runner as
the figure subtitle — it needs the computed embedding, so it lives with the analysis.

Each guardrail is ``{"level": "info"|"warn", "code", "title", "detail"}``. Pure-Python;
``build`` never raises — a guardrail failure must never break the figure.
"""

from __future__ import annotations

from skills.contract import SkillSpec, resolved_params

# Skills that apply FDR / multiple-testing correction internally.
_FDR_SKILLS = {"deg", "volcano", "enrichment"}
# scRNA skills that normalize raw counts internally (CPM-10k + log1p) — pre-normalized
# input risks double-normalization.
_INTERNAL_NORMALIZE = {"umap_scrna", "cluster", "violin"}
# obs column names that usually denote a batch / sample covariate.
_BATCH_KEYS = {"batch", "sample", "donor", "patient", "condition", "batch_id", "orig.ident"}

_LOW_CELL = 200          # below this, scRNA embeddings/clustering get unstable
_NORMALIZED_MAX = 50.0   # log/CPM matrices rarely exceed this; raw counts do


def _g(level: str, code: str, title: str, detail: str) -> dict:
    return {"level": level, "code": code, "title": title, "detail": detail}


def _method_guardrails(spec: SkillSpec, p: dict) -> list[dict]:
    out: list[dict] = []
    if spec.id in _FDR_SKILLS:
        out.append(
            _g(
                "info",
                "multiple-testing",
                "Multiple-testing correction applied",
                "p-values are corrected across genes/sets by the Benjamini–Hochberg FDR procedure.",
            )
        )
    fdr = p.get("fdr_threshold")
    if isinstance(fdr, (int, float)) and not isinstance(fdr, bool):
        if fdr >= 1.0:
            out.append(
                _g(
                    "warn",
                    "fdr-threshold",
                    "No FDR filtering",
                    f"fdr_threshold = {fdr}: every gene passes the significance cutoff.",
                )
            )
        elif fdr > 0.1:
            out.append(
                _g(
                    "warn",
                    "fdr-threshold",
                    "Lax FDR threshold",
                    f"fdr_threshold = {fdr}: thresholds above 0.1 inflate false positives; 0.05 is conventional.",
                )
            )
    return out


def _data_guardrails(spec: SkillSpec, profile: dict) -> list[dict]:
    out: list[dict] = []

    n_obs = profile.get("n_obs")
    if isinstance(n_obs, int) and n_obs < _LOW_CELL:
        out.append(
            _g(
                "warn",
                "low-cell-count",
                "Low cell count",
                f"{n_obs} cells: below ~{_LOW_CELL}, clustering and UMAP embeddings are "
                "unstable and sensitive to parameters.",
            )
        )

    if spec.id in _INTERNAL_NORMALIZE:
        x_max = profile.get("x_max")
        if profile.get("x_is_integer") is False and isinstance(x_max, (int, float)) and x_max < _NORMALIZED_MAX:
            out.append(
                _g(
                    "warn",
                    "pre-normalized-input",
                    "Input may already be normalized",
                    f"matrix has non-integer values (max ≈ {x_max:.1f}); this skill normalizes "
                    "raw counts internally (CPM-10k → log1p), so pre-normalized input risks "
                    "double-normalization. Provide raw counts.",
                )
            )

    for col, k in (profile.get("batch_columns") or {}).items():
        out.append(
            _g(
                "warn",
                "uncorrected-batch",
                "Possible uncorrected batch effect",
                f"obs column '{col}' has {k} groups and no batch-effect correction is applied; "
                "consider Harmony/BBKNN before clustering or embedding.",
            )
        )

    return out


def _profile(data_path: str) -> dict | None:
    """Light, best-effort profile of the input. None unless it's a parseable .h5ad."""
    if not data_path.lower().endswith(".h5ad"):
        return None
    try:
        return _profile_h5ad(data_path)
    except Exception:
        return None


def _profile_h5ad(data_path: str) -> dict:
    import anndata  # only present with the omics extra (real-engine path)
    import numpy as np

    adata = anndata.read_h5ad(data_path, backed="r")
    try:
        n_obs = int(adata.n_obs)

        # Sample up to 200 cells to gauge the value scale without loading the whole matrix.
        sample = adata.X[: min(200, n_obs)]
        arr = sample.toarray() if hasattr(sample, "toarray") else np.asarray(sample)
        arr = arr[np.isfinite(arr)]
        x_max = float(arr.max()) if arr.size else 0.0
        x_is_integer = bool(arr.size) and bool(np.all(arr == np.round(arr)))

        batch_columns: dict[str, int] = {}
        for col in adata.obs.columns:
            if str(col).lower() in _BATCH_KEYS:
                k = int(adata.obs[col].nunique())
                if 2 <= k <= max(2, n_obs // 2):  # >1 group, but not a per-cell unique id
                    batch_columns[str(col)] = k

        return {
            "n_obs": n_obs,
            "x_max": x_max,
            "x_is_integer": x_is_integer,
            "batch_columns": batch_columns,
        }
    finally:
        # Release the backed file handle so the caller can unlink the temp upload (Windows).
        try:
            if getattr(adata, "isbacked", False) and adata.file is not None:
                adata.file.close()
        except Exception:
            pass


def build(spec: SkillSpec, data_path: str, params: dict) -> list[dict]:
    """All guardrails for one figure — method/param checks plus any data checks."""
    try:
        out = _method_guardrails(spec, resolved_params(spec, params))
    except Exception:
        out = []
    try:
        profile = _profile(data_path)
        if profile:
            out += _data_guardrails(spec, profile)
    except Exception:
        pass
    return out
