"""The ``CloudConnector`` seam — one protocol every provider (URL/S3, Google, OneDrive, Dropbox)
implements, so the import/export endpoints and the registry never branch on provider identity.

Both directions **stream through the object store** (``put_stream`` / ``download_to_path``), never
buffering a whole file — a GB-scale omics upload must not land in the process heap. ``token`` is the
provider access token (a Nango-brokered bearer for the OAuth providers; ``None`` for URL/S3, which
needs no auth). The URL/S3 connector is fully working now; the OAuth connectors are scaffolded and
gated behind their per-provider feature flag until the owner's client IDs exist in Nango.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CloudConnector(Protocol):
    def fetch_to_store(
        self, handle: str, token: str | None, key: str, max_bytes: int
    ) -> int:
        """Stream the provider file identified by ``handle`` (a URL/S3 URI, or a provider file id)
        into the object store at ``key``, enforcing a running ``max_bytes`` cap (the tenant's storage
        headroom). Returns the number of bytes written. Raises on a too-large stream, an unreachable
        source, an SSRF-blocked target, or a missing/expired ``token``."""
        ...

    def push_from_store(self, key: str, dest: str, token: str | None) -> int:
        """Export: stream the object at ``key`` out to ``dest`` on the provider (a folder id, or an
        ``s3://bucket/prefix`` URI). Returns the number of bytes written. Scaffolded for the OAuth
        providers until their client IDs exist."""
        ...
