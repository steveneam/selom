"""Google Drive connector (scaffold). Streams a Drive file's raw bytes into the object store using a
Nango-brokered access token. Dormant until ``SELOM_CLOUD_GOOGLE`` is on and the owner's Google client
IDs live in Nango (the registry refuses the provider before this is reached while the flag is off).

``handle`` is a Drive file id. Raw binaries (h5ad/csv/…) download via ``alt=media``; native Google
Docs/Sheets would need the ``/export`` endpoint (out of scope for the foundation slice).
"""

from __future__ import annotations

from cloud._stream import stream_http_to_store
from cloud.errors import CloudFetchError

_DRIVE_MEDIA = "https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true"


class GoogleDriveConnector:
    def fetch_to_store(self, handle: str, token: str | None, key: str, max_bytes: int) -> int:
        if not token:
            raise CloudFetchError("Google Drive import needs a connected account (no token)")
        return stream_http_to_store(
            method="GET",
            url=_DRIVE_MEDIA.format(file_id=handle),
            key=key,
            max_bytes=max_bytes,
            headers={"Authorization": f"Bearer {token}"},
        )

    def push_from_store(self, key: str, dest: str, token: str | None) -> int:
        raise CloudFetchError("Google Drive export is not available yet")
