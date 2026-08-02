"""Dropbox connector. Streams a file's bytes into the object store using a Nango-brokered access
token, and streams an export back out. Dormant until ``SELOM_CLOUD_DROPBOX`` is on and the owner's
Dropbox client IDs live in Nango.

``handle`` is a Dropbox path (``/folder/file.h5ad``) or a ``id:...`` file id. The content endpoint
takes the file reference in the ``Dropbox-API-Arg`` header and returns the raw body.

Export (``push_path``) has two paths because the API forces it: ``/files/upload`` is capped at
**150 MB**, so anything larger goes through an **upload session** in chunks
(docs/cloud-export/spec.md D4). Neither path buffers the payload in memory. ``dest`` is a folder
**path**; empty means the App Folder root. Uploads use ``mode=add`` with ``autorename``, so an
export can never silently overwrite a user's file (spec R7).
"""

from __future__ import annotations

import json
import pathlib

from cloud._stream import stream_http_to_store
from cloud.errors import CloudFetchError

_CONTENT_DOWNLOAD = "https://content.dropboxapi.com/2/files/download"
_CONTENT_UPLOAD = "https://content.dropboxapi.com/2/files/upload"
_SESSION_START = "https://content.dropboxapi.com/2/files/upload_session/start"
_SESSION_APPEND = "https://content.dropboxapi.com/2/files/upload_session/append_v2"
_SESSION_FINISH = "https://content.dropboxapi.com/2/files/upload_session/finish"

#: Dropbox's documented ceiling for a single /files/upload call.
SIMPLE_UPLOAD_MAX = 150 * 1024 * 1024
#: Chunk size for the session path. 8 MiB keeps the request count sane without a large buffer.
_CHUNK = 8 * 1024 * 1024


def _dest_path(dest: str, filename: str) -> str:
    """Dropbox wants a full destination path with a leading slash; `dest` is the folder."""
    folder = (dest or "").strip().strip("/")
    return f"/{folder}/{filename}" if folder else f"/{filename}"


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
        from cloud.connectors.base import push_store_object_via_path

        return push_store_object_via_path(self, key, dest, token)

    def push_path(self, local_path, dest: str, token: str | None, *, filename: str,
                  transport=None) -> int:
        """Upload ``local_path`` to Dropbox folder ``dest`` as ``filename``.

        ``transport`` is a test seam (an ``httpx.MockTransport``); production passes ``None``.
        """
        import httpx

        if not token:
            raise CloudFetchError("Dropbox export needs a connected account (no token)")
        local = pathlib.Path(local_path)
        if not local.is_file():
            raise CloudFetchError(f"nothing to upload at {local}")
        size = local.stat().st_size
        path = _dest_path(dest, filename)
        auth = {"Authorization": f"Bearer {token}"}

        with httpx.Client(transport=transport, timeout=180.0, follow_redirects=True) as client:
            if size <= SIMPLE_UPLOAD_MAX:
                with local.open("rb") as fh:
                    resp = client.post(
                        _CONTENT_UPLOAD,
                        headers={
                            **auth,
                            "Content-Type": "application/octet-stream",
                            "Dropbox-API-Arg": json.dumps(
                                {"path": path, "mode": "add", "autorename": True,
                                 "mute": False, "strict_conflict": False}),
                        },
                        content=fh,
                    )
                if resp.status_code >= 400:
                    raise CloudFetchError(f"Dropbox upload failed (HTTP {resp.status_code})")
                return size

            # Over the single-call ceiling: session upload, one chunk at a time.
            with local.open("rb") as fh:
                first = fh.read(_CHUNK)
                start = client.post(
                    _SESSION_START,
                    headers={**auth, "Content-Type": "application/octet-stream",
                             "Dropbox-API-Arg": json.dumps({"close": False})},
                    content=first,
                )
                if start.status_code >= 400:
                    raise CloudFetchError(
                        f"Dropbox refused the upload session (HTTP {start.status_code})")
                try:
                    session_id = start.json()["session_id"]
                except (ValueError, KeyError) as exc:
                    raise CloudFetchError("Dropbox returned no upload session id") from exc

                offset = len(first)
                while chunk := fh.read(_CHUNK):
                    appended = client.post(
                        _SESSION_APPEND,
                        headers={**auth, "Content-Type": "application/octet-stream",
                                 "Dropbox-API-Arg": json.dumps(
                                     {"cursor": {"session_id": session_id, "offset": offset},
                                      "close": False})},
                        content=chunk,
                    )
                    if appended.status_code >= 400:
                        raise CloudFetchError(
                            f"Dropbox upload failed at offset {offset} "
                            f"(HTTP {appended.status_code})")
                    offset += len(chunk)

                finish = client.post(
                    _SESSION_FINISH,
                    headers={**auth, "Content-Type": "application/octet-stream",
                             "Dropbox-API-Arg": json.dumps(
                                 {"cursor": {"session_id": session_id, "offset": offset},
                                  "commit": {"path": path, "mode": "add", "autorename": True}})},
                )
                if finish.status_code >= 400:
                    raise CloudFetchError(
                        f"Dropbox could not finalise the upload (HTTP {finish.status_code})")
        return size
