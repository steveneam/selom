"""DB retry/backoff for the Aurora Serverless v2 "resuming" class (materialization 7b, spec §8/T3).

Aurora Serverless v2 scaling from a paused/low state drops the first connection after idle; the
first query then errors with a transient "server closed the connection" / "database is resuming"
``OperationalError``. ``pool_pre_ping`` (db/engine.py) recycles a *known-dead* pooled connection, but
a scaling event mid-flight still needs a bounded retry. This wraps a unit of DB work in an
exponential backoff (default 3 tries, 2s → 4s → 8s) that retries ONLY the transient class — a real
error (bad SQL, constraint violation, auth) is re-raised immediately, never masked.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.exc import DBAPIError, OperationalError

T = TypeVar("T")

# Substrings that mark Aurora's resume/scale transient — matched case-insensitively against the
# driver message. Anything not on this list is a genuine failure and is not retried.
_TRANSIENT_MARKERS = (
    "is resuming",
    "is starting up",
    "server closed the connection",
    "connection reset",
    "could not connect",
    "operational timeout",
    "terminating connection",
)


def is_transient(exc: BaseException) -> bool:
    if not isinstance(exc, (OperationalError, DBAPIError)):
        return False
    msg = str(getattr(exc, "orig", exc)).lower()
    return any(marker in msg for marker in _TRANSIENT_MARKERS)


def run_with_db_retry(
    fn: Callable[[], T],
    *,
    retries: int = 3,
    base_delay: float = 2.0,
    _sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run ``fn`` with bounded exponential backoff on the Aurora-resume transient class.

    ``_sleep`` is injected so tests assert the backoff without real delay.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except (OperationalError, DBAPIError) as exc:
            attempt += 1
            if attempt > retries or not is_transient(exc):
                raise
            _sleep(base_delay * (2 ** (attempt - 1)))
