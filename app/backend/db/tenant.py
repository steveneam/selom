"""Structural tenant isolation — ``TenantQuery`` + the RLS backstop (materialization 7b, spec §6).

The headline production risk (plan R-3) is a cross-tenant leak from a forgotten ``user_id`` filter.
Two defences, defence-in-depth:

  1. **Application (primary) — ``TenantQuery``.** Bound to ONE tenant at construction; every
     ``select``/``insert``/``update``/``delete`` injects ``WHERE user_id = <tenant>``. There is no
     method that returns rows without the predicate, so it can't be forgotten — not a convention, a
     structural guarantee. ``insert`` *overwrites* any caller-supplied ``user_id`` with the bound
     one, so a malicious body ``{"user_id": "victim"}`` is silently corrected, never honoured.
  2. **Database (backstop) — native Postgres RLS.** Each transaction runs ``set_tenant(conn, uid)``
     (``SET LOCAL app.user_id`` via ``set_config(..., is_local=true)``); the 0002/0003 policies then
     refuse cross-tenant rows even if a future code path bypasses ``TenantQuery``. No-op on SQLite
     (the dev/test path has no RLS — the app layer is what those tests prove).

The tenant ``user_id`` only ever comes from the verified auth claim (``auth/context.py``), never from
a request param/body (spec §6.2).
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa


def _is_postgres(conn: sa.Connection) -> bool:
    return conn.dialect.name == "postgresql"


def set_tenant(conn: sa.Connection, user_id: str) -> None:
    """Bind the DB-layer tenant for the current transaction (RLS backstop). Postgres-only.

    Uses ``set_config(setting, value, is_local=true)`` — the parameterizable, injection-safe
    equivalent of ``SET LOCAL`` (the value is bound, never string-interpolated). On SQLite this is a
    no-op (no RLS); the application ``TenantQuery`` is the guarantee there.
    """
    if _is_postgres(conn):
        conn.execute(sa.text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})


def upsert_user(
    conn: sa.Connection,
    user_id: str,
    email: str,
    **defaults,
) -> None:
    """Insert the ``users`` row on first request for a new tenant; idempotent (do-nothing on conflict).

    Concurrency-safe via ``ON CONFLICT DO NOTHING`` (both SQLite + Postgres support it), so two
    simultaneous first-requests can't double-insert. Must run AFTER ``set_tenant(conn, user_id)`` so
    the Postgres RLS ``WITH CHECK`` (``user_id = app.user_id``) passes for the new row.
    """
    from db.schema import users

    values = {"user_id": user_id, "email": email, **defaults}
    if _is_postgres(conn):
        from sqlalchemy.dialects.postgresql import insert as _insert
    else:
        from sqlalchemy.dialects.sqlite import insert as _insert
    stmt = _insert(users).values(**values).on_conflict_do_nothing(index_elements=["user_id"])
    conn.execute(stmt)


def _pk_col(table: sa.Table) -> sa.Column:
    cols = list(table.primary_key.columns)
    if len(cols) != 1:
        raise ValueError(f"{table.name} has a composite/no PK — TenantQuery needs a single-column PK")
    return cols[0]


class TenantQuery:
    """Every data-access call is bound to ONE tenant. No method issues an unscoped query."""

    def __init__(self, conn: sa.Connection, user_id: str) -> None:
        if not user_id:
            raise ValueError("TenantQuery requires a non-empty user_id (the verified tenant)")
        self._conn = conn
        self._uid = user_id  # set ONCE from the verified claim — never from a request param

    @property
    def user_id(self) -> str:
        return self._uid

    def _tenant_col(self, table: sa.Table) -> sa.Column:
        col = table.c.get("user_id")
        if col is None:
            raise ValueError(f"{table.name} has no user_id column — not a tenant table")
        return col

    def select(self, table: sa.Table, **filters) -> list[sa.Row]:
        """Rows for this tenant only, optionally narrowed by equality ``filters``."""
        stmt = sa.select(table).where(self._tenant_col(table) == self._uid)
        for key, value in filters.items():
            stmt = stmt.where(table.c[key] == value)
        return list(self._conn.execute(stmt).all())

    def get(self, table: sa.Table, row_id) -> sa.Row | None:
        stmt = sa.select(table).where(
            _pk_col(table) == row_id, self._tenant_col(table) == self._uid
        )
        return self._conn.execute(stmt).first()

    def insert(self, table: sa.Table, **values):
        """Insert a row owned by this tenant. A caller-supplied ``user_id`` is OVERWRITTEN.

        Returns the primary-key value (a generated uuid-hex when the caller omits the PK, mirroring
        ``SqlJobStore``). The tenant predicate is forced, never trusted from input.
        """
        values["user_id"] = self._uid  # overwrite — never honour a caller's user_id
        pk = _pk_col(table)
        if pk.name not in values and pk.name in ("id",):
            values[pk.name] = uuid.uuid4().hex
        self._conn.execute(sa.insert(table).values(**values))
        return values.get(pk.name)

    def update(self, table: sa.Table, row_id, **changes) -> int:
        """Update a row, scoped to this tenant. ``user_id`` cannot be changed via ``changes``."""
        changes.pop("user_id", None)  # a tenant can never reassign ownership
        if not changes:
            return 0
        stmt = (
            sa.update(table)
            .where(_pk_col(table) == row_id, self._tenant_col(table) == self._uid)
            .values(**changes)
        )
        return self._conn.execute(stmt).rowcount

    def delete(self, table: sa.Table, row_id) -> int:
        stmt = sa.delete(table).where(
            _pk_col(table) == row_id, self._tenant_col(table) == self._uid
        )
        return self._conn.execute(stmt).rowcount
