"""Thin server-side client for the self-hosted Nango (deploy/nango/) — just enough to exchange a
Connect **connection id** for the provider's live **access token**, which the OAuth connectors then
use to stream a file, and to list which accounts are connected. Nango holds + refreshes the OAuth
credentials; Selom never stores a provider token.

Endpoints (Nango Connections API):
    GET {NANGO_SERVER_URL}/connection/{connection_id}?provider_config_key={key}&refresh_token=true
    Authorization: Bearer {NANGO_SECRET_KEY}
→ ``{"credentials": {"access_token": "..."}, ...}``  (Nango refreshes the token if near expiry).

    GET {NANGO_SERVER_URL}/connections
→ ``{"connections": [{"connection_id": ..., "provider_config_key": ..., "end_user": {...}}, ...]}``

**Two Nango instances exist and confusing them costs a diagnosis** — the LIVE one is
``https://nango.swordfish.cfd`` (what ``SELOM_NANGO_BASE_URL`` points at); a local ``:3003`` dev
stack shares nothing with it and a key from one returns ``unknown_account`` on the other. Run
``bash deploy/nango/preflight.sh`` (exit-code gated) before trusting anything here.
"""

from __future__ import annotations

from typing import Any

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


def list_connections() -> list[dict[str, Any]]:
    """Every account connected in Nango, as raw ``{connection_id, provider_config_key, end_user}``.

    Why the server has to answer this: a connection id is a Nango-minted UUID, so a user cannot
    know it and the client cannot guess it. Without this the import form would have to ask a human
    to paste a UUID — which is another way of saying the feature is unreachable
    (``docs/reachability/backlog.md``). Carries no credential material: a connection id names a
    grant, it is not the grant.
    """
    import httpx

    from config import settings

    if not settings.nango_secret_key:
        raise ProviderNotConfigured(
            "Nango is not configured (set SELOM_NANGO_SECRET_KEY) — connect a provider first"
        )
    url = f"{settings.nango_base_url.rstrip('/')}/connections"
    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {settings.nango_secret_key}"},
            timeout=settings.nango_timeout_s,
        )
    except httpx.HTTPError as exc:
        raise CloudFetchError(f"could not reach Nango: {exc}") from exc
    if resp.status_code >= 400:
        raise CloudFetchError(f"Nango returned HTTP {resp.status_code} listing connections")
    rows = resp.json().get("connections")
    if not isinstance(rows, list):
        raise CloudFetchError("Nango response carried no connections list")
    return [r for r in rows if isinstance(r, dict)]
