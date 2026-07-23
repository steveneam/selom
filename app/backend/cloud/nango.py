"""Thin server-side client for the self-hosted Nango (deploy/nango/) — just enough to exchange a
Connect **connection id** for the provider's live **access token**, which the OAuth connectors then
use to stream a file. Nango holds + refreshes the OAuth credentials; Selom never stores a provider
token.

Endpoint (Nango Connections API):
    GET {NANGO_SERVER_URL}/connection/{connection_id}?provider_config_key={key}&refresh_token=true
    Authorization: Bearer {NANGO_SECRET_KEY}
→ ``{"credentials": {"access_token": "..."}, ...}``  (Nango refreshes the token if near expiry).
"""

from __future__ import annotations

from cloud.errors import CloudFetchError, ProviderNotConfigured


def get_access_token(connection_id: str, provider_config_key: str) -> str:
    """Return the live access token for a Nango connection. Raises ``ProviderNotConfigured`` when the
    Nango secret key isn't set (nothing is wired yet), ``CloudFetchError`` on a Nango/API failure or a
    response without an access token."""
    import httpx

    from config import settings

    if not settings.nango_secret_key:
        raise ProviderNotConfigured(
            "Nango is not configured (set SELOM_NANGO_SECRET_KEY) — connect a provider first"
        )
    if not connection_id:
        raise CloudFetchError("missing Nango connection id")

    url = f"{settings.nango_base_url.rstrip('/')}/connection/{connection_id}"
    try:
        resp = httpx.get(
            url,
            params={"provider_config_key": provider_config_key, "refresh_token": "true"},
            headers={"Authorization": f"Bearer {settings.nango_secret_key}"},
            timeout=settings.nango_timeout_s,
        )
    except httpx.HTTPError as exc:
        raise CloudFetchError(f"could not reach Nango: {exc}") from exc
    if resp.status_code >= 400:
        raise CloudFetchError(f"Nango returned HTTP {resp.status_code} for connection {connection_id!r}")
    token = (resp.json().get("credentials") or {}).get("access_token")
    if not token:
        raise CloudFetchError("Nango response carried no access_token")
    return str(token)
