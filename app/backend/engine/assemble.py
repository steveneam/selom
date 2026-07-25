"""Engine spine — multi-sample scRNA assembly (the scRNA sibling of C6 ``ingest_many``).

A real GEO scRNA deposit (e.g. Kim/Hani GSE201356) arrives as a SET of *per-sample* 10x matrices —
one Cell-Ranger triplet (``matrix.mtx.gz`` + ``barcodes.tsv.gz`` + ``features.tsv.gz``) or one
per-sample ``.h5ad`` each — with **no per-cell design in ``obs``**: the design (line/genotype, sample
id, condition) lives in the *filenames* (``GSM6061839_2niPE2-ANAI-3_matrix.mtx.gz``).
:func:`assemble_scrna` reads that set, concatenates it into ONE AnnData, and **materializes the
filename-encoded design into ``obs``** — ``sample_id`` always (derived from each unit's filename
prefix), plus any ``line`` / ``condition`` / … the caller keys to each sample via ``obs_map``. This is
the scRNA peer of :func:`engine.ingest.ingest_many` (which merges single-condition ERG tables into
one multi-condition table); the shipped ``/data/combine`` is its ERG sibling.

Design = filenames + an optional ``obs_map`` (the confirmed intake answers): the sample *grouping* is
filename-derived (each triplet / ``.h5ad`` / 10x directory is one sample, keyed by its filename
prefix), and ``obs_map`` attaches the per-sample design fields keyed by that same filename identity —
DETECTED == CONSUMED, no guessing at biology from a token heuristic. scanpy/anndata do the read +
concat; each dep is lazy-imported inside a function so importing ``engine`` stays cheap.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from engine.ingest import is_10x_dir as _is_10x_dir  # A21 — ONE 10x detector, bound by identity
from engine.ingest import load_unit as _load_unit  # A21 — ONE loader registry, never a second one

# A 10x Cell-Ranger member file, keyed by role → the name tokens it can wear (v3 ``features`` and the
# older v2 ``genes``; gzip-compressed as GEO delivers, or plain). A per-sample deposit names each
# member ``<prefix>_<token>`` (the GEO ``GSM…_<sample>_matrix.mtx.gz`` shape), so stripping the token
# (and the joining separator) recovers the sample prefix that identifies the sample.
_ROLE_TOKENS: dict[str, tuple[str, ...]] = {
    "matrix": ("matrix.mtx.gz", "matrix.mtx"),
    "barcodes": ("barcodes.tsv.gz", "barcodes.tsv"),
    "features": ("features.tsv.gz", "features.tsv", "genes.tsv.gz", "genes.tsv"),
}
_CANONICAL_STEM = {"matrix": "matrix.mtx", "barcodes": "barcodes.tsv", "features": "features.tsv"}


def _split_10x_member(name: str) -> tuple[str, str] | None:
    """``('GSM6061839_2niPE2-ANAI-3', 'matrix')`` for a 10x triplet member, else ``None``.

    The sample prefix is the filename with its role token (and the trailing ``._- `` separator that
    joins it) stripped, so all three members of one sample collapse to the same prefix."""
    low = name.lower()
    for role, tokens in _ROLE_TOKENS.items():
        for tok in tokens:
            if low.endswith(tok):
                prefix = name[: len(name) - len(tok)].rstrip("._- ")
                return prefix, role
    return None


def _match_obs_entry(sample_key: str, obs_map: dict[str, dict] | None) -> dict[str, Any]:
    """The ``obs_map`` design fields for ``sample_key``, matched most-specific-first so the caller can
    key by the full prefix, the GSM-stripped biological name, or a distinctive substring:

    1. exact — ``obs_map`` key == the sample prefix (``GSM6061839_2niPE2-ANAI-3``),
    2. exact — key == the prefix with a leading ``GSM<digits>_`` stripped (``2niPE2-ANAI-3``),
    3. substring — key occurs in the prefix (case-insensitive); the **longest** such key wins, so a
       specific ``2niPE2-ANAI-3`` beats a shared ``2niPE2`` and matching stays deterministic.

    Returns ``{}`` when nothing matches (that sample keeps a filename-only ``sample_id``)."""
    if not obs_map:
        return {}
    if sample_key in obs_map:
        return dict(obs_map[sample_key])
    bio = re.sub(r"(?i)^gsm\d+[._-]+", "", sample_key)
    if bio != sample_key and bio in obs_map:
        return dict(obs_map[bio])
    low = sample_key.lower()
    hits = [(k, v) for k, v in obs_map.items() if k and str(k).lower() in low]
    if hits:
        _k, v = max(hits, key=lambda kv: len(str(kv[0])))
        return dict(v)
    return {}


def _resolve_obs(sample_key: str, obs_map: dict[str, dict] | None) -> dict[str, str]:
    """The obs columns for one sample: ``sample_id`` = the filename-derived key, overlaid with the
    matched ``obs_map`` entry (which may itself refine ``sample_id`` to a cleaner label). All values
    are stored as strings so the columns are categorical-clean and the h5ad serialises."""
    entry = _match_obs_entry(sample_key, obs_map)
    obs: dict[str, str] = {"sample_id": sample_key}
    for k, v in entry.items():
        obs[str(k)] = str(v)
    return obs


def _read_unit(kind: str, ref: Any) -> Any:
    """Load one per-sample unit to an AnnData. ``kind`` is ``dir`` (a 10x directory), ``h5ad`` (a
    single AnnData file), or ``triplet`` (a ``{role: path}`` dict staged into a canonical dir, which
    the registry then recognizes as a 10x directory — ``scanpy.read_10x_mtx`` requires the fixed
    ``matrix.mtx``/``barcodes.tsv``/``features.tsv`` names GEO's ``GSM…_`` prefix hides).

    Every read goes through :func:`engine.ingest.load_unit` — the ONE loader registry (A21). What
    stays here is only what assemble genuinely adds: the canonical-name staging dir."""
    if kind in ("dir", "h5ad"):
        return _load_unit(ref)
    staging = Path(tempfile.mkdtemp(prefix="selom-10x-"))
    try:
        for role, src in ref.items():
            src = Path(src)
            canonical = _CANONICAL_STEM[role] + (".gz" if src.name.lower().endswith(".gz") else "")
            dest = staging / canonical
            try:
                dest.symlink_to(src)  # avoid copying a multi-hundred-MB matrix
            except OSError:
                shutil.copyfile(src, dest)  # symlink unsupported (some FS/OS) → copy
        return _load_unit(staging)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _plan_units(srcs: list[str | Path]) -> list[tuple[str, str, Any]]:
    """Group the input paths into ordered per-sample units ``(sample_key, kind, ref)``.

    Directories and ``.h5ad`` files are one sample each; loose triplet members are grouped by their
    filename prefix. Raises ``ValueError`` for an unrecognized file (never silently dropped — a
    dropped member would corrupt the design) or an incomplete triplet (missing matrix/barcodes/
    features)."""
    triplets: dict[str, dict[str, str]] = {}
    order: list[tuple[str, str, Any]] = []  # non-triplet units in first-seen order
    triplet_order: list[str] = []
    unrecognized: list[str] = []
    for s in srcs:
        p = Path(s)
        name = p.name
        if _is_10x_dir(p):
            order.append((p.stem or name, "dir", str(p)))
            continue
        if name.lower().endswith(".h5ad"):
            order.append((p.stem, "h5ad", str(p)))
            continue
        member = _split_10x_member(name)
        if member is None:
            unrecognized.append(name)
            continue
        prefix, role = member
        prefix = prefix or (p.parent.name or "sample")  # a bare matrix.mtx.gz → its folder name
        if prefix not in triplets:
            triplets[prefix] = {}
            triplet_order.append(prefix)
        triplets[prefix][role] = str(p)

    if unrecognized:
        raise ValueError(
            "assemble_scrna: unrecognized file(s) " + ", ".join(repr(n) for n in unrecognized)
            + " — expected 10x triplet members (matrix.mtx / barcodes.tsv / features.tsv, "
              "optionally .gz), a 10x directory, or a per-sample .h5ad.")

    for prefix in triplet_order:
        members = triplets[prefix]
        missing = [r for r in ("matrix", "barcodes", "features") if r not in members]
        if missing:
            raise ValueError(
                f"assemble_scrna: sample {prefix!r} is missing its {', '.join(missing)} "
                f"file(s) — a 10x sample needs all of matrix + barcodes + features.")
        order.append((prefix, "triplet", members))
    return order


# --- gene-axis honesty (A14) ------------------------------------------------------------------
# ``ad.concat(join="outer", fill_value=0)`` unions the gene axis and writes 0 for every gene a
# sample's ``features.tsv`` never carried. Downstream a fabricated 0 is byte-indistinguishable from
# a measured zero count, so a gene present in only one sample's reference becomes a perfect
# sample-specific marker — and because ``obs['sample']`` is mirrored to the batch key, that is
# exactly the batch-confounded-as-biology failure mode. Live for real deposits that mix references
# or prefixed feature names (``GRCh38_``-prefixed symbols).
#
# So: the join DEFAULTS TO ``"inner"`` — every count in the assembled matrix is a measured count —
# and whichever join runs, the overlap is MEASURED and REPORTED. Silently dropping genes would be
# the same defect wearing the other hat, so ``"inner"`` is not allowed to be quiet either: the
# verdict below states what was dropped or fabricated, and warns when the references disagree.
JOINS = ("inner", "outer")

# Below this shared/union ratio the samples are not plausibly the same reference (a Cell-Ranger
# re-run against one reference is the fix, not a join flag).
_OVERLAP_WARN_BELOW = 0.9


def gene_overlap(parts: list, join: str) -> dict:
    """The honest gene-axis verdict for a set of per-sample AnnData, computed BEFORE the concat.

    Returns ``n_genes_union`` / ``n_genes_shared`` / ``per_sample_n_genes`` / ``shared_fraction``,
    the ``join`` that ran, how many genes it ``dropped`` (inner) or ``zero_filled`` (outer), and a
    ``level`` + ``message`` + ``fix``. ``level`` is ``"ok"`` when every sample carries the same gene
    set, ``"info"`` when they differ but overlap well, and ``"warn"`` below
    :data:`_OVERLAP_WARN_BELOW` — the references disagree and no join makes that honest.
    """
    per_sample = {}
    sets = []
    for adata in parts:
        names = [str(v) for v in adata.var_names]
        sets.append(set(names))
        per_sample[str(adata.obs["sample_id"].iloc[0]) if adata.n_obs else str(len(sets))] = len(names)
    union = set().union(*sets) if sets else set()
    shared = set.intersection(*sets) if sets else set()
    n_union, n_shared = len(union), len(shared)
    frac = (n_shared / n_union) if n_union else 1.0
    dropped = n_union - n_shared if join == "inner" else 0
    zero_filled = n_union - n_shared if join == "outer" else 0

    if n_shared == n_union:
        level = "ok"
        message = f"All {len(parts)} sample(s) carry the same {n_union} genes — nothing was dropped or filled."
        fix = ""
    elif join == "outer":
        level = "warn" if frac < _OVERLAP_WARN_BELOW else "info"
        message = (
            f"{zero_filled} of {n_union} genes are absent from at least one sample's reference and "
            f"were ZERO-FILLED by join='outer'. Those zeros are NOT measured counts — they are "
            f"indistinguishable from a measured zero downstream, and with sample mirrored to the "
            f"batch key they read as perfect sample-specific markers. Only {n_shared} genes "
            f"({frac:.1%}) are measured in every sample.")
        fix = ("Re-run Cell Ranger against ONE reference, or assemble with join='inner' (the "
               "default) so every count in the matrix is a measured count.")
    else:
        level = "warn" if frac < _OVERLAP_WARN_BELOW else "info"
        message = (
            f"{dropped} of {n_union} genes are not present in every sample's reference and were "
            f"DROPPED by join='inner'; {n_shared} genes ({frac:.1%}) are shared and kept. No count "
            f"was fabricated.")
        fix = ("Re-run Cell Ranger against ONE reference if the drop is large — the samples appear "
               "to use different references.")
    if level == "warn":
        fix = ("Samples appear to use DIFFERENT references. " + fix)
    return {
        "n_genes_union": n_union, "n_genes_shared": n_shared, "per_sample_n_genes": per_sample,
        "shared_fraction": round(frac, 4), "join": join,
        "dropped_genes": dropped, "zero_filled_genes": zero_filled,
        "level": level, "message": message, "fix": fix,
    }


def assemble_scrna(
    srcs: list[str | Path],
    obs_map: dict[str, dict] | None = None,
    join: str = "inner",
) -> Any:
    """Assemble a SET of **per-sample** scRNA matrices into ONE concatenated AnnData with the
    filename-encoded design materialized into ``obs``.

    ``srcs`` are the per-sample inputs in any mix of: a 10x Cell-Ranger triplet (loose
    ``…_matrix.mtx.gz`` + ``…_barcodes.tsv.gz`` + ``…_features.tsv.gz`` members, grouped by filename
    prefix), a 10x directory, or a per-sample ``.h5ad``. ``obs_map`` maps a sample key (see
    :func:`_match_obs_entry`) to the obs fields to stamp on that sample (``{"line": …,
    "condition": …}``) — the design source of truth, keyed by the same filename identity the grouping
    uses.

    Every cell gets ``obs['sample_id']`` (the sample's filename-derived key, or an ``obs_map``
    override); barcodes are namespaced ``{sample_id}_{barcode}`` so cells stay distinct and traceable
    across samples. ``obs['sample']`` is mirrored from ``sample_id`` when the design didn't set it, so
    the batch-key-reading scRNA skills (integration / QC / mixing) find a batch column out of the box.

    ``join`` is ``"inner"`` by default — the gene axis is the INTERSECTION, so every count in the
    assembled matrix is a measured count (A14). ``"outer"`` is opt-in and zero-fills the genes a
    sample's reference lacks; those zeros are fabricated and are disclosed as such. Either way the
    overlap is measured and stamped into ``uns['selom_gene_overlap']`` (see :func:`gene_overlap`),
    which :func:`summarize` surfaces — a large drop or fill is never silent.

    Raises ``ValueError`` for no inputs, an unknown ``join``, an unrecognized file, or an incomplete
    triplet."""
    import anndata as ad

    if not srcs:
        raise ValueError("assemble_scrna: no inputs")
    if join not in JOINS:
        raise ValueError(f"assemble_scrna: join must be one of {JOINS}, got {join!r}")

    units = _plan_units(srcs)
    parts = []
    for sample_key, kind, ref in units:
        adata = _read_unit(kind, ref)
        obs = _resolve_obs(sample_key, obs_map)
        sid = obs["sample_id"]
        for col, val in obs.items():
            adata.obs[col] = val
        # Namespace barcodes by sample so an identical Cell-Ranger barcode from two samples stays two
        # distinct cells (and its origin is legible), not silently merged.
        adata.obs_names = [f"{sid}_{bc}" for bc in adata.obs_names.astype(str)]
        parts.append(adata)

    # Measured BEFORE the concat — afterwards the two gene sets are gone and the verdict would be a
    # guess. ``fill_value`` is only passed for the outer join, so an inner assembly cannot fabricate.
    overlap = gene_overlap(parts, join)
    if len(parts) == 1:
        combined = parts[0]
    elif join == "outer":
        combined = ad.concat(parts, join="outer", fill_value=0)
    else:
        combined = ad.concat(parts, join="inner")
    combined.obs_names_make_unique()  # backstop — the sample prefix already makes them unique
    if "sample" not in combined.obs.columns:
        combined.obs["sample"] = combined.obs["sample_id"]  # reachability: the canonical batch key
    combined.uns["selom_gene_overlap"] = overlap  # travels with the .h5ad, read back by summarize()
    return combined


def summarize(adata: Any) -> dict:
    """A small JSON summary of an assembled AnnData for the endpoint header: cell/gene counts, the
    samples (first-seen order), the obs columns materialized, cells-per-sample, and the gene-overlap
    verdict.

    ``n_genes`` is the assembled matrix's actual gene count (post-join). The verdict block
    (``gene_overlap``, plus the flat ``n_genes_union`` / ``n_genes_shared`` / ``per_sample_n_genes``
    the finding names) says what the union was, what is shared, and what the join dropped or
    zero-filled — so a caller reading only this header can still tell whether a 0 in the matrix is a
    measured count (A14)."""
    obs = adata.obs
    sid = obs["sample_id"].astype(str)
    samples = list(dict.fromkeys(sid.tolist()))  # first-seen (= file) order
    out = {
        "n_cells": int(adata.n_obs),
        "n_genes": int(adata.n_vars),
        "n_samples": len(samples),
        "samples": samples,
        "obs_columns": [str(c) for c in obs.columns],
        "per_sample_n": {s: int((sid == s).sum()) for s in samples},
    }
    overlap = dict(adata.uns.get("selom_gene_overlap") or {}) if hasattr(adata, "uns") else {}
    if overlap:
        out["gene_overlap"] = overlap
        for k in ("n_genes_union", "n_genes_shared", "per_sample_n_genes"):
            out[k] = overlap[k]
    return out


def _prepare_for_write(adata: Any) -> Any:
    """Coerce ``obs``/``var`` to anndata-writable dtypes on a COPY of ``adata``.

    pandas-3 stores every string (the obs/var index, the design columns) as an arrow-backed
    ``StringArray`` (``future.infer_string`` is on by default), which anndata 0.12.6 has no h5ad
    writer for — ``write_h5ad`` raises ``No method registered for writing ArrowStringArray``. Rebuild
    each frame with an object-dtype index and object-dtype columns; the rebuild runs under
    ``future.infer_string=False`` so pandas doesn't silently re-infer the columns back to arrow
    strings. Numeric/bool columns keep their dtype. Downstream skills read obs via ``.astype(str)``,
    so object columns serve them identically."""
    import pandas as pd

    out = adata.copy()
    with pd.option_context("future.infer_string", False):
        for attr in ("obs", "var"):
            df = getattr(out, attr)
            rebuilt = pd.DataFrame(
                index=pd.Index([str(x) for x in df.index], dtype=object, name=df.index.name))
            for c in df.columns:
                s = df[c]
                if pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s):
                    rebuilt[c] = s.to_numpy()
                else:
                    rebuilt[c] = pd.Index([str(v) for v in s], dtype=object).to_numpy()
            setattr(out, attr, rebuilt)
    return out


def to_h5ad_bytes(adata: Any) -> bytes:
    """Serialize an assembled AnnData to ``.h5ad`` bytes (for the object store / a download response).

    Coerces to writable dtypes first (:func:`_prepare_for_write`, the pandas-3/anndata arrow-string
    quirk) and keeps ``allow_write_nullable_strings`` on for good measure."""
    import anndata as ad

    ad.settings.allow_write_nullable_strings = True
    d = Path(tempfile.mkdtemp(prefix="selom-assembled-"))
    try:
        out = d / "assembled_scrna.h5ad"
        _prepare_for_write(adata).write_h5ad(out)
        return out.read_bytes()
    finally:
        shutil.rmtree(d, ignore_errors=True)
