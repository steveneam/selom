"""Engine spine — content-addressed intermediate-table lineage (D3).

The owner's "always a table; intermediate tables" — made inspectable and reproducible. Every table
that flows between stages (the ingested matrix a skill consumes, a combined cohort table) can be
**materialized** as a content-addressed artifact: the table bytes are written under their own SHA-256
(`<id>.csv`) beside a metadata sidecar (`<id>.meta.json`) that records the **lineage** — the parent
artifact(s) / source file(s) it derived from, the **cleaning recipe** that produced it, and (for a
combine) the **merge receipt** "merged from {A, B, C}".

Three things this buys, the D3 acceptance:

* **"inspect the matrix the skill actually saw"** — the run stamps an ``artifact_id``; ``GET
  /artifacts/{id}/table`` returns exactly the table the runner consumed.
* **a cleaned re-run is reproducible** — the id IS the content hash, so the same input through the
  same recipe yields the *same* artifact (idempotent: a re-materialize finds the existing immutable
  record, it never rewrites or forks).
* **combine records its provenance** — a merged table's meta carries each source file as a parent
  and renders "merged from {A, B, C}".

Content-addressed, immutable, dependency-free — the same discipline as the C1 result cache
(`skills/_result_cache.py`), and the **local precursor to D4** (the deferred DuckDB/Parquet lane):
the local-dir backend swaps for an object store behind this same interface, exactly as C1's disk
tier swaps for R2. A single-cell **matrix** payload (AnnData) is recorded **meta-only** (shape +
lineage, no multi-GB CSV) — honest and bounded. See
``docs/architecture-consistency-gate/intermediate-table-lineage.md``.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import threading
from typing import Any

from pydantic import BaseModel, Field, computed_field

from engine.databundle import _is_anndata, _is_dataframe

# Artifact kinds (the stage that produced the table).
KIND_INGESTED = "ingested"    # the table a skill consumed, straight from ingest (parent = source file)
KIND_COMBINED = "combined"    # a multi-file merge (parents = the inputs) — the /data/combine receipt
KIND_CLEANED = "cleaned"      # an applied cleaning/normalization (future — cleaning is advisory today)
KIND_MATRIX = "matrix"        # a single-cell matrix recorded meta-only (not materialized as a table)


class ParentRef(BaseModel):
    """One lineage edge: a source file (by its content SHA) or a prior artifact (by its id)."""

    kind: str = "source"   # source | artifact
    id: str = ""           # sha256 of a source file, or a parent artifact_id
    label: str = ""        # the friendly filename (what the receipt shows)


class RecipeStep(BaseModel):
    """One step of the recipe that produced this table (the cleaning plan step, or a merge op)."""

    id: str = ""
    label: str = ""
    detail: str = ""


class ArtifactMeta(BaseModel):
    """The lineage sidecar for one materialized intermediate table — the wire shape the API returns.

    ``artifact_id`` is the content hash (the table bytes, or a matrix's shape descriptor). ``parents``
    + ``recipe`` + ``recipe_note`` are the provenance; ``receipt`` renders the human "merged from …".
    """

    artifact_id: str
    kind: str = KIND_INGESTED
    filename: str = ""
    materialized: bool = True      # False for a meta-only matrix record (no table bytes on disk)
    n_rows: int = 0
    n_cols: int = 0
    columns: list[str] = Field(default_factory=list)
    parents: list[ParentRef] = Field(default_factory=list)
    recipe: list[RecipeStep] = Field(default_factory=list)
    recipe_note: str = ""
    note: str = ""
    created_at: str = ""

    @computed_field
    @property
    def receipt(self) -> str:
        """The human provenance line: "merged from {A, B, C}" for a combine, else "derived from X"."""
        if not self.parents:
            return ""
        names = [p.label or (p.id[:8] if p.id else "?") for p in self.parents]
        if self.kind == KIND_COMBINED or len(names) > 1:
            return "merged from {" + ", ".join(names) + "}"
        return f"derived from {names[0]}"


# --- hashing ---------------------------------------------------------------------------------


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _hash_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _df_csv_bytes(df: Any) -> bytes:
    """Deterministic CSV serialization of a table (stable column order + no index) — the bytes that
    are both the materialized artifact AND its content hash, so the same table always self-identifies."""
    return df.to_csv(index=False).encode("utf-8")


def file_sha256(path: Any) -> str:
    """Content SHA of a source file (empty when missing/unreadable) — for a source ``ParentRef``."""
    try:
        p = pathlib.Path(path)
        if not p.is_file():
            return ""
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def source_parent(path: Any, filename: str = "") -> ParentRef:
    """A ``ParentRef`` for an input file: its content SHA + friendly name."""
    name = filename or (pathlib.Path(str(path)).name if path else "")
    return ParentRef(kind="source", id=file_sha256(path), label=name)


# --- the store -------------------------------------------------------------------------------


class ArtifactStore:
    """Content-addressed local store: ``<id>.csv`` (the table) + ``<id>.meta.json`` (the lineage),
    under ``data/artifacts/``. Immutable — a content hash that already exists is never rewritten, so a
    re-materialize is a cheap idempotent no-op (the reproducibility guarantee). Disk-backed with a
    small in-process meta cache; the D4 object-store tier swaps the backend behind this interface."""

    def __init__(self, root: Any, enabled: bool = True) -> None:
        self.root = pathlib.Path(root)
        self.enabled = enabled
        self._meta_mem: dict[str, ArtifactMeta] = {}
        self._lock = threading.Lock()

    def _table_path(self, aid: str) -> pathlib.Path:
        return self.root / f"{aid}.csv"

    def _meta_path(self, aid: str) -> pathlib.Path:
        return self.root / f"{aid}.meta.json"

    def _atomic_write(self, target: pathlib.Path, write) -> None:
        tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
        write(tmp)
        os.replace(tmp, target)  # atomic — no torn reads across workers

    def put(self, aid: str, meta: ArtifactMeta, csv_bytes: bytes | None) -> None:
        """Write the table (if any) + its meta, immutably (skip if the id already exists)."""
        if not self.enabled:
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            if csv_bytes is not None and not self._table_path(aid).is_file():
                self._atomic_write(self._table_path(aid), lambda t: t.write_bytes(csv_bytes))
            if not self._meta_path(aid).is_file():
                self._atomic_write(self._meta_path(aid),
                                   lambda t: t.write_text(meta.model_dump_json(), encoding="utf-8"))
            with self._lock:
                self._meta_mem.setdefault(aid, meta)
        except (OSError, ValueError, TypeError):
            pass  # materialization is best-effort — never break a run over a lineage write

    def get_table(self, aid: str) -> bytes | None:
        try:
            p = self._table_path(aid)
            return p.read_bytes() if p.is_file() else None
        except OSError:
            return None

    def get_meta(self, aid: str) -> ArtifactMeta | None:
        with self._lock:
            cached = self._meta_mem.get(aid)
        if cached is not None:
            return cached
        try:
            p = self._meta_path(aid)
            if p.is_file():
                meta = ArtifactMeta.model_validate_json(p.read_text(encoding="utf-8"))
                with self._lock:
                    self._meta_mem[aid] = meta
                return meta
        except (OSError, ValueError):
            pass
        return None

    def clear(self) -> None:
        with self._lock:
            self._meta_mem.clear()
        try:
            for pat in ("*.csv", "*.meta.json", "*.tmp"):
                for p in self.root.glob(pat):
                    p.unlink(missing_ok=True)
        except OSError:
            pass


# --- process-default instance (lazily built from config) -------------------------------------

_default: ArtifactStore | None = None
_default_lock = threading.Lock()


def get_store() -> ArtifactStore:
    global _default
    if _default is None:
        with _default_lock:
            if _default is None:
                from config import settings

                _default = ArtifactStore(root=settings.data_dir / "artifacts",
                                         enabled=settings.artifacts_enabled)
    return _default


def set_store(store: ArtifactStore | None) -> None:
    """Swap the process-default store (test seam)."""
    global _default
    _default = store


# --- materialize / inspect -------------------------------------------------------------------


def _recipe_steps(recipe: Any) -> list[RecipeStep]:
    """Coerce a cleaning plan's steps (or a list of dicts) into ``RecipeStep``s."""
    out: list[RecipeStep] = []
    for s in recipe or []:
        d = s.model_dump() if hasattr(s, "model_dump") else dict(s)
        out.append(RecipeStep(id=str(d.get("id", "")), label=str(d.get("label", "")),
                              detail=str(d.get("detail", ""))))
    return out


def materialize(payload: Any, *, kind: str, filename: str = "", parents: list[ParentRef] | None = None,
                recipe: Any = None, recipe_note: str = "", note: str = "") -> ArtifactMeta | None:
    """Materialize a stage's table as a content-addressed artifact → its :class:`ArtifactMeta`.

    A DataFrame is written as ``<id>.csv``; an AnnData matrix is recorded **meta-only** (shape +
    lineage, no CSV). Returns ``None`` when the store is disabled or the payload is neither. Immutable
    and idempotent — a re-materialize of the same bytes returns the existing record (reproducible).
    """
    store = get_store()
    if not store.enabled:
        return None
    parents = parents or []
    steps = _recipe_steps(recipe)

    if _is_dataframe(payload):
        csv = _df_csv_bytes(payload)
        aid = _hash_bytes(csv)
        existing = store.get_meta(aid)
        if existing is not None:
            return existing  # already materialized — immutable, reproducible
        meta = ArtifactMeta(
            artifact_id=aid, kind=kind, filename=filename, materialized=True,
            n_rows=int(len(payload)), n_cols=int(payload.shape[1]),
            columns=[str(c) for c in payload.columns][:200],
            parents=parents, recipe=steps, recipe_note=recipe_note, note=note, created_at=_now())
        store.put(aid, meta, csv)
        return meta

    if _is_anndata(payload):
        n_obs, n_var = int(payload.n_obs), int(payload.n_vars)
        descriptor = json.dumps({"kind": KIND_MATRIX, "filename": filename, "n_obs": n_obs,
                                 "n_var": n_var, "parents": [p.id for p in parents]}, sort_keys=True)
        aid = _hash_bytes(descriptor.encode("utf-8"))
        existing = store.get_meta(aid)
        if existing is not None:
            return existing
        meta = ArtifactMeta(
            artifact_id=aid, kind=KIND_MATRIX, filename=filename, materialized=False,
            n_rows=n_obs, n_cols=n_var, parents=parents, recipe=steps, recipe_note=recipe_note,
            note=note or f"single-cell matrix — not materialized as a table ({n_obs} cells × {n_var} genes)",
            created_at=_now())
        store.put(aid, meta, None)
        return meta

    return None


def materialize_bundle(bundle: Any, *, parents: list[ParentRef] | None = None,
                       recipe: Any = None, recipe_note: str = "") -> ArtifactMeta | None:
    """Materialize an ingested ``DataBundle``'s payload — the table the skill consumed. ``kind`` is
    derived (a combined bundle vs a plain ingest); ``parents`` defaults to the bundle's source file.
    Fail-soft: any error returns ``None`` (a lineage record must never break a run)."""
    try:
        meta_in = getattr(bundle, "meta", None) or {}
        kind = KIND_COMBINED if meta_in.get("erg_format") == "combined" else KIND_INGESTED
        src = getattr(bundle, "source", None)
        filename = getattr(src, "filename", "") if src else ""
        if parents is None:
            path = getattr(bundle, "path", None)
            sha = getattr(src, "sha256", "") if src else ""
            parents = [ParentRef(kind="source", id=sha or file_sha256(path), label=filename)]
        return materialize(bundle.payload, kind=kind, filename=filename, parents=parents,
                           recipe=recipe, recipe_note=recipe_note)
    except Exception:  # noqa: BLE001 — best-effort lineage; never raise into the run path
        return None


def get_table(artifact_id: str) -> bytes | None:
    """The materialized table bytes (CSV) for ``artifact_id`` — "inspect the matrix the skill saw"."""
    return get_store().get_table(artifact_id)


def get_meta(artifact_id: str) -> ArtifactMeta | None:
    return get_store().get_meta(artifact_id)


def lineage(artifact_id: str) -> list[ArtifactMeta]:
    """The artifact + its ancestor artifacts (walking ``artifact``-kind parents). Source-file parents
    are leaves (no meta of their own). Forward-compatible with artifact→artifact cleaning chains."""
    out: list[ArtifactMeta] = []
    seen: set[str] = set()
    stack = [artifact_id]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        meta = get_meta(cur)
        if meta is None:
            continue
        out.append(meta)
        for p in meta.parents:
            if p.kind == "artifact" and p.id:
                stack.append(p.id)
    return out
