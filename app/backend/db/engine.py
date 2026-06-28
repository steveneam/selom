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

import sqlalchemy as sa

_engines: dict[str, sa.Engine] = {}


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


def reset_engines() -> None:
    """Dispose + drop every cached engine (test hygiene / forced reconnect)."""
    for eng in _engines.values():
        eng.dispose()
    _engines.clear()
