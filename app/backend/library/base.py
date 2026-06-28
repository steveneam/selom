"""Shared base for the tenant-CRUD repos behind the FE stores (AWS materialization step 7c).

The step-6 ``uploads/`` package owns projects + datasets + the upload flow; this package owns the
*rest* of the tenant data model the FE ``projectStore`` / ``workspaceStore`` persist — figures, gene
sets, saved papers, skill installs, cleaning recipes, reproduction-run pointers. (It is the data
layer for the *Workspace Library feature*; the name overlap is incidental.)

Every repo mirrors ``UploadRepo`` (``uploads/repo.py``): one short transaction per method,
``set_tenant`` + ``TenantQuery`` so a forgotten ``user_id`` filter is structurally impossible (spec
§6.1), and the tenant is ALWAYS the verified ``ctx.user_id`` — never a request body (spec §6.2). The
methods are split across mixins for readability and composed into one ``LibraryRepo`` (``repo.py``),
so the whole library shares ONE engine/pool and main.py wires a single dependency.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa

from db.engine import make_engine


def iso(dt) -> str | None:
    """Serialize a DB timestamp as ISO-8601 (the wire shape ``UploadRepo`` already uses; the FE
    adapter converts it to an epoch-ms ``createdAt``)."""
    return dt.isoformat() if isinstance(dt, datetime) else dt


def ensure_workspace(conn: sa.Connection, tq) -> str:
    """The account's single workspace id (created on first need). Account-level assets (gene sets,
    papers, workspace-wide skill installs) carry it so the ``skill_installs`` functional unique
    ``COALESCE(project_id, workspace_id), skill_id`` stays unique *per tenant* — a workspace-wide
    install with a NULL workspace_id would collide across tenants. Mirrors ``UploadRepo._ensure_workspace``."""
    from db.schema import workspaces

    existing = conn.execute(
        sa.select(workspaces.c.id).where(workspaces.c.user_id == tq.user_id).limit(1)
    ).first()
    if existing is not None:
        return existing.id
    return tq.insert(workspaces, name="My workspace")


class TenantRepo:
    """Engine construction shared by every library mixin (SQLite dev/test, Postgres prod, one URL)."""

    def __init__(self, engine: sa.Engine | None = None, url: str = "", create: bool = False) -> None:
        self.engine = engine if engine is not None else make_engine(url)
        if create:  # dev/test convenience (SQLite); prod applies the Alembic migration instead
            from db.schema import metadata

            metadata.create_all(self.engine)
