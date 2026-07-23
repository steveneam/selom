"""``CappedReader`` — a file-like adapter over a byte-chunk iterator that enforces a running
byte-cap, so a provider→store stream can't exceed the tenant's storage headroom (or OOM the box).

It turns any iterator of ``bytes`` (httpx ``iter_bytes``, an S3 ``StreamingBody.iter_chunks``, …)
into a ``.read(size)`` the object store's ``put_stream`` (and boto3's ``upload_fileobj``) can pull
from. Bytes are counted **as they are pulled from the source**; crossing ``max_bytes`` raises
``CloudTooLarge`` immediately — before the over-limit bytes are written anywhere.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from cloud.errors import CloudFetchError, CloudTooLarge

_NET_CHUNK = 1 << 16  # 64 KiB network reads


class CappedReader:
    def __init__(self, chunks: Iterable[bytes], max_bytes: int) -> None:
        self._it: Iterator[bytes] = iter(chunks)
        self._buf = bytearray()
        self.max_bytes = max(0, int(max_bytes))
        self.bytes_read = 0

    def _pull(self) -> bytes | None:
        """Next source chunk (counting + capping), or ``None`` at end of stream."""
        try:
            chunk = next(self._it)
        except StopIteration:
            return None
        self.bytes_read += len(chunk)
        if self.bytes_read > self.max_bytes:
            raise CloudTooLarge(
                f"import exceeds the {self.max_bytes} byte limit (storage quota / cap)"
            )
        return chunk

    def read(self, size: int = -1) -> bytes:
        # size < 0 / None → drain the rest (still capped); otherwise fill up to `size`.
        if size is None or size < 0:
            while (chunk := self._pull()) is not None:
                self._buf.extend(chunk)
            out = bytes(self._buf)
            self._buf.clear()
            return out
        while len(self._buf) < size:
            chunk = self._pull()
            if chunk is None:
                break
            self._buf.extend(chunk)
        out = bytes(self._buf[:size])
        del self._buf[:size]
        return out


def stream_http_to_store(
    *,
    method: str,
    url: str,
    key: str,
    max_bytes: int,
    headers: dict[str, str] | None = None,
    content: bytes | None = None,
    follow_redirects: bool = True,
    timeout_s: float = 120.0,
    transport=None,
) -> int:
    """Stream a provider HTTP download straight into the object store at ``key``, capped at
    ``max_bytes``. Shared by the OAuth connectors (Google/OneDrive/Dropbox), which hit a **fixed,
    trusted** provider host with a bearer token — so (unlike the user-supplied URL connector) no SSRF
    check is applied and provider CDN redirects are followed. Returns bytes written.

    ``transport`` is a test seam (an ``httpx.MockTransport``); production passes ``None``.
    """
    import httpx

    from storage.object_store import get_object_store

    store = get_object_store()
    with httpx.Client(
        transport=transport, timeout=timeout_s, follow_redirects=follow_redirects
    ) as client:
        with client.stream(method, url, headers=headers, content=content) as resp:
            if resp.status_code >= 400:
                raise CloudFetchError(f"provider returned HTTP {resp.status_code}")
            reader = CappedReader(resp.iter_bytes(_NET_CHUNK), max_bytes)
            ctype = (resp.headers.get("content-type") or "application/octet-stream")
            store.put_stream(key, reader, ctype.split(";")[0].strip())
            return reader.bytes_read
