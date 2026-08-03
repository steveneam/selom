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
(`skills/_result_cache.py`). The artifact bytes now ride the shared **ObjectStore** seam
(`storage/object_store.py`, keys ``artifacts/{id}.csv`` + ``artifacts/{id}.meta.json``): the
backend swaps from local disk to S3 by config, behind this same interface — this is the named D4
(materialization step 4, docs/aws-materialization/spec.md §1.2). A single-cell **matrix** payload
(AnnData) is recorded **meta-only** (shape + lineage, no multi-GB CSV) — honest and bounded. See
``docs/architecture-consistency-gate/intermediate-table-lineage.md``.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import re
import threading
from typing import Any

from pydantic import BaseModel, Field, computed_field

from engine.databundle import _is_anndata, _is_dataframe
from storage.object_store import LocalObjectStore, get_object_store

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


def _owner_seg(owner: str) -> str:
    """The tenant's object-store path segment — the artifact analogue of ``WHERE user_id = ?``.

    The tenant id is always a verified claim (``auth/context.py``), never user input, so this is
    defence in depth rather than the primary control. But an object-store key is a PATH: a ``sub``
    claim containing ``/`` or ``..`` from a future identity provider would let one tenant's prefix
    address another's. Hash anything that is not a plain identifier rather than trusting the shape,
    and refuse an empty owner outright — a blank segment would collapse every tenant back onto the
    one shared prefix this exists to eliminate.
    """
    owner = str(owner or "").strip()
    if not owner:
        raise ValueError("lineage: an artifact must have an owner (the verified tenant)")
    # `.` and `..` fullmatch the safe pattern (dots are legal INSIDE an id) but are the two path
    # segments that must never survive verbatim — caught by a test, not by reading the regex.
    if _SAFE_OWNER.fullmatch(owner) and owner.strip(".") != "":
        return owner
    return "h_" + _hash_bytes(owner.encode("utf-8"))[:32]


_SAFE_OWNER = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


def source_parent(path: Any, filename: str = "") -> ParentRef:
    """A ``ParentRef`` for an input file: its content SHA + friendly name."""
    name = filename or (pathlib.Path(str(path)).name if path else "")
    return ParentRef(kind="source", id=file_sha256(path), label=name)


# --- the store -------------------------------------------------------------------------------


class ArtifactStore:
    """Content-addressed store on the shared ObjectStore seam: ``artifacts/<id>.csv`` (the table) +
    ``artifacts/<id>.meta.json`` (the lineage). Immutable — a content hash that already exists is
    never rewritten, so a re-materialize is a cheap idempotent no-op (the reproducibility guarantee).
    A small in-process meta cache fronts the seam; the backend swaps from local disk to S3 by config
    (D4) behind this interface — no caller changes."""

    def __init__(self, root: Any = None, enabled: bool = True, object_store=None) -> None:
        # ``root`` (a local dir) keeps the test/explicit-local construction working — it becomes a
        # root-scoped ``LocalObjectStore``. With no root and no injected store, the bytes ride the
        # shared object store (data_dir-local in dev, S3 in prod) selected by config.
        self.root = pathlib.Path(root) if root is not None else None
        self.enabled = enabled
        self._obj = object_store
        self._meta_mem: dict[tuple[str, str], ArtifactMeta] = {}
        self._lock = threading.Lock()

    def _store(self):
        """The backend: an injected store, else a root-scoped local store, else the shared process
        object store (resolved live so a test ``set_object_store`` is honoured)."""
        if self._obj is not None:
            return self._obj
        if self.root is not None:
            return LocalObjectStore(self.root)
        return get_object_store()

    def _table_key(self, aid: str, owner: str) -> str:
        return f"artifacts/{_owner_seg(owner)}/{aid}.csv"

    def _meta_key(self, aid: str, owner: str) -> str:
        return f"artifacts/{_owner_seg(owner)}/{aid}.meta.json"

    def put(self, aid: str, meta: ArtifactMeta, csv_bytes: bytes | None, *, owner: str) -> None:
        """Write the table (if any) + its meta under the OWNER's prefix, immutably.

        Immutability is per tenant, which is the point: the id is a content hash, so two tenants
        who upload the same table derive the same id. Sharing one key would make the second
        tenant's read a cross-tenant read of the first tenant's bytes. Each tenant gets its own
        copy — cross-tenant dedup IS the leak."""
        if not self.enabled:
            return
        try:
            obj = self._store()
            if csv_bytes is not None and not obj.head(self._table_key(aid, owner)):
                obj.put_bytes(self._table_key(aid, owner), csv_bytes, "text/csv")
            if not obj.head(self._meta_key(aid, owner)):
                obj.put_bytes(self._meta_key(aid, owner), meta.model_dump_json().encode("utf-8"),
                              "application/json")
            with self._lock:
                self._meta_mem.setdefault((owner, aid), meta)
        except (OSError, ValueError, TypeError):
            pass  # materialization is best-effort — never break a run over a lineage write

    def get_table(self, aid: str, *, owner: str) -> bytes | None:
        try:
            return self._store().get_bytes(self._table_key(aid, owner))
        except OSError:
            return None

    def get_meta(self, aid: str, *, owner: str) -> ArtifactMeta | None:
        with self._lock:
            cached = self._meta_mem.get((owner, aid))
        if cached is not None:
            return cached
        try:
            raw = self._store().get_bytes(self._meta_key(aid, owner))
            if raw is not None:
                meta = ArtifactMeta.model_validate_json(raw)
                with self._lock:
                    self._meta_mem[(owner, aid)] = meta
                return meta
        except (OSError, ValueError):
            pass
        return None

    def clear(self) -> None:
        """Drop the in-proc meta cache and remove the durable tier (test / hygiene). Only a
        root-scoped local store is enumerable (the ObjectStore Protocol has no list); a shared/
        S3-backed store no-ops here."""
        with self._lock:
            self._meta_mem.clear()
        if self.root is None or self._obj is not None:
            return
        try:
            for p in self.root.glob("**/*"):  # bytes now nest under artifacts/
                if p.is_file():
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

                # No root: the bytes ride the shared object store, keyed artifacts/{id} (local
                # under data_dir/artifacts/ in dev — the same path as before — or S3 in prod).
                _default = ArtifactStore(enabled=settings.artifacts_enabled)
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


