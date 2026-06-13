"""Statistical / data-quality guardrails (charter B4 — publish-confidence).

The third leg of the publish-confidence bundle: alongside the reproducibility record
(``provenance.py``) and the methods prose (``methods.py``), this surfaces the *caveats*
a reader needs to trust a figure — was multiple-testing correction applied, is the FDR
threshold sane, are there too few cells, does the input look already normalized, is
there an uncorrected batch?

Two kinds of check:

  * method/param guardrails — derived from the skill + its resolved parameters; always
    available, deterministic, no data read.
  * data guardrails — derived from a light profile of the input. For ``.h5ad`` (needs
    ``anndata``, the real-engine path): cell count, value scale, candidate batch columns.
    For ``.csv``/``.tsv`` (stdlib, always): bulk-DE replication + raw-count check (deg),
    and gene-list size (enrichment). Best-effort and never-raising, so the light/stub
    path and unrecognized inputs simply skip the data checks.

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


_MIN_REPLICATES = 3   # bulk DE wants >= 3 per group for stable dispersion estimates
_MIN_GENES = 10       # over-representation analysis is unstable on tiny gene lists


def _csv_data_guardrails(spec: SkillSpec, profile: dict) -> list[dict]:
    out: list[dict] = []

    if spec.id == "deg":
        # Bulk count matrix: column 0 = gene id, the rest are samples; the 2-level
        # design is the column-name prefix before the first '_' (matches the runner).
        n_samples = max(0, profile.get("n_cols", 0) - 1)
        groups = _column_groups(profile.get("header") or [])
        if 0 < n_samples < 2 * _MIN_REPLICATES:
            out.append(
                _g(
                    "warn",
                    "low-replication",
                    "Few samples for bulk DE",
                    f"{n_samples} samples in the count matrix; bulk differential expression needs "
                    f"replication (≥{_MIN_REPLICATES} per group) for stable dispersion estimates.",
                )
            )
        elif groups and min(groups.values()) < _MIN_REPLICATES:
            small = ", ".join(f"{k} (n={v})" for k, v in groups.items() if v < _MIN_REPLICATES)
            out.append(
                _g(
                    "warn",
                    "low-replication",
                    "Few replicates in a group",
                    f"group {small}: bulk DE is unstable below {_MIN_REPLICATES} replicates per group.",
                )
            )
        if profile.get("numeric_is_integer") is False:
            out.append(
                _g(
                    "warn",
                    "non-integer-counts",
                    "Counts are not integers",
                    "pyDESeq2 expects raw integer counts; the matrix has non-integer values "
                    "(normalized/transformed), which biases the dispersion model. Provide raw counts.",
                )
            )

    elif spec.id == "enrichment":
        n_genes = profile.get("n_rows", 0)
        if 0 < n_genes < _MIN_GENES:
            out.append(
                _g(
                    "warn",
                    "small-gene-list",
                    "Small gene list",
                    f"{n_genes} genes in the query; over-representation analysis is underpowered and "
                    f"unstable below ~{_MIN_GENES} genes.",
                )
            )

    return out


def _column_groups(header: list) -> dict:
    """Sample-column counts per design group, matching the bulk-DEG runner's name-based
    inference (strip the trailing replicate suffix: ctrl_1 -> ctrl). Column 0 is the
    gene id, so it's skipped. (A supplied design sheet overrides this in the runner.)"""
    import re

    groups: dict[str, int] = {}
    for name in header[1:]:
        label = re.sub(r"_\d+$", "", str(name))
        groups[label] = groups.get(label, 0) + 1
    return groups


def _to_float(cell: str):
    try:
        return float(cell)
    except (TypeError, ValueError):
        return None


def _profile_csv(data_path: str) -> dict | None:
    """Light, best-effort CSV/TSV profile (stdlib). Dimensions + a value-scale sample
    from the first rows (data columns only). None on any read error."""
    import csv

    delimiter = "\t" if data_path.lower().endswith(".tsv") else ","
    try:
        with open(data_path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle, delimiter=delimiter)
            header = next(reader, None)
            if header is None:
                return None
            n_rows = 0
            saw_numeric = False
            is_integer = True
            max_val = 0.0
            for row in reader:
                n_rows += 1
                if n_rows <= 50:  # sample value scale from the first data rows only
                    for cell in row[1:]:
                        value = _to_float(cell)
                        if value is None:
                            continue
                        saw_numeric = True
                        max_val = max(max_val, value)
                        if value != round(value):
                            is_integer = False
            return {
                "kind": "csv",
                "n_rows": n_rows,
                "n_cols": len(header),
                "header": [str(h) for h in header],
                "numeric_is_integer": is_integer if saw_numeric else None,
                "numeric_max": max_val if saw_numeric else None,
            }
    except Exception:
        return None


def _profile(data_path: str) -> dict | None:
    """Light, best-effort h5ad profile. None unless it's a parseable .h5ad."""
    if not data_path.lower().endswith(".h5ad"):
        return None
    try:
        return _profile_h5ad(data_path)
    except Exception:
        return None


def _profile_h5ad(data_path: str) -> dict:
    import anndata  # only present with the omics extra (real-engine path)
    import numpy as np
    from scipy import sparse

    adata = anndata.read_h5ad(data_path, backed="r")
    try:
        n_obs = int(adata.n_obs)

        # Read up to 200 cells into memory to gauge the value scale without loading the
        # whole matrix. Slice the AnnData (not adata.X) + to_memory so this works for both
        # backed dense and backed sparse h5ad — real scRNA matrices are sparse.
        sample = adata[: min(200, n_obs)].to_memory().X
        if sparse.issparse(sample):
            vals = np.asarray(sample.data, dtype="float64")  # stored (nonzero) values
        else:
            vals = np.asarray(sample, dtype="float64").ravel()
        vals = vals[np.isfinite(vals)]
        x_max = float(vals.max()) if vals.size else 0.0
        x_is_integer = bool(vals.size) and bool(np.all(vals == np.round(vals)))

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
    low = data_path.lower()
    try:
        if low.endswith(".h5ad"):
            profile = _profile(data_path)
            if profile:
                out += _data_guardrails(spec, profile)
        elif low.endswith((".csv", ".tsv")):
            profile = _profile_csv(data_path)
            if profile:
                out += _csv_data_guardrails(spec, profile)
    except Exception:
        pass
    return out
