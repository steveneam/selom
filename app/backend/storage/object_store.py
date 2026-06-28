"""Object store — the single byte-IO seam every content-addressed store rides on.

One ``ObjectStore`` Protocol, two interchangeable backends selected **once** by config
(``SELOM_OBJECT_STORE``), exactly as ``make_result_store`` selected Local↔R2 before:

  * ``LocalObjectStore`` (default) — bytes under ``data_dir``; the dev path never needs
    AWS (plan D6). ``presign_get`` returns ``None`` — in dev the app serves bytes through
    its own routes (e.g. ``GET /jobs/{id}/result``), so each adapter supplies its own URL.
  * ``S3ObjectStore`` — boto3 ``s3`` client (regional AWS S3). boto3 is lazy-imported so
    the light core install never needs it; credentials come from the standard AWS chain
    (``~/.aws/credentials`` in dev, the Lambda execution role in prod) — not Selom env vars.

The four content-addressed stores (result · result-cache disk tier · lineage · ledger)
converge onto this one seam — one boto3 surface to harden, one place for retry/backoff
(T3) and prefix/IAM (T1). See docs/aws-materialization/spec.md §1.

RISKS #5: boto3 >=1.36 breaks S3-compatible checksums unless the client sets
``request_checksum_calculation='when_required'`` — applied below.
"""

from __future__ import annotations

import os
import pathlib
from typing import Protocol


class ObjectStore(Protocol):
    def get_bytes(self, key: str) -> bytes | None:
        """Return the object's bytes, or None if absent."""
        ...

    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """Write bytes at ``key`` (content-addressed keys make an overwrite idempotent)."""
        ...

    def head(self, key: str) -> bool:
        """True if the object exists (a cross-process completion probe)."""
        ...

    def head_size(self, key: str) -> int | None:
        """The object's size in bytes, or ``None`` if absent (the upload-confirm landing check)."""
        ...

    def download_to_path(self, key: str, dest) -> bool:
        """Stream the object to local file ``dest`` (never buffers the whole object in memory) —
        the large-omics parse path reads from here, not ``get_bytes`` (spec §4.2). True if
        downloaded, False if absent."""
        ...

    def delete(self, key: str) -> None:
        """Remove the object if present (a no-op if absent)."""
        ...

    def list_keys(self, prefix: str) -> list[str]:
        """Every object key under ``prefix`` (the T2 sweep spots an object with no row, spec §7)."""
        ...

    def presign_get(self, key: str, ttl: int) -> str | None:
        """A time-limited GET URL (S3), or ``None`` for the local backend — in dev the
        app serves bytes through its own routes, so the adapter supplies the URL."""
        ...

    def presign_put(self, key: str, ttl: int, max_bytes: int) -> dict:
        """A presigned POST policy for a direct client→store upload (spec §1.1/§4.2): ``{url, fields}``.

        The server derives ``key`` from the verified tenant (``uploads/{user_id}/…``) and signs it
        EXACTLY, so the client can't write outside its prefix (T1); a ``content-length-range``
        condition caps the size *before* the bytes land (replacing the post-read cap). The local
        backend returns an in-app upload-route shape (dev never needs AWS)."""
        ...


class LocalObjectStore:
    """Filesystem backend rooted at ``data_dir``; keys map to nested paths."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = pathlib.Path(root)

    def _path(self, key: str) -> pathlib.Path:
        return self.root / key

    def get_bytes(self, key: str) -> bytes | None:
        p = self._path(key)
        return p.read_bytes() if p.exists() else None

    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Write-temp-then-replace: atomic on the same filesystem, so a concurrent reader
        # never sees a torn write (the cache/lineage adapters relied on this before the
        # seam; S3 PUT is atomic by nature). content_type is unused for the filesystem.
        tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, p)

    def head(self, key: str) -> bool:
        return self._path(key).exists()

    def head_size(self, key: str) -> int | None:
        p = self._path(key)
        return p.stat().st_size if p.exists() else None

    def download_to_path(self, key: str, dest) -> bool:
        import shutil

        p = self._path(key)
        if not p.exists():
            return False
        dest = pathlib.Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
        return True

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def list_keys(self, prefix: str) -> list[str]:
        base = self._path(prefix)
        if not base.exists():
            return []
        files = [base] if base.is_file() else (p for p in base.rglob("*") if p.is_file())
        return [p.relative_to(self.root).as_posix() for p in files]

    def presign_get(self, key: str, ttl: int) -> str | None:
        return None  # dev: the app serves bytes; the adapter supplies its own route

    def presign_put(self, key: str, ttl: int, max_bytes: int) -> dict:
        # Dev: there's no S3 to PUT to — the step-6 intake serves an in-app upload route. The shape
        # mirrors S3's {url, fields} so the FE upload code is backend-agnostic.
        return {"url": f"/uploads/local/{key}", "fields": {"key": key, "max_bytes": max_bytes}}


class S3ObjectStore:
    """AWS S3 backend (regional). boto3 is imported lazily so the light core never needs it."""

    def __init__(self, settings) -> None:
        import boto3
        from botocore.config import Config

        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region or None,  # None -> boto3 resolves from the chain
            config=Config(
                request_checksum_calculation="when_required",   # RISKS #5
                response_checksum_validation="when_supported",
                retries={"max_attempts": 5, "mode": "standard"},  # T3 transient-error backoff
            ),
        )

    def get_bytes(self, key: str) -> bytes | None:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.NoSuchKey:
            return None
        return obj["Body"].read()

    def put_bytes(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )

    def head(self, key: str) -> bool:
        return self.head_size(key) is not None

    def head_size(self, key: str) -> int | None:
        from botocore.exceptions import ClientError

        try:
            obj = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            # Map "absent" (404/NotFound/NoSuchKey) → None; RE-RAISE everything else.
            # Swallowing all exceptions made a throttle/403/5xx look identical to "not there",
            # so upload-confirm returned a misleading 409 on a transient error (the hardest
            # class to diagnose in prod). Distinguish absent from broken.
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NotFound", "NoSuchKey"):
                return None
            raise
        return int(obj.get("ContentLength", 0))

    def download_to_path(self, key: str, dest) -> bool:
        from botocore.exceptions import ClientError

        dest = pathlib.Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.client.download_file(self.bucket, key, str(dest))  # streams to disk
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NotFound", "NoSuchKey"):
                return False
            raise
        return True

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys

    def presign_get(self, key: str, ttl: int) -> str | None:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=ttl,
        )

    def presign_put(self, key: str, ttl: int, max_bytes: int) -> dict:
        # POST policy (not a PUT query URL) so the size ceiling is signed in: the client cannot PUT
        # more than max_bytes, and the key is fixed (T1 prefix isolation — server-derived, not input).
        return self.client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Conditions=[["content-length-range", 0, max_bytes]],
            ExpiresIn=ttl,
        )


def make_object_store(settings) -> ObjectStore:
    if settings.object_store.strip().lower() == "s3":
        return S3ObjectStore(settings)
    return LocalObjectStore(settings.data_dir)


# Lazy process default + a test seam (mirrors get_cache/set_cache, get_store/set_store) so
# the cache · lineage · ledger adapters share one backend and tests inject an in-memory one.
_object_store: ObjectStore | None = None


def get_object_store() -> ObjectStore:
    global _object_store
    if _object_store is None:
        from config import settings

        _object_store = make_object_store(settings)
    return _object_store


def set_object_store(store: ObjectStore | None) -> None:
    global _object_store
    _object_store = store
