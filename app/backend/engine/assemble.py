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


def _is_10x_dir(p: Path) -> bool:
    # A directory-form 10x sample (mirrors engine.ingest._is_10x): the canonical triplet inside a dir.
    return p.is_dir() and any((p / f).exists() for f in ("matrix.mtx", "matrix.mtx.gz"))


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
    single AnnData file), or ``triplet`` (a ``{role: path}`` dict staged into a canonical dir for
    :func:`scanpy.read_10x_mtx`, which requires the fixed ``matrix.mtx``/``barcodes.tsv``/
    ``features.tsv`` names GEO's ``GSM…_`` prefix hides)."""
    import anndata as ad
    import scanpy as sc

    if kind == "dir":
        return sc.read_10x_mtx(ref)
    if kind == "h5ad":
        return ad.read_h5ad(ref)
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
        return sc.read_10x_mtx(staging)
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


def assemble_scrna(
    srcs: list[str | Path],
    obs_map: dict[str, dict] | None = None,
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
    Genes are unioned (``join='outer'``, absent genes → 0). Raises ``ValueError`` for no inputs, an
    unrecognized file, or an incomplete triplet."""
    import anndata as ad

    if not srcs:
        raise ValueError("assemble_scrna: no inputs")

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

    combined = parts[0] if len(parts) == 1 else ad.concat(parts, join="outer", fill_value=0)
    combined.obs_names_make_unique()  # backstop — the sample prefix already makes them unique
    if "sample" not in combined.obs.columns:
        combined.obs["sample"] = combined.obs["sample_id"]  # reachability: the canonical batch key
    return combined


def summarize(adata: Any) -> dict:
    """A small JSON summary of an assembled AnnData for the endpoint header: cell/gene counts, the
    samples (first-seen order), the obs columns materialized, and cells-per-sample."""
    obs = adata.obs
    sid = obs["sample_id"].astype(str)
    samples = list(dict.fromkeys(sid.tolist()))  # first-seen (= file) order
    return {
        "n_cells": int(adata.n_obs),
        "n_genes": int(adata.n_vars),
        "n_samples": len(samples),
        "samples": samples,
        "obs_columns": [str(c) for c in obs.columns],
        "per_sample_n": {s: int((sid == s).sum()) for s in samples},
    }


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
