"""SQLAlchemy engine factory — one pooled engine per database URL.

The URL chooses the backend by config (the local-dev/AWS-prod seam, plan D6):
  * ``sqlite:///…`` (dev/test) — stdlib, zero infra.
  * ``postgresql+psycopg://…`` (prod) — Aurora; psycopg is the prod-only driver, imported by
    SQLAlchemy lazily when a postgres URL is dialed, so the SQLite fast suite never needs it.

Engines are cached per URL so the app reuses one connection pool; a fresh ``SqlJobStore`` on the
same URL shares it (and the same data — that's the cross-instance statelessness guarantee).
``T3`` (Aurora resume): ``pool_pre_ping`` recycles a connection the serverless DB dropped while
paused, so the first query after idle reconnects instead of erroring.
"""

from __future__ import annotations

import os
import threading

import sqlalchemy as sa

_engines: dict[str, sa.Engine] = {}
_schema_lock = threading.Lock()


def make_engine(url: str) -> sa.Engine:
    if not url:
        raise ValueError("a database URL is required (set SELOM_DATABASE_URL for SELOM_JOB_STORE=sql)")
    eng = _engines.get(url)
    if eng is None:
        if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            # On Lambda each warm container keeps its OWN pool; idle connections multiply under
            # concurrency and Aurora reaps them, so a default QueuePool causes a connection storm.
            # NullPool (connect-per-use) is the serverless-correct choice (RDS Proxy is the
            # alternative — spec §8). pre_ping is redundant when every connect is already fresh.
            from sqlalchemy.pool import NullPool

            eng = sa.create_engine(url, poolclass=NullPool, future=True)
        else:
            # Long-lived dev server / container: a pooled engine, pre-pinged so a connection the
            # serverless DB dropped while paused (T3 Aurora resume) reconnects on next use.
            eng = sa.create_engine(url, pool_pre_ping=True, future=True)
        _engines[url] = eng
    return eng


def ensure_schema(engine: sa.Engine) -> None:
    """Create the dev/test schema on ``engine``, safely under concurrency.

    THE BUG THIS FIXES. ``UploadRepo``, ``LibraryRepo`` and ``SqlJobStore`` each called
    ``metadata.create_all(self.engine)`` from their own constructor, and each is built lazily by a
    FastAPI dependency — so on a COLD database the first burst of concurrent requests races.
    ``create_all(checkfirst=True)`` reflects, then issues CREATE, and the gap between the two is not
    atomic: two requests both see the table missing, both CREATE, one loses with
    ``table analysis_jobs already exists``. Measured on a fresh store: **5 requests died with a 500
    on every first page load**, silently, because the frontend re-fetches and the second attempt
    finds the schema already there. Only a browser run against a freshly-deleted store shows it.

    Two things make it safe rather than merely quieter:
      * the lock serializes the in-process racers, which is all of them for a single uvicorn worker;
      * the ``OperationalError`` catch covers the cross-process case (a second worker, or the
        Alembic path running alongside), where a lock cannot reach. Losing that race is a
        SUCCESS — the table exists, which is the entire post-condition — so it is swallowed only
        after re-checking that the tables really are there, never blanket.
    """
    from db.schema import metadata

    with _schema_lock:
        try:
            metadata.create_all(engine)
        except sa.exc.OperationalError:
            # Another process won. Confirm the post-condition rather than trusting the error text,
            # which differs per backend — a genuine failure (bad path, no permission) must still raise.
            existing = set(sa.inspect(engine).get_table_names())
            missing = {t.name for t in metadata.sorted_tables} - existing
            if missing:
                raise


def reset_engines() -> None:
    """Dispose + drop every cached engine (test hygiene / forced reconnect)."""
    for eng in _engines.values():
        eng.dispose()
    _engines.clear()
