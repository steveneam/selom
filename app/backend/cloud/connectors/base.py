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
        ``s3://bucket/prefix`` URI). Returns the number of bytes written.

        Implemented once for every provider by :func:`push_store_object_via_path` — download the
        stored object to a temp file, then hand it to :meth:`push_path`."""
        ...

    def push_path(self, local_path, dest: str, token: str | None, *, filename: str) -> int:
        """Export: upload the file at ``local_path`` to ``dest`` on the provider, named
        ``filename``. Returns the number of bytes written.

        This is the primitive, not ``push_from_store``: every provider upload is "read this file,
        write it there". Splitting it out is what lets a **rendered figure** be exported without
        inventing a scratch object in the store first — the figure path renders to a temp file and
        calls this directly (docs/cloud-export/spec.md D1/D2)."""
        ...


def push_store_object_via_path(connector: "CloudConnector", key: str, dest: str,
                               token: str | None) -> int:
    """Shared ``push_from_store``: object store -> temp file -> ``connector.push_path``.

    Every connector's ``push_from_store`` is this, so the download-and-clean-up half exists once.
    The temp directory is context-managed, so the local copy is removed even if the upload raises.
    """
    import pathlib
    import tempfile

    from cloud.errors import CloudFetchError
    from storage.object_store import get_object_store

    name = pathlib.PurePosixPath(key).name
    store = get_object_store()
    with tempfile.TemporaryDirectory(prefix="selom-export-") as td:
        local = pathlib.Path(td) / name
        if not store.download_to_path(key, local):
            raise CloudFetchError(f"object not in store: {key}")
        return connector.push_path(local, dest, token, filename=name)
