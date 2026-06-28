"""Alembic migration environment.

The database URL is resolved (in order): an inline ``-x url=…`` override, then
``config.settings.database_url`` (``SELOM_DATABASE_URL``). The same migration set therefore
applies to the SQLite dev/test path and the Aurora Postgres prod path — Postgres-only DDL
(RLS, etc.) is guarded per-dialect inside the migrations (step 7), so an upgrade is portable.
"""

from __future__ import annotations

import pathlib
import sys

from alembic import context
from sqlalchemy import create_engine, pool

# Make the backend package importable (config, db.schema) regardless of CWD.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from db.schema import metadata  # noqa: E402

config = context.config
target_metadata = metadata


def _url() -> str:
    x = context.get_x_argument(as_dictionary=True)
    if x.get("url"):
        return x["url"]
    from config import settings

    if not settings.database_url:
        raise RuntimeError(
            "no database URL — set SELOM_DATABASE_URL or pass `-x url=sqlite:///dev.db`"
        )
    return settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_url(), poolclass=pool.NullPool, future=True)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
