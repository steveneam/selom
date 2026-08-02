"""Google Drive connector. Streams a Drive file's raw bytes into the object store using a
Nango-brokered access token, and streams an export back out. Dormant until ``SELOM_CLOUD_GOOGLE`` is
on and the owner's Google client IDs live in Nango (the registry refuses the provider before this is
reached while the flag is off).

``handle`` is a Drive file id. Raw binaries (h5ad/csv/…) download via ``alt=media``; native Google
Docs/Sheets would need the ``/export`` endpoint (out of scope for the foundation slice).

Export (``push_path``) uses Drive's **resumable** upload: a session is opened with the file
metadata, then the bytes are streamed to the returned session URI. This is the documented path for
anything non-trivial and it uploads from the file handle, so a large dataset never lands in the
process heap (docs/cloud-export/spec.md D4). ``dest`` is a Drive **folder id**; empty means ``root``
(the user's My Drive). Files are always **created**, never updated, so an export cannot overwrite
something the user already has (spec R7).
"""

from __future__ import annotations

import json
import mimetypes
import pathlib

from cloud._stream import stream_http_to_store
from cloud.errors import CloudFetchError

_DRIVE_MEDIA = "https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true"
_DRIVE_RESUMABLE = (
    "https://www.googleapis.com/upload/drive/v3/files"
    "?uploadType=resumable&supportsAllDrives=true"
)


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
        from cloud.connectors.base import push_store_object_via_path

        return push_store_object_via_path(self, key, dest, token)

    def push_path(self, local_path, dest: str, token: str | None, *, filename: str,
                  transport=None) -> int:
        """Upload ``local_path`` into Drive folder ``dest`` as ``filename``.

        ``transport`` is a test seam (an ``httpx.MockTransport``); production passes ``None``.
        """
        import httpx

        if not token:
            raise CloudFetchError("Google Drive export needs a connected account (no token)")
        local = pathlib.Path(local_path)
        if not local.is_file():
            raise CloudFetchError(f"nothing to upload at {local}")
        size = local.stat().st_size
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # A folder id, or My Drive when the caller did not choose one. "/" and "root" both mean
        # the drive root -- accepting them keeps the FE from having to special-case an empty pick.
        folder = (dest or "").strip().strip("/")
        parents = [] if folder in ("", "root") else [folder]
        metadata = {"name": filename}
        if parents:
            metadata["parents"] = parents

        with httpx.Client(transport=transport, timeout=120.0, follow_redirects=True) as client:
            # 1. Open the resumable session. Drive returns the upload URI in the Location header.
            start = client.post(
                _DRIVE_RESUMABLE,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": ctype,
                    "X-Upload-Content-Length": str(size),
                },
                content=json.dumps(metadata).encode("utf-8"),
            )
            if start.status_code >= 400:
                raise CloudFetchError(
                    f"Google Drive refused the upload session (HTTP {start.status_code})")
            session_uri = start.headers.get("location") or start.headers.get("Location")
            if not session_uri:
                raise CloudFetchError("Google Drive returned no resumable session URI")

            # 2. Stream the bytes to the session URI. Passing the open file handle as content keeps
            #    httpx reading in chunks rather than materialising the payload (spec R6).
            with local.open("rb") as fh:
                put = client.put(
                    session_uri,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": ctype,
                        "Content-Length": str(size),
                    },
                    content=fh,
                )
            if put.status_code >= 400:
                raise CloudFetchError(f"Google Drive upload failed (HTTP {put.status_code})")
        return size
