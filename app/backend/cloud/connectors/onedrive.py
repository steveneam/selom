"""OneDrive / Microsoft Graph connector (scaffold). Streams a drive item's content into the object
store using a Nango-brokered access token. Dormant until ``SELOM_CLOUD_ONEDRIVE`` is on and the
owner's Microsoft client IDs live in Nango.

``handle`` is a Graph drive-item id. ``/content`` 302s to a short-lived download URL; the shared
helper follows the redirect (a trusted Microsoft CDN host).
"""

from __future__ import annotations

from cloud._stream import stream_http_to_store
from cloud.errors import CloudFetchError

_GRAPH_CONTENT = "https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/content"


class OneDriveConnector:
    def fetch_to_store(self, handle: str, token: str | None, key: str, max_bytes: int) -> int:
        if not token:
            raise CloudFetchError("OneDrive import needs a connected account (no token)")
        return stream_http_to_store(
            method="GET",
            url=_GRAPH_CONTENT.format(item_id=handle),
            key=key,
            max_bytes=max_bytes,
            headers={"Authorization": f"Bearer {token}"},
        )

    def push_from_store(self, key: str, dest: str, token: str | None) -> int:
        raise CloudFetchError("OneDrive export is not available yet")

    def push_path(self, local_path, dest: str, token: str | None, *, filename: str) -> int:
        # Still scaffolded: OneDrive is on the DEFERRED list until a machine logs into Azure
        # cleanly (docs/cloud-export/spec.md D5). Google + Dropbox are implemented.
        raise CloudFetchError("OneDrive export is not available yet")
