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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from engine.databundle import DataBundle, classify
from engine.models import GENERIC_TABLE, SourceRef


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


def _load_csv(path: Path, *, sep: str | None = None, **_: Any) -> Any:
    import pandas as pd

    if sep is None and path.suffix.lower() == ".tsv":
        sep = "\t"
    return pd.read_csv(path, sep=sep) if sep else pd.read_csv(path)


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
    for an unrecognized input type (an unloadable file is an honest error, distinct from an
    unknown *modality* of a loadable one, which is ``Kind.UNKNOWN``)."""
    path = Path(src)
    loader = _pick_loader(path)
    if loader is None:
        raise ValueError(
            f"no ingest loader for {path.name!r}; supported: .h5ad, 10x-mtx dir, .xlsx/.xls, .csv/.tsv"
        )
    payload = loader.load(path, sheet=sheet, sep=sep)
    source = _source_ref(path, sheet=sheet)  # provenance keys on the ORIGINAL file (the .iwxdata)
    # The runner handle (E4): a path-based skill runs from here. For a directly-readable file it IS
    # the source; for a decoded binary format (materialize) we write the decoded table to a temp CSV
    # so the CSV-reading skills run unchanged. `source` (provenance) still points at the original.
    run_path = str(path)
    if loader.materialize and _is_dataframe(payload):
        import tempfile

        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        tmp.close()
        payload.to_csv(tmp.name, index=False)
        run_path = tmp.name
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
