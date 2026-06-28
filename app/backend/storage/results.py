"""Result store — where a finished figure spec lives, and how it's fetched.

A thin adapter over the shared ``ObjectStore`` seam (storage/object_store.py): the
figure bundle is bytes at ``results/{job_id}.json`` on whichever backend config
selects — the local filesystem in dev, AWS S3 in prod — behind one ``ResultStore``
interface. The local backend has no presigned URL, so the fetch URL stays the in-app
``GET /jobs/{id}/result`` route; S3 returns a real time-limited presigned GET.

This is step 1 of the materialization (docs/aws-materialization/spec.md §1.2, §13):
the result store is the first of four content-addressed stores to ride the seam.
"""

from __future__ import annotations

import json
from typing import Protocol

from storage.object_store import ObjectStore, make_object_store


class ResultStore(Protocol):
    def put(self, key: str, payload: dict) -> str:
        """Persist a result bundle ({figure, provenance, methods}); return a fetch URL."""
        ...

    def get(self, key: str) -> dict | None:
        """Return the stored result bundle, or None if absent."""
        ...

    def url_if_exists(self, key: str) -> str | None:
        """A fetch URL if the result is present, else None (cross-process completion probe)."""
        ...


class ObjectStoreResultStore:
    """``ResultStore`` over the shared ``ObjectStore`` (key ``results/{id}.json``)."""

    def __init__(self, store: ObjectStore, presign_ttl: int) -> None:
        self.store = store
        self.ttl = presign_ttl

    def _key(self, key: str) -> str:
        return f"results/{key}.json"

    def put(self, key: str, payload: dict) -> str:
        self.store.put_bytes(self._key(key), json.dumps(payload).encode(), "application/json")
        return self._url(key)

    def get(self, key: str) -> dict | None:
        raw = self.store.get_bytes(self._key(key))
        return json.loads(raw) if raw is not None else None

    def url_if_exists(self, key: str) -> str | None:
        return self._url(key) if self.store.head(self._key(key)) else None

    def _url(self, key: str) -> str:
        # S3 -> a real presigned GET; local -> the in-app route (dev has no presigning).
        return self.store.presign_get(self._key(key), self.ttl) or f"/jobs/{key}/result"


def make_result_store(settings) -> ResultStore:
    return ObjectStoreResultStore(make_object_store(settings), settings.s3_presign_ttl)
