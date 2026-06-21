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
from engine.models import SourceRef


@dataclass(frozen=True)
class _Loader:
    name: str
    recognize: Callable[[Path], bool]
    load: Callable[..., Any]


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


# --- recognizers ------------------------------------------------------------------------

def _is_h5ad(p: Path) -> bool:
    return p.suffix.lower() == ".h5ad"


def _is_10x(p: Path) -> bool:
    return p.is_dir() and any((p / f).exists() for f in ("matrix.mtx", "matrix.mtx.gz"))


def _is_xlsx(p: Path) -> bool:
    return p.suffix.lower() in (".xlsx", ".xls", ".xlsm")


def _is_csv(p: Path) -> bool:
    return p.suffix.lower() in (".csv", ".tsv", ".txt")


REGISTRY: tuple[_Loader, ...] = (
    _Loader("h5ad", _is_h5ad, _load_h5ad),
    _Loader("10x_mtx", _is_10x, _load_10x),
    _Loader("xlsx", _is_xlsx, _load_xlsx),
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
    source = _source_ref(path, sheet=sheet)
    return DataBundle(
        payload=payload,
        kind=classify(payload, hint=hint, source=source),
        source=source,
        path=str(path),  # the runner handle (E4): skills are still path-based, so the ANALYZE
    )                    # entry runs from here while the rest of the spine keys on the payload.
