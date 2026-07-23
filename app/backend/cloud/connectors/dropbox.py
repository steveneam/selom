"""Dropbox connector (scaffold). Streams a file's bytes into the object store using a Nango-brokered
access token. Dormant until ``SELOM_CLOUD_DROPBOX`` is on and the owner's Dropbox client IDs live in
Nango.

``handle`` is a Dropbox path (``/folder/file.h5ad``) or a ``id:...`` file id. The content endpoint
takes the file reference in the ``Dropbox-API-Arg`` header and returns the raw body.
"""

from __future__ import annotations

import json

from cloud._stream import stream_http_to_store
from cloud.errors import CloudFetchError

_CONTENT_DOWNLOAD = "https://content.dropboxapi.com/2/files/download"


class DropboxConnector:
    def fetch_to_store(self, handle: str, token: str | None, key: str, max_bytes: int) -> int:
        if not token:
            raise CloudFetchError("Dropbox import needs a connected account (no token)")
        return stream_http_to_store(
            method="POST",
            url=_CONTENT_DOWNLOAD,
            key=key,
            max_bytes=max_bytes,
            headers={
                "Authorization": f"Bearer {token}",
                "Dropbox-API-Arg": json.dumps({"path": handle}),
            },
        )

    def push_from_store(self, key: str, dest: str, token: str | None) -> int:
        raise CloudFetchError("Dropbox export is not available yet")
