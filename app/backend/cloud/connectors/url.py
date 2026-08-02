"""URL / S3 connector — the one cloud provider that needs no OAuth. It streams a public ``http(s)``
URL or an ``s3://bucket/key`` object straight into Selom's object store, enforcing the SSRF guard and
a running byte-cap. This is the fully-working path in the foundation slice; the OAuth connectors
reuse the same ``CappedReader`` → ``put_stream`` streaming shape once their tokens exist.
"""

from __future__ import annotations

import httpx

from cloud._stream import CappedReader
from cloud.errors import CloudFetchError
from cloud.ssrf import assert_safe_url

_NET_CHUNK = 1 << 16          # 64 KiB network reads
_MAX_REDIRECTS = 5
_DEFAULT_TIMEOUT_S = 120.0    # generous: streaming a large omics file, not a snappy API call
_S3_PREFIX = "s3://"


class UrlConnector:
    """Import from a URL / S3 URI. ``transport`` is a test seam (inject an ``httpx.MockTransport``);
    production passes ``None`` so httpx uses the real network transport."""

    def __init__(self, transport: httpx.BaseTransport | None = None,
                 timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        self._transport = transport
        self._timeout_s = timeout_s

    # --- import ------------------------------------------------------------------------------
    def fetch_to_store(self, handle: str, token: str | None, key: str, max_bytes: int) -> int:
        handle = (handle or "").strip()
        if not handle:
            raise CloudFetchError("no URL/S3 reference supplied")
        if handle.lower().startswith(_S3_PREFIX):
            return self._fetch_s3(handle, key, max_bytes)
        return self._fetch_http(handle, key, max_bytes)

    def _fetch_http(self, url: str, key: str, max_bytes: int) -> int:
        from storage.object_store import get_object_store

        store = get_object_store()
        current = url
        with httpx.Client(transport=self._transport, timeout=self._timeout_s) as client:
            for _ in range(_MAX_REDIRECTS + 1):
                assert_safe_url(current)  # re-check EVERY hop (a public URL can 302 internal)
                with client.stream("GET", current, follow_redirects=False) as resp:
                    if resp.is_redirect:
                        loc = resp.headers.get("location")
                        if not loc:
                            raise CloudFetchError("redirect without a Location header")
                        current = str(httpx.URL(current).join(loc))
                        continue
                    if resp.status_code >= 400:
                        raise CloudFetchError(f"source returned HTTP {resp.status_code}")
                    reader = CappedReader(resp.iter_bytes(_NET_CHUNK), max_bytes)
                    ctype = (resp.headers.get("content-type") or "application/octet-stream")
                    store.put_stream(key, reader, ctype.split(";")[0].strip())
                    return reader.bytes_read
        raise CloudFetchError(f"too many redirects (> {_MAX_REDIRECTS})")

    def _fetch_s3(self, uri: str, key: str, max_bytes: int) -> int:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError

        from storage.object_store import get_object_store

        bucket, _, obj_key = uri[len(_S3_PREFIX):].partition("/")
        if not bucket or not obj_key:
            raise CloudFetchError(f"malformed s3 URI (need s3://bucket/key): {uri!r}")
        client = boto3.client(
            "s3", config=Config(retries={"max_attempts": 5, "mode": "standard"})
        )
        try:
            obj = client.get_object(Bucket=bucket, Key=obj_key)
        except (BotoCoreError, ClientError) as exc:
            raise CloudFetchError(f"could not read {uri}: {exc}") from exc
        reader = CappedReader(obj["Body"].iter_chunks(_NET_CHUNK), max_bytes)
        ctype = obj.get("ContentType") or "application/octet-stream"
        get_object_store().put_stream(key, reader, ctype)
        return reader.bytes_read

    # --- export (s3:// destination) -----------------------------------------------------------
    def push_from_store(self, key: str, dest: str, token: str | None) -> int:
        from cloud.connectors.base import push_store_object_via_path

        return push_store_object_via_path(self, key, dest, token)

    def push_path(self, local_path, dest: str, token: str | None, *, filename: str) -> int:
        """Upload a local file to an ``s3://bucket/prefix`` destination.

        Behaviour is unchanged from when this read the object store directly: a trailing-slash (or
        empty) prefix is a folder and keeps ``filename``; otherwise the prefix IS the key.
        """
        import pathlib as _pathlib

        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        if not dest.lower().startswith(_S3_PREFIX):
            raise CloudFetchError("URL/S3 export supports only an s3://bucket/key destination")
        bucket, _, prefix = dest[len(_S3_PREFIX):].partition("/")
        if not bucket:
            raise CloudFetchError(f"malformed s3 destination: {dest!r}")
        dest_key = prefix if prefix and not prefix.endswith("/") else f"{prefix}{filename}"
        local = _pathlib.Path(local_path)
        if not local.is_file():
            raise CloudFetchError(f"nothing to upload at {local}")
        client = boto3.client("s3")
        try:
            with local.open("rb") as fh:
                client.upload_fileobj(fh, bucket, dest_key)
        except (BotoCoreError, ClientError) as exc:
            raise CloudFetchError(f"could not write {dest}: {exc}") from exc
        return local.stat().st_size
