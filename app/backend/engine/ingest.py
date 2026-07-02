"""Engine spine — the ingest registry (P1, E1, step 2).

:func:`ingest` reads any supported input into a **classified** :class:`~engine.databundle.DataBundle`.
A registry of one loader per input type (``recognize`` + ``load``); new input types are new
registry entries, never edits to callers. See ``docs/engine-spine/spec.md`` Sec 4.

This is the analysis front door (it loads the *full* payload). The cheap sheet inventory in
``extract.ingest`` (find ST2/ST6 by name without a full read) stays for routing — the two are
complementary, not duplicates.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from engine.databundle import DataBundle, classify
from engine.models import GENERIC_TABLE, QCReport, SourceRef


@dataclass(frozen=True)
class _Loader:
    name: str
    recognize: Callable[[Path], bool]
    load: Callable[..., Any]
    # A binary/proprietary format whose decoded payload a path-based skill can't re-read from the
    # original file (e.g. an .iwxdata ZIP). When True, ingest materializes the decoded DataFrame to
    # a temp CSV and points DataBundle.path at it, so the existing CSV-reading skills run unchanged.
    materialize: bool = False
    # An electrophysiology (ERG) format. ERG is not an omics ``Kind`` (engine.cleaning carries it as
    # a profile on top), so the materialized waveform table must NOT be force-classified into an
    # omics modality — a Diagnosys frame's NaN shape otherwise false-positives as proteomics. When
    # True, ingest classifies it as the neutral ``GENERIC_TABLE`` and records the format signal in
    # ``meta['erg_format']`` so :func:`engine.cleaning.profile_data` can claim ERG-certain-by-format
    # (a .csv/.txt Diagnosys export has no telltale suffix — the loader is the reliable signal).
    erg: bool = False


# --- loaders (each lazy-imports its dep so the registry stays cheap to import) -----------

def _load_h5ad(path: Path, **_: Any) -> Any:
    import anndata as ad

    return ad.read_h5ad(path)


def _load_10x(path: Path, **_: Any) -> Any:
    import scanpy as sc

    return sc.read_10x_mtx(path)


def _load_xlsx(path: Path, *, sheet: str | int | None = None, **_: Any) -> Any:
    import pandas as pd

    return pd.read_excel(path, sheet_name=0 if sheet is None else sheet)


# Encodings tried in order when reading a delimited text file. utf-8-sig transparently handles both
# BOM-less UTF-8 and a UTF-8 BOM (so a leading BOM never mangles the first column name); cp1252 is the
# common Windows/Excel export; latin-1 always decodes (every byte maps to a code point) so it is the
# guaranteed backstop — a real stranger's CSV never crashes on an odd encoding. First codec that
# decodes the whole file wins ([[layered-deterministic-extraction]]: content-first, honest fallback).
_CSV_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def _resolve_encoding(raw: bytes) -> str:
    for enc in _CSV_ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"  # unreachable (latin-1 decodes any byte) — explicit for the reader


def _sniff_delimiter(sample: str) -> str:
    """Best guess of a delimited-text separator among comma/tab/semicolon/pipe. Uses ``csv.Sniffer``,
    falling back to the candidate that splits the header into the most fields (default comma) — so a
    European semicolon export or a pipe-delimited file parses into columns, not one blob."""
    import csv

    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
    except csv.Error:  # no clear/uniform delimiter (e.g. a genuinely single-column file)
        header = next((ln for ln in sample.splitlines() if ln.strip()), "")
        counts = {d: header.count(d) for d in (",", "\t", ";", "|")}
        best = max(counts, key=counts.get)
        return best if counts[best] else ","


def _load_csv(path: Path, *, sep: str | None = None, **_: Any) -> Any:
    """Read a delimited text file (.csv/.tsv/.txt) robustly: sniff the encoding (UTF-8 ± BOM / cp1252 /
    latin-1) and — unless the caller pins ``sep`` or the suffix is ``.tsv`` — the delimiter, so a messy
    real export loads instead of crashing on a non-UTF-8 byte or collapsing to one column. An empty
    file is an honest ``ValueError``; a genuine parse failure propagates for :func:`ingest` to turn
    into a clear, actionable message (never a 500)."""
    import io

    import pandas as pd

    raw = path.read_bytes()
    if not raw.strip():
        raise ValueError(f"{path.name!r} is empty — no data to read.")
    enc = _resolve_encoding(raw)
    if sep is None:
        sep = ("\t" if path.suffix.lower() == ".tsv"
               else _sniff_delimiter(raw[:65536].decode(enc, errors="replace")))
    return pd.read_csv(io.BytesIO(raw), sep=sep, encoding=enc)


def _load_iwxdata(path: Path, **_: Any) -> Any:
    # Native iWorx/LabScribe ERG export → the canonical erg_waveforms_long DataFrame. The decoder
    # is pure-stdlib (skills._iwx); pandas is assembled inside read_iwxdata.
    from skills._iwx import read_iwxdata

    return read_iwxdata(str(path))


def _load_diagnosys(path: Path, **_: Any) -> Any:
    # Diagnosys Espion/Celeris export (.txt full multi-table / .csv reduced) → the canonical
    # erg_waveforms_long DataFrame (all modes, primary channel per eye). Pure-stdlib parse
    # (skills._celeris); pandas assembled inside read_celeris.
    from skills._celeris import read_celeris

    return read_celeris(str(path))


# --- recognizers ------------------------------------------------------------------------

def _is_h5ad(p: Path) -> bool:
    return p.suffix.lower() == ".h5ad"


def _is_10x(p: Path) -> bool:
    return p.is_dir() and any((p / f).exists() for f in ("matrix.mtx", "matrix.mtx.gz"))


def _is_xlsx(p: Path) -> bool:
    return p.suffix.lower() in (".xlsx", ".xls", ".xlsm")


def _is_csv(p: Path) -> bool:
    return p.suffix.lower() in (".csv", ".tsv", ".txt")


def _is_iwxdata(p: Path) -> bool:
    return p.suffix.lower() == ".iwxdata"


def _is_diagnosys(p: Path) -> bool:
    # A Diagnosys export wears a .csv/.txt/.tsv extension, so it must be detected by its
    # magic header (cheap — reads the first line) and recognized BEFORE the generic csv loader.
    if p.suffix.lower() not in (".csv", ".txt", ".tsv"):
        return False
    try:
        from skills._celeris import is_diagnosys_export

        return is_diagnosys_export(str(p))
    except Exception:  # noqa: BLE001 — recognition must never raise; fall through to csv
        return False


REGISTRY: tuple[_Loader, ...] = (
    _Loader("h5ad", _is_h5ad, _load_h5ad),
    _Loader("10x_mtx", _is_10x, _load_10x),
    _Loader("xlsx", _is_xlsx, _load_xlsx),
    _Loader("iwxdata", _is_iwxdata, _load_iwxdata, materialize=True, erg=True),
    _Loader("diagnosys_erg", _is_diagnosys, _load_diagnosys, materialize=True, erg=True),  # before csv
    _Loader("csv", _is_csv, _load_csv),
)


def _pick_loader(path: Path) -> _Loader | None:
    return next((ld for ld in REGISTRY if ld.recognize(path)), None)


def _load_failure_message(loader: _Loader, path: Path, exc: Exception) -> str:
    """Turn a loader's opaque parse exception into a clear, actionable reason for the user. A
    genuinely unloadable file (corrupt / wrong format / ragged rows) is an honest 400 — never a 500
    with a stack trace. Names the failure type without leaking the traceback."""
    name = path.name
    kind = type(exc).__name__
    by_loader = {
        "csv": (f"couldn't parse {name!r} as a table — check the delimiter, the header row, and that "
                f"every row has the same number of columns ({kind})."),
        "xlsx": (f"couldn't open {name!r} as an Excel file — it may be corrupt or not a real "
                 f".xlsx/.xls ({kind})."),
        "h5ad": f"couldn't open {name!r} as an AnnData/.h5ad file — it may be corrupt ({kind}).",
        "10x_mtx": f"couldn't read {name!r} as a 10x-mtx directory ({kind}).",
        "iwxdata": f"couldn't decode {name!r} as a native iWorx ERG export ({kind}).",
        "diagnosys_erg": f"couldn't decode {name!r} as a Diagnosys ERG export ({kind}).",
    }
    return by_loader.get(loader.name, f"couldn't read {name!r} ({kind}: {exc}).")


def _source_ref(path: Path, *, sheet: str | int | None = None) -> SourceRef:
    sr = SourceRef(filename=path.name, sheet=str(sheet) if sheet is not None else "")
    if path.is_file():
        h = hashlib.sha256()
        n = 0
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
                n += len(chunk)
        sr.n_bytes = n
        sr.sha256 = h.hexdigest()
    return sr


def ingest(
    src: str | Path,
    *,
    hint: str | None = None,
    sheet: str | int | None = None,
    sep: str | None = None,
) -> DataBundle:
    """Read ``src`` into a classified ``DataBundle``. ``hint`` forces the modality;
    ``sheet`` selects an xlsx sheet; ``sep`` overrides the CSV delimiter. Raises ``ValueError``
    for an unrecognized input type **and** for a recognized-but-unloadable file (a corrupt Excel,
    ragged CSV, undecodable bytes) — both are honest, actionable errors the caller turns into a 400,
    never a 500. An *unloadable file* is distinct from an unknown *modality* of a loadable one, which
    classifies to ``Kind.UNKNOWN`` and still ingests."""
    path = Path(src)
    loader = _pick_loader(path)
    if loader is None:
        raise ValueError(
            f"no ingest loader for {path.name!r}; supported: .h5ad, 10x-mtx dir, .xlsx/.xls, .csv/.tsv"
        )
    try:
        payload = loader.load(path, sheet=sheet, sep=sep)
    except ValueError:
        raise  # already an honest, actionable message (empty file, iWorx/Diagnosys decode, …)
    except Exception as exc:  # noqa: BLE001 — a parse failure is an honest 400 for the user, never a 500
        raise ValueError(_load_failure_message(loader, path, exc)) from exc
    source = _source_ref(path, sheet=sheet)  # provenance keys on the ORIGINAL file (the .iwxdata)
    # The runner handle (E4): a path-based skill runs from here. For a directly-readable file it IS
    # the source; for a decoded binary format (materialize) we write the decoded table to a temp CSV
    # so the CSV-reading skills run unchanged. `source` (provenance) still points at the original.
    run_path = str(path)
    if loader.materialize and _is_dataframe(payload):
        run_path = _materialize_csv(payload)  # content-addressed, managed temp (leak-free, acceptance D)
    # An ERG-format loader pins the modality to the neutral GENERIC_TABLE (ERG isn't an omics Kind)
    # and records the format signal for profile_data; a caller `hint` still wins.
    kind = classify(payload, hint=hint or (GENERIC_TABLE if loader.erg else None), source=source)
    return DataBundle(
        payload=payload,
        kind=kind,
        source=source,
        path=run_path,
        meta={"erg_format": loader.name} if loader.erg else {},
    )


def _is_dataframe(obj: Any) -> bool:
    return any(t.__name__ == "DataFrame" for t in type(obj).__mro__)


# --- materialized decode temps (Task C3 / materialization step 6, acceptance D) ----------------
# A path-based skill can't re-read a decoded binary format (.iwxdata ZIP) or a combined cohort frame
# from the original file, so :func:`ingest` writes the decoded DataFrame to a CSV and points
# ``DataBundle.path`` at it. Those temps used ``delete=False`` and were never cleaned — a
# per-invocation leak on Lambda's ephemeral disk (spec §4.2 / acceptance D). The fix is holistic, NOT
# a naive ``finally`` (the temp is referenced by ``bundle.path`` and REUSED across requests by the C3
# cache, so deleting it at the end of ``ingest`` would break the next cached run):
#
#   1. ONE process-managed dir, removed at interpreter exit — a hard backstop so nothing outlives the
#      process / a Lambda instance teardown.
#   2. CONTENT-ADDRESSED names (``{sha}.csv``) — re-decoding the same bytes REUSES the file instead of
#      writing a fresh one every invocation (this is what kills the cited per-invocation growth).
#   3. Eviction-tied deletion — when the C3 cache drops the entry that owns a temp, the temp is
#      deleted (unless another live entry shares the identical content), bounding disk in a warm,
#      long-lived process too.

_MATERIALIZED_DIR: Path | None = None
_MATERIALIZED_DIR_LOCK = threading.Lock()


def _materialized_dir() -> Path:
    global _MATERIALIZED_DIR
    if _MATERIALIZED_DIR is None:
        with _MATERIALIZED_DIR_LOCK:
            if _MATERIALIZED_DIR is None:
                import atexit
                import shutil
                import tempfile

                d = Path(tempfile.mkdtemp(prefix="selom-decoded-"))
                atexit.register(lambda: shutil.rmtree(d, ignore_errors=True))
                _MATERIALIZED_DIR = d
    return _MATERIALIZED_DIR


def _materialize_csv(df) -> str:
    """Write ``df`` to a CONTENT-ADDRESSED CSV in the managed dir, reusing it when those exact bytes
    already landed (a repeated decode doesn't multiply temps). Atomic write-then-replace (like
    ``LocalObjectStore.put_bytes``) so a concurrent reader never sees a torn file."""
    import os

    payload = df.to_csv(index=False).encode("utf-8")
    sha = hashlib.sha256(payload).hexdigest()
    target = _materialized_dir() / f"{sha}.csv"
    if not target.exists():
        tmp = target.with_name(f"{sha}.{os.getpid()}.tmp")
        tmp.write_bytes(payload)
        os.replace(tmp, target)
    return str(target)


def _is_managed_temp(path: str | None) -> bool:
    return bool(path) and _MATERIALIZED_DIR is not None and Path(path).parent == _MATERIALIZED_DIR


def _release_materialized(path: str | None) -> None:
    """Delete a managed materialized temp once NO remaining cache entry references it. Call under
    ``_INPUT_LOCK`` (after the owning entry has been popped)."""
    if not _is_managed_temp(path):
        return
    for bundle, materialized in _INPUT_CACHE.values():
        if materialized and bundle.path == path:
            return  # still owned by another live cache entry — keep it
    Path(path).unlink(missing_ok=True)


# --- parsed-input cache (Task C3) -------------------------------------------------------------
# An in-process memoization of :func:`ingest` keyed by the input content hash, so the same bytes
# aren't re-parsed across ``/data/inspect`` + ``/run`` (each endpoint uploads to its own temp path,
# but the bytes — hence the key — are identical). In-process only: the payload is a live
# AnnData/DataFrame that can't serialize to disk. On a hit the heavy payload + kind are *shared*
# (read-only — QC/profile read them; the skill run reads from ``path``, a file), while source/qc/path
# are rebound per request so one caller's metadata or file lifecycle can't corrupt the shared entry.

_INPUT_CACHE: "OrderedDict[tuple, tuple[DataBundle, bool]]" = OrderedDict()
_INPUT_LOCK = threading.Lock()


def _sha256_file(path: str | Path) -> str | None:
    p = Path(path)
    try:
        if not p.is_file():
            return None
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _rebind(entry: tuple[DataBundle, bool], src: str | Path) -> DataBundle:
    """A per-request view of a cached parse. The payload/kind/meta are shared; ``source`` is a fresh
    copy (the caller overwrites ``.filename``), ``qc`` is reset, and ``path`` is rebound: a
    *materialized* parse keeps its persistent decoded temp; a direct file is rebound to this upload."""
    bundle, materialized = entry
    path = bundle.path if materialized else str(Path(src))
    return replace(
        bundle,
        source=bundle.source.model_copy(deep=True),
        qc=QCReport(),
        meta=dict(bundle.meta),
        path=path,
    )


def ingest_cached(
    src: str | Path,
    *,
    hint: str | None = None,
    sheet: str | int | None = None,
    sep: str | None = None,
) -> DataBundle:
    """:func:`ingest`, memoized by ``(content sha256, hint, sheet, sep)`` (Task C3). A second call
    on the same bytes skips the re-parse; a different file / hint / sheet misses. Falls through to a
    plain :func:`ingest` when the cache is disabled or the input is unhashable."""
    from config import settings

    if not settings.input_cache_enabled:
        return ingest(src, hint=hint, sheet=sheet, sep=sep)
    sha = _sha256_file(src)
    key = (sha, hint, str(sheet), sep) if sha else None
    if key is not None:
        with _INPUT_LOCK:
            hit = _INPUT_CACHE.get(key)
            if hit is not None:
                _INPUT_CACHE.move_to_end(key)
                return _rebind(hit, src)
    bundle = ingest(src, hint=hint, sheet=sheet, sep=sep)  # already bound to this request
    if key is not None:
        materialized = bundle.path is not None and bundle.path != str(Path(src))
        with _INPUT_LOCK:
            _INPUT_CACHE[key] = (bundle, materialized)
            _INPUT_CACHE.move_to_end(key)
            while len(_INPUT_CACHE) > max(0, settings.input_cache_max):
                _evicted, (evicted_bundle, was_materialized) = _INPUT_CACHE.popitem(last=False)
                if was_materialized:
                    _release_materialized(evicted_bundle.path)  # free the decode temp it owned
    return bundle


def clear_input_cache() -> None:
    with _INPUT_LOCK:
        for bundle, materialized in _INPUT_CACHE.values():
            if materialized and _is_managed_temp(bundle.path):
                Path(bundle.path).unlink(missing_ok=True)
        _INPUT_CACHE.clear()


def _load_payload(path: Path, *, sheet: str | int | None = None, sep: str | None = None):
    """Load ``path`` to its in-memory payload via the registry WITHOUT the materialize-to-temp
    step ``ingest`` does — for callers (``ingest_many``) that assemble their own combined frame."""
    loader = _pick_loader(path)
    if loader is None:
        raise ValueError(f"no ingest loader for {path.name!r}")
    return loader.load(path, sheet=sheet, sep=sep), loader, _source_ref(path, sheet=sheet)


def ingest_many(
    srcs: list[str | Path],
    *,
    labels: list[str] | None = None,
    hint: str | None = None,
) -> DataBundle:
    """Combine several **single-condition** ERG (or any canonical-waveform) tables into ONE
    multi-condition :class:`DataBundle` — the C6 path (one ``.iwxdata`` / Diagnosys file = one
    eye/animal = one condition; a cohort needs them merged so the trace-mean + Fig-1E-with-reps run
    on a real n). Each file contributes its rows under a **condition label**, precedence:

    1. an explicit ``labels[i]`` (the user says "this file is condition X"),
    2. else the file's own non-empty ``condition`` column (kept per-row — e.g. the iWorx strain
       ``C57``/``Rd10``, so several files share one cohort label),
    3. else the filename stem.

    ``sample_id`` is namespaced with the file stem only **on cross-file collision**, so replicates
    stay distinct without uglifying already-unique ids. ``condition_order`` follows first-seen order
    (= the order the files are given → deterministic column order in the grid). A ``source_file``
    column is added for provenance. The combined frame is classified + materialized to a temp CSV,
    so the existing path-based ERG skills run on it unchanged."""
    import pandas as pd

    paths = [Path(s) for s in srcs]
    if not paths:
        raise ValueError("ingest_many: no inputs")
    labels = list(labels or [])

    frames: list = []
    seen_ids: dict[str, set[str]] = {}  # sample_id -> set of file stems that used it
    for i, p in enumerate(paths):
        payload, _loader, source = _load_payload(p)
        if not _is_dataframe(payload):
            raise ValueError(f"ingest_many: {p.name!r} did not load as a table")
        df = payload.copy()
        stem = p.stem
        explicit = labels[i].strip() if i < len(labels) and labels[i] and labels[i].strip() else None
        has_cond = ("condition" in df.columns
                    and df["condition"].astype(str).str.strip().replace("nan", "").ne("").any())
        if explicit:
            df["condition"] = explicit
        elif not has_cond:
            df["condition"] = stem
        df["source_file"] = source.filename
        if "sample_id" in df.columns:
            for sid in df["sample_id"].dropna().astype(str).unique():
                seen_ids.setdefault(sid, set()).add(stem)
        frames.append((df, stem))

    collide = {sid for sid, stems in seen_ids.items() if len(stems) > 1}
    out: list = []
    for df, stem in frames:
        if collide and "sample_id" in df.columns:
            df["sample_id"] = df["sample_id"].astype(str).map(
                lambda s, stem=stem: f"{stem}::{s}" if s in collide else s)
        out.append(df)
    combined = pd.concat(out, ignore_index=True, sort=False)

    # Deterministic condition_order = first-seen order across the merged frame (= file order).
    order_map: dict[str, int] = {}
    for c in combined["condition"].astype(str):
        order_map.setdefault(c, len(order_map))
    combined["condition_order"] = combined["condition"].astype(str).map(order_map)

    run_path = _materialize_csv(combined)  # content-addressed, managed temp (leak-free, acceptance D)
    source = SourceRef(filename=f"combined_{len(paths)}_files.csv", n_bytes=0, sha256="")
    kind = classify(combined, hint=hint or GENERIC_TABLE, source=source)
    return DataBundle(
        payload=combined,
        kind=kind,
        source=source,
        path=run_path,
        meta={"erg_format": "combined", "n_files": len(paths),
              "conditions": list(order_map.keys())},
    )