def materialize(payload: Any, *, owner: str, kind: str, filename: str = "",
                parents: list[ParentRef] | None = None,
                recipe: Any = None, recipe_note: str = "", note: str = "") -> ArtifactMeta | None:
    """Materialize a stage's table as a content-addressed artifact → its :class:`ArtifactMeta`.

    A DataFrame is written as ``<id>.csv``; an AnnData matrix is recorded **meta-only** (shape +
    lineage, no CSV). Returns ``None`` when the store is disabled or the payload is neither. Immutable
    and idempotent — a re-materialize of the same bytes returns the existing record (reproducible).
    """
    # Validate the owner HERE, before the fail-soft layers below can swallow it. `put` and
    # `get_meta` deliberately absorb ValueError so a lineage write never breaks a run — which would
    # turn a missing tenant into a silent no-op write instead of a loud error. Caught by a test.
    _owner_seg(owner)
    store = get_store()
    if not store.enabled:
        return None
    parents = parents or []
    steps = _recipe_steps(recipe)

    if _is_dataframe(payload):
        csv = _df_csv_bytes(payload)
        aid = _hash_bytes(csv)
        existing = store.get_meta(aid, owner=owner)
        if existing is not None:
            return existing  # already materialized — immutable, reproducible
        meta = ArtifactMeta(
            artifact_id=aid, kind=kind, filename=filename, materialized=True,
            n_rows=int(len(payload)), n_cols=int(payload.shape[1]),
            columns=[str(c) for c in payload.columns][:200],
            parents=parents, recipe=steps, recipe_note=recipe_note, note=note, created_at=_now())
        store.put(aid, meta, csv, owner=owner)
        return meta

    if _is_anndata(payload):
        n_obs, n_var = int(payload.n_obs), int(payload.n_vars)
        descriptor = json.dumps({"kind": KIND_MATRIX, "filename": filename, "n_obs": n_obs,
                                 "n_var": n_var, "parents": [p.id for p in parents]}, sort_keys=True)
        aid = _hash_bytes(descriptor.encode("utf-8"))
        existing = store.get_meta(aid, owner=owner)
        if existing is not None:
            return existing
        meta = ArtifactMeta(
            artifact_id=aid, kind=KIND_MATRIX, filename=filename, materialized=False,
            n_rows=n_obs, n_cols=n_var, parents=parents, recipe=steps, recipe_note=recipe_note,
            note=note or f"single-cell matrix — not materialized as a table ({n_obs} cells × {n_var} genes)",
            created_at=_now())
        store.put(aid, meta, None, owner=owner)
        return meta

    return None


def materialize_bundle(bundle: Any, *, owner: str, parents: list[ParentRef] | None = None,
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
        return materialize(bundle.payload, owner=owner, kind=kind, filename=filename,
                           parents=parents, recipe=recipe, recipe_note=recipe_note)
    except Exception:  # noqa: BLE001 — best-effort lineage; never raise into the run path
        return None


def get_table(artifact_id: str, *, owner: str) -> bytes | None:
    """The materialized table bytes (CSV) for ``artifact_id`` — "inspect the matrix the skill saw".

    ``owner`` is required and unguessable-by-the-caller (it comes from the verified claim), so an
    id alone is not enough to read an artifact. An id is an identifier, not an authorization."""
    return get_store().get_table(artifact_id, owner=owner)


def get_meta(artifact_id: str, *, owner: str) -> ArtifactMeta | None:
    return get_store().get_meta(artifact_id, owner=owner)


def lineage(artifact_id: str, *, owner: str) -> list[ArtifactMeta]:
    """The artifact + its ancestor artifacts (walking ``artifact``-kind parents). Source-file parents
    are leaves (no meta of their own). Forward-compatible with artifact→artifact cleaning chains.

    The whole walk stays inside ``owner``'s prefix: an ancestor id that belongs to another tenant
    simply resolves to no meta and drops out, so lineage can never become a read-through to another
    tenant's records via a crafted parent edge."""
    out: list[ArtifactMeta] = []
    seen: set[str] = set()
    stack = [artifact_id]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        meta = get_meta(cur, owner=owner)
        if meta is None:
            continue
        out.append(meta)
        for p in meta.parents:
            if p.kind == "artifact" and p.id:
                stack.append(p.id)
    return out
