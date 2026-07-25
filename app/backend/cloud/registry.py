"""Provider registry — the single table the import/export endpoints read so they never branch on
provider identity. Each provider declares its kind (``url`` vs ``oauth``), the Nango integration id
its OAuth token comes from, and the settings flag that gates it. ``url`` is always on; an ``oauth``
provider lights up only when its flag is set (i.e. the owner added client IDs to Nango).
"""

from __future__ import annotations

from dataclasses import dataclass

from cloud.connectors.base import CloudConnector
from cloud.connectors.dropbox import DropboxConnector
from cloud.connectors.google import GoogleDriveConnector
from cloud.connectors.onedrive import OneDriveConnector
from cloud.connectors.url import UrlConnector

KIND_URL = "url"
KIND_OAUTH = "oauth"


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    kind: str                    # KIND_URL | KIND_OAUTH
    provider_config_key: str     # Nango integration id (oauth only) — must match the owner's Nango setup
    flag: str | None             # Settings attribute gating it (oauth only); None ⇒ always enabled


_PROVIDERS: dict[str, Provider] = {
    "url": Provider("url", "URL / S3", KIND_URL, "", None),
    "google": Provider("google", "Google Drive", KIND_OAUTH, "google-drive", "cloud_google_enabled"),
    "onedrive": Provider("onedrive", "OneDrive", KIND_OAUTH, "onedrive", "cloud_onedrive_enabled"),
    "dropbox": Provider("dropbox", "Dropbox", KIND_OAUTH, "dropbox", "cloud_dropbox_enabled"),
}

# Connector instances are stateless singletons. A test seam (mirrors set_object_store) lets a test
# swap the ``url`` connector for one backed by an httpx MockTransport.
_CONNECTORS: dict[str, CloudConnector] = {
    "url": UrlConnector(),
    "google": GoogleDriveConnector(),
    "onedrive": OneDriveConnector(),
    "dropbox": DropboxConnector(),
}


def get_provider(provider_id: str) -> Provider | None:
    return _PROVIDERS.get(provider_id)


def list_providers() -> list[Provider]:
    """Every registered provider, in declaration order.

    Declaration order IS the FE's menu order — it crosses the wire via ``GET /cloud/providers`` and
    the client renders it as given rather than re-sorting (``cloud.contract``). Returns a new list so
    a caller cannot mutate the registry.
    """
    return list(_PROVIDERS.values())


def provider_for_config_key(provider_config_key: str) -> Provider | None:
    """Reverse lookup: a Nango integration id → the registered provider it belongs to.

    Nango speaks ``provider_config_key`` (``google-drive``); Selom speaks the registry id
    (``google``). One table owns the mapping in both directions so a connection listing can be
    keyed the way the rest of the API is, without a second lookup table on the client.
    """
    if not provider_config_key:
        return None
    for provider in _PROVIDERS.values():
        if provider.provider_config_key == provider_config_key:
            return provider
    return None


def get_connector(provider_id: str) -> CloudConnector | None:
    return _CONNECTORS.get(provider_id)


def set_connector(provider_id: str, connector: CloudConnector) -> None:
    """Test seam — inject a connector (e.g. a MockTransport-backed ``UrlConnector``)."""
    _CONNECTORS[provider_id] = connector


def is_enabled(provider: Provider, settings) -> bool:
    """URL/S3 is always on; an OAuth provider is on only when its feature flag is set."""
    if provider.kind == KIND_URL:
        return True
    return bool(getattr(settings, provider.flag, False)) if provider.flag else False
