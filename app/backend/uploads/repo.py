"""Tenant data access for the presigned-upload flow (materialization step 6).

A SQLAlchemy-portable repository over ``projects`` + ``datasets`` (spec §2.3), mirroring
``SqlJobStore``: each method opens its own short transaction, sets the RLS tenant, and goes through
``TenantQuery`` so a forgotten ``user_id`` filter is structurally impossible (spec §6.1). Built on
the same local-dev/AWS-prod seam — SQLite for the inner loop, Aurora Postgres in prod, one URL.

The tenant is ALWAYS the verified claim passed in by the handler (``ctx.user_id``), never a request
param (spec §6.2). Quota is enforced on the write path (spec §12): ``create_project`` checks
``max_projects``; ``intake`` checks ``max_datasets`` + ``max_storage_bytes`` *before* a presigned URL
is issued, so a tenant can't exceed its plan by uploading straight to S3.

Reconciliation primitives for T2 (spec §7) live here too (``heal_from_key`` / ``list_stale_pending``
/ ``list_active_upload_keys`` / ``delete_dataset``); the service layer (``uploads/service.py``)
orchestrates them with the object store. The cross-tenant sweep queries are NOT tenant-scoped (a
system job) — on Postgres they need a BYPASSRLS role, resolved at the deploy step; on SQLite they run
as-is (no RLS).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from db.engine import ensure_schema, make_engine
from db.retry import run_with_db_retry
from db.schema import datasets, projects, users, workspaces
from db.tenant import TenantQuery, set_tenant, upsert_user
from uploads.keys import upload_key

# Dataset lifecycle (datasets.status) — spec §4.2/§7.
PENDING = "pending_upload"
READY = "ready"
FAILED = "failed"


class QuotaExceeded(Exception):
    """A tenant write would exceed its plan limit (spec §12). Carries which limit + the numbers."""

    def __init__(self, limit: str, used, allowed, message: str) -> None:
        super().__init__(message)
        self.limit = limit
        self.used = used
        self.allowed = allowed
        self.message = message

    def to_dict(self) -> dict:
        return {"error": "quota_exceeded", "limit": self.limit, "used": self.used,
                "allowed": self.allowed, "message": self.message}


def _project_public(row) -> dict:
    return {"id": row.id, "name": row.name, "color": row.color,
            "workspace_id": row.workspace_id, "created_at": _iso(row.created_at)}


def _dataset_public(row) -> dict:
    return {
        "id": row.id, "project_id": row.project_id, "filename": row.filename,
        "label": row.label, "modality": row.modality, "status": row.status,
        "size_bytes": int(row.size_bytes or 0), "current_sha256": row.current_sha256,
        "upload_s3_key": row.upload_s3_key, "parquet_s3_key": row.parquet_s3_key,
        "qc": row.qc, "source": row.source, "created_at": _iso(row.created_at),
    }


def _iso(dt) -> str | None:
    return dt.isoformat() if isinstance(dt, datetime) else dt


class UploadRepo:
    """Projects + datasets data access (SQLite dev/test, Postgres prod) behind ``TenantQuery``."""

    def __init__(self, engine: sa.Engine | None = None, url: str = "", create: bool = False) -> None:
        self.engine = engine if engine is not None else make_engine(url)
        if create:  # dev/test convenience (SQLite); prod applies the Alembic migration instead
            ensure_schema(self.engine)

    # --- quota helpers (tenant-scoped reads) --------------------------------------------------
    def _quota(self, conn: sa.Connection, user_id: str) -> sa.Row:
        return conn.execute(sa.select(users).where(users.c.user_id == user_id)).first()

    def _count(self, conn: sa.Connection, table: sa.Table, user_id: str) -> int:
        return int(conn.execute(
            sa.select(sa.func.count()).select_from(table).where(table.c.user_id == user_id)
        ).scalar_one())

    def _storage_used(self, conn: sa.Connection, user_id: str) -> int:
        # Reserved bytes = the declared size of every non-failed dataset (pending reserves quota too,
        # so a flood of intakes can't blow past the plan; a swept stale pending frees it again).
        total = conn.execute(
            sa.select(sa.func.coalesce(sa.func.sum(datasets.c.size_bytes), 0))
            .where(datasets.c.user_id == user_id, datasets.c.status != FAILED)
        ).scalar_one()
        return int(total or 0)

    # --- projects -----------------------------------------------------------------------------
    def create_project(self, user_id: str, email: str | None, name: str,
                       color: str = "blue", project_id: str | None = None) -> dict:
        # ``project_id`` is the FE's client-authoritative id (sub-spec §2.2): the optimistic store
        # mints it, routes to it synchronously, then POSTs it here. Idempotent on (tenant, id) so a
        # retried optimistic write / import returns the existing row, never a duplicate. Omit it →
        # the server mints one (the step-6 default, unchanged).
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                upsert_user(conn, user_id, email or f"{user_id}@unknown.local")
                tq = TenantQuery(conn, user_id)
                if project_id is not None:
                    existing = tq.get(projects, project_id)
                    if existing is not None:
                        return _project_public(existing)  # idempotent re-POST
                q = self._quota(conn, user_id)
                used = self._count(conn, projects, user_id)
                if q is not None and used >= q.max_projects:
                    raise QuotaExceeded("max_projects", used, int(q.max_projects),
                                        f"Project limit reached ({q.max_projects}).")
                ws_id = self._ensure_workspace(conn, tq, user_id)
                values = {"name": name, "color": color or "blue", "workspace_id": ws_id}
                if project_id is not None:
                    values["id"] = project_id
                pid = tq.insert(projects, **values)
                return _project_public(tq.get(projects, pid))
        return run_with_db_retry(_work)

    def list_projects(self, user_id: str) -> list[dict]:
        def _work():
            with self.engine.connect() as conn:
                set_tenant(conn, user_id)
                rows = TenantQuery(conn, user_id).select(projects)
                return [_project_public(r) for r in rows]
        return run_with_db_retry(_work)

    def update_project(self, user_id: str, project_id: str, **changes) -> dict | None:
        """Rename / recolor a project (FE ``renameProject``). ``None`` ⇒ not this tenant's project."""
        patch = {k: v for k, v in changes.items() if k in ("name", "color") and v is not None}

        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                if tq.get(projects, project_id) is None:
                    return None
                if patch:
                    tq.update(projects, project_id, **patch)
                return _project_public(tq.get(projects, project_id))
        return run_with_db_retry(_work)

    def delete_project(self, user_id: str, project_id: str) -> int:
        """Delete a project and its children (FE ``deleteProject``). On Postgres the FKs cascade;
        SQLite doesn't enforce FKs, so delete the project-scoped children explicitly to avoid orphans
        on the dev path. Workspace-scoped assets (gene sets, papers) are NOT project-owned → untouched."""
        from db.schema import cleaning_recipes, figures, skill_installs

        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                if tq.get(projects, project_id) is None:
                    return 0
                for fig in tq.select(figures, project_id=project_id):
                    tq.delete(figures, fig.id)
                for ds in tq.select(datasets, project_id=project_id):
                    for rec in tq.select(cleaning_recipes, dataset_id=ds.id):
                        tq.delete(cleaning_recipes, rec.id)
                    tq.delete(datasets, ds.id)
                for inst in tq.select(skill_installs, project_id=project_id):
                    tq.delete(skill_installs, inst.id)
                return tq.delete(projects, project_id)
        return run_with_db_retry(_work)

    def update_dataset(self, user_id: str, dataset_id: str, **changes) -> dict | None:
        """Patch a dataset's user-facing fields (FE ``renameDataset`` / ``updateDatasetProfile`` /
        ``markDatasetUpdated``): label · modality · qc · current_sha256. ``None`` ⇒ not this tenant's."""
        patch = {k: v for k, v in changes.items()
                 if k in ("label", "modality", "qc", "current_sha256") and v is not None}

        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                if tq.get(datasets, dataset_id) is None:
                    return None
                if patch:
                    tq.update(datasets, dataset_id, **patch)
                return _dataset_public(tq.get(datasets, dataset_id))
        return run_with_db_retry(_work)

    def _ensure_workspace(self, conn: sa.Connection, tq: TenantQuery, user_id: str) -> str:
        existing = conn.execute(
            sa.select(workspaces.c.id).where(workspaces.c.user_id == user_id).limit(1)
        ).first()
        if existing is not None:
            return existing.id
        return tq.insert(workspaces, name="My workspace")

    # --- datasets / uploads -------------------------------------------------------------------
    def intake(self, user_id: str, email: str | None, project_id: str, filename: str,
               content_sha256: str | None, size_bytes: int) -> dict:
        """Reserve a dataset (``pending_upload``) + return its server-derived key. Quota-gated.

        Raises ``QuotaExceeded`` over plan, ``KeyError`` if the project isn't this tenant's. The key
        is built from the verified ``user_id`` (T1) — the caller then presigns exactly it."""
        size_bytes = max(0, int(size_bytes or 0))

        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                upsert_user(conn, user_id, email or f"{user_id}@unknown.local")
                tq = TenantQuery(conn, user_id)
                if tq.get(projects, project_id) is None:
                    raise KeyError(project_id)  # not this tenant's project → 404 upstream
                q = self._quota(conn, user_id)
                used = self._count(conn, datasets, user_id)
                if q is not None and used >= q.max_datasets:
                    raise QuotaExceeded("max_datasets", used, int(q.max_datasets),
                                        f"Dataset limit reached ({q.max_datasets}).")
                if q is not None:
                    projected = self._storage_used(conn, user_id) + size_bytes
                    if projected > q.max_storage_bytes:
                        raise QuotaExceeded("max_storage_bytes", projected, int(q.max_storage_bytes),
                                            "Storage limit reached.")
                dsid = uuid.uuid4().hex
                key = upload_key(user_id, project_id, dsid, filename)
                tq.insert(datasets, id=dsid, project_id=project_id,
                          filename=filename, upload_s3_key=key, size_bytes=size_bytes,
                          current_sha256=content_sha256, status=PENDING)
                row = tq.get(datasets, dsid)
                return {"dataset": _dataset_public(row), "key": key}
        return run_with_db_retry(_work)

    def create_dataset(self, user_id: str, email: str | None, project_id: str, filename: str,
                       dataset_id: str | None = None, modality: str | None = None,
                       qc: dict | None = None, current_sha256: str | None = None) -> dict:
        """Create a metadata-only dataset row (FE ``addDataset``) — a dropped file the FE classifies via
        /data/inspect but doesn't (yet) upload to the store. Client-authoritative id + idempotent;
        status=``ready`` with no ``upload_s3_key`` (a run-dataset on it returns "re-upload"). Quota-gated.
        Coexists with ``intake`` (the real presigned-upload path); this is the no-bytes metadata twin."""
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                upsert_user(conn, user_id, email or f"{user_id}@unknown.local")
                tq = TenantQuery(conn, user_id)
                if dataset_id is not None:
                    existing = tq.get(datasets, dataset_id)
                    if existing is not None:
                        return _dataset_public(existing)  # idempotent re-POST
                if tq.get(projects, project_id) is None:
                    raise KeyError(project_id)
                q = self._quota(conn, user_id)
                used = self._count(conn, datasets, user_id)
                if q is not None and used >= q.max_datasets:
                    raise QuotaExceeded("max_datasets", used, int(q.max_datasets),
                                        f"Dataset limit reached ({q.max_datasets}).")
                values = {"project_id": project_id, "filename": filename, "modality": modality,
                          "qc": qc, "current_sha256": current_sha256, "status": READY, "size_bytes": 0}
                if dataset_id is not None:
                    values["id"] = dataset_id
                did = tq.insert(datasets, **values)
                return _dataset_public(tq.get(datasets, did))
        return run_with_db_retry(_work)

    def confirm(self, user_id: str, dataset_id: str, size_bytes: int | None = None,
                sha256: str | None = None) -> dict | None:
        """Flip a ``pending_upload`` row to ``ready`` once the object has landed. Idempotent (a
        re-confirm of a ``ready`` row is a no-op that returns it). Returns ``None`` if not this
        tenant's dataset."""
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                row = tq.get(datasets, dataset_id)
                if row is None:
                    return None
                changes: dict = {"status": READY}
                if size_bytes is not None:
                    changes["size_bytes"] = max(0, int(size_bytes))
                if sha256:
                    changes["current_sha256"] = sha256
                tq.update(datasets, dataset_id, **changes)
                return _dataset_public(tq.get(datasets, dataset_id))
        return run_with_db_retry(_work)

    def stamp_parsed(self, user_id: str, dataset_id: str, parquet_s3_key: str,
                     current_sha256: str, qc: dict | None = None) -> dict | None:
        """Record the parsed-matrix pointer after server-side ingest (spec §4.2)."""
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                if tq.get(datasets, dataset_id) is None:
                    return None
                tq.update(datasets, dataset_id, parquet_s3_key=parquet_s3_key,
                          current_sha256=current_sha256, qc=qc)
                return _dataset_public(tq.get(datasets, dataset_id))
        return run_with_db_retry(_work)

    def set_source(self, user_id: str, dataset_id: str, source: dict) -> dict | None:
        """Stamp cloud-import provenance (``{provider, ref, fetched_at}``) on a dataset row
        (routers/cloud.py). ``None`` ⇒ not this tenant's dataset."""
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                if tq.get(datasets, dataset_id) is None:
                    return None
                tq.update(datasets, dataset_id, source=source)
                return _dataset_public(tq.get(datasets, dataset_id))
        return run_with_db_retry(_work)

    def fail(self, user_id: str, dataset_id: str) -> dict | None:
        """Mark a dataset ``failed`` (a remote import that couldn't stream/parse — spec cloud/).
        Fail-soft: the row + any partial object are swept later (T2); ``None`` ⇒ not this tenant's."""
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                if tq.get(datasets, dataset_id) is None:
                    return None
                tq.update(datasets, dataset_id, status=FAILED)
                return _dataset_public(tq.get(datasets, dataset_id))
        return run_with_db_retry(_work)

    def storage_headroom(self, user_id: str) -> int | None:
        """Bytes this tenant may still store (``max_storage_bytes`` − reserved). ``None`` when the
        tenant has no quota row (unlimited) — the caller falls back to a config cap. Used as the
        running byte-cap for a remote import, so a stream can't blow past the plan (spec cloud/)."""
        def _work():
            with self.engine.connect() as conn:
                set_tenant(conn, user_id)
                q = self._quota(conn, user_id)
                if q is None:
                    return None
                return max(0, int(q.max_storage_bytes) - self._storage_used(conn, user_id))
        return run_with_db_retry(_work)

    def get_dataset(self, user_id: str, dataset_id: str) -> dict | None:
        def _work():
            with self.engine.connect() as conn:
                set_tenant(conn, user_id)
                row = TenantQuery(conn, user_id).get(datasets, dataset_id)
                return _dataset_public(row) if row is not None else None
        return run_with_db_retry(_work)

    def list_datasets(self, user_id: str, project_id: str | None = None) -> list[dict]:
        def _work():
            with self.engine.connect() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                rows = tq.select(datasets, project_id=project_id) if project_id else tq.select(datasets)
                return [_dataset_public(r) for r in rows]
        return run_with_db_retry(_work)

    def delete_dataset(self, user_id: str, dataset_id: str) -> int:
        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                return TenantQuery(conn, user_id).delete(datasets, dataset_id)
        return run_with_db_retry(_work)

    # --- T2 reconciliation (spec §7) ----------------------------------------------------------
    def heal_from_key(self, key: str, size_bytes: int | None = None,
                      sha256: str | None = None) -> dict | None:
        """S3-event path: an ``ObjectCreated`` event on ``uploads/`` flips the matching
        ``pending_upload`` row to ``ready``, so a dropped confirm POST still self-heals. The tenant is
        parsed FROM the key (server-derived, not input). Returns the dataset, or ``None`` if no
        matching pending row (a re-fired event for an already-ready row is also a no-op → its dict)."""
        from uploads.keys import parse_upload_key

        parsed = parse_upload_key(key)
        if parsed is None:
            return None
        user_id, dataset_id = parsed["user_id"], parsed["dataset_id"]

        def _work():
            with self.engine.begin() as conn:
                set_tenant(conn, user_id)
                tq = TenantQuery(conn, user_id)
                row = tq.get(datasets, dataset_id)
                if row is None or row.upload_s3_key != key:
                    return None  # the key's ids don't resolve to a real row → not ours to heal
                if row.status != READY:
                    changes = {"status": READY}
                    if size_bytes is not None:
                        changes["size_bytes"] = max(0, int(size_bytes))
                    if sha256:
                        changes["current_sha256"] = sha256
                    tq.update(datasets, dataset_id, **changes)
                return _dataset_public(tq.get(datasets, dataset_id))
        return run_with_db_retry(_work)

    def list_stale_pending(self, now: datetime, ttl_hours: int) -> list[dict]:
        """Pending rows older than the TTL whose object may never have landed (the reverse orphan,
        spec §7). System-wide (not tenant-scoped) — a sweep job; needs BYPASSRLS on Postgres (deploy
        step). The age compare is done in Python (not SQL): ``func.now()`` stores a tz-NAIVE string on
        SQLite, so a SQL ``< tz-aware`` compare would mis-string-match — pending rows are few, so the
        filter is cheap and dialect-proof."""
        cutoff = now - timedelta(hours=max(0, ttl_hours))

        def _work():
            with self.engine.connect() as conn:
                rows = conn.execute(sa.select(datasets).where(datasets.c.status == PENDING)).all()
                out = []
                for r in rows:
                    created = r.created_at
                    if created is None:
                        continue
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    if created < cutoff:
                        out.append({"id": r.id, "user_id": r.user_id,
                                    "upload_s3_key": r.upload_s3_key})
                return out
        return run_with_db_retry(_work)

    def list_active_upload_keys(self) -> set[str]:
        """Every ``upload_s3_key`` referenced by a live row (any status) — so the sweep can spot an
        object with no row (the forward orphan). System-wide; BYPASSRLS on Postgres (deploy step)."""
        def _work():
            with self.engine.connect() as conn:
                rows = conn.execute(
                    sa.select(datasets.c.upload_s3_key).where(datasets.c.upload_s3_key.is_not(None))
                ).all()
                return {r.upload_s3_key for r in rows}
        return run_with_db_retry(_work)

    def purge_dataset(self, user_id: str, dataset_id: str) -> int:
        """Hard-delete a dataset row by (tenant, id) — used by the sweep for a stale pending row."""
        return self.delete_dataset(user_id, dataset_id)


# Lazy process singleton + a test seam (mirrors get_object_store/get_verifier). Built from
# settings.database_url; the upload endpoints require a DB, so a missing URL surfaces as a clear
# 503 at the handler, not a silent default.
_repo: UploadRepo | None = None


def get_upload_repo() -> UploadRepo:
    global _repo
    if _repo is None:
        from config import settings

        if not settings.database_url:
            raise RuntimeError(
                "uploads require a database (set SELOM_DATABASE_URL; SELOM_DB_AUTO_CREATE=true for dev)"
            )
        _repo = UploadRepo(url=settings.database_url, create=settings.db_auto_create)
    return _repo


def set_upload_repo(repo: UploadRepo | None) -> None:
    global _repo
    _repo = repo
