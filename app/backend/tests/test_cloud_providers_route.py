"""``GET /cloud/providers`` + ``GET /cloud/connections`` — the surface that makes cloud import
reachable (L2-01).

The frozen wire SHAPE is asserted in ``tests/test_contract_cloud_providers.py`` (outside this lane's
glob, deliberately). What is asserted here is the lane's own half: the route exists, it answers from
the registry + live settings rather than a literal, and the connections listing keys Nango's
``provider_config_key`` back onto the registry id without ever leaking a token.

Why the two endpoints are separate: ``enabled`` says the SERVER will accept a provider; a connection
says an ACCOUNT is on the other end. A UI that conflates them either offers an import form that
cannot succeed, or hides a provider that is ready — both were the A20 failure mode.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from auth.context import AuthContext, get_verifier
from cloud import registry
from cloud.errors import CloudFetchError


class _Verifier:
    def verify(self, request) -> AuthContext:  # noqa: ARG002
        return AuthContext(user_id="A", email="a@x.com")


@pytest.fixture
def client():
    from main import app

    app.dependency_overrides[get_verifier] = lambda: _Verifier()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_verifier, None)


# ------------------------------------------------------------------------------ GET /cloud/providers
def test_providers_route_is_registered_and_lists_every_registered_provider(client):
    r = client.get("/cloud/providers")
    assert r.status_code == 200, r.text
    ids = [p["id"] for p in r.json()["providers"]]
    assert ids == [p.id for p in registry.list_providers()]


def test_providers_route_needs_no_auth_header(client):
    """The menu must render before a user has done anything, and the body carries no tenant data.

    Asserted explicitly so a later "harden everything" sweep cannot quietly gate the provider menu
    behind a token and put the feature back out of reach.
    """
    from main import app

    app.dependency_overrides.pop(get_verifier, None)
    assert TestClient(app).get("/cloud/providers").status_code == 200


def test_enabled_tracks_the_live_settings_flag_through_the_route(monkeypatch):
    """`enabled` is the SERVER's answer end-to-end — not just in the serializer. Flipping the real
    settings flag must change the route's bytes, or the FE is back to guessing (A20)."""
    from main import app
    import routers.cloud as cloud_router

    def google(body) -> bool:
        return next(p["enabled"] for p in body["providers"] if p["id"] == "google")

    client = TestClient(app)
    monkeypatch.setattr(cloud_router.settings, "cloud_google_enabled", False, raising=False)
    assert google(client.get("/cloud/providers").json()) is False
    monkeypatch.setattr(cloud_router.settings, "cloud_google_enabled", True, raising=False)
    assert google(client.get("/cloud/providers").json()) is True


# ---------------------------------------------------------------------------- GET /cloud/connections
_NANGO_ROWS = [
    {
        "connection_id": "c878e8db-ab37-40ed-9866-ba458d12a7df",
        "provider_config_key": "google-drive",
        "end_user": {"display_name": "Steven", "email": "owner@example.test"},
        "created": "2026-07-25T05:39:09.594+00:00",
    },
    {
        "connection_id": "5f45a106-7469-42c0-9fc0-cba40968e4a4",
        "provider_config_key": "dropbox",
        "end_user": {},
        "created": "2026-07-25T05:39:09.594+00:00",
    },
    # An integration Selom does not register — must not reach the client.
    {"connection_id": "zzz", "provider_config_key": "salesforce", "end_user": {}},
]


def test_connections_are_keyed_by_registry_id_and_labelled(client, monkeypatch):
    import routers.cloud as cloud_router

    monkeypatch.setattr(cloud_router.nango, "list_connections", lambda: list(_NANGO_ROWS))
    monkeypatch.setattr(cloud_router.settings, "cloud_google_enabled", True, raising=False)
    monkeypatch.setattr(cloud_router.settings, "cloud_dropbox_enabled", True, raising=False)

    rows = client.get("/cloud/connections").json()["connections"]
    by_provider = {r["provider"]: r for r in rows}
    assert set(by_provider) == {"google", "dropbox"}, "an unregistered integration leaked through"
    assert by_provider["google"]["connection_id"] == "c878e8db-ab37-40ed-9866-ba458d12a7df"
    assert by_provider["google"]["label"] == "Steven (owner@example.test)"
    # No end_user → the connection id's prefix, never an invented name.
    assert by_provider["dropbox"]["label"] == "5f45a106"


def test_a_connection_for_a_disabled_provider_is_not_offered(client, monkeypatch):
    """Its import would be refused by the flag gate, so showing it would be an affordance that
    cannot succeed."""
    import routers.cloud as cloud_router

    monkeypatch.setattr(cloud_router.nango, "list_connections", lambda: list(_NANGO_ROWS))
    monkeypatch.setattr(cloud_router.settings, "cloud_google_enabled", False, raising=False)
    monkeypatch.setattr(cloud_router.settings, "cloud_dropbox_enabled", True, raising=False)

    providers = {r["provider"] for r in client.get("/cloud/connections").json()["connections"]}
    assert providers == {"dropbox"}


def test_no_credential_material_crosses_the_connections_wire(client, monkeypatch):
    """A connection id names a grant; it is not the grant. Nothing token-shaped may ride along."""
    import routers.cloud as cloud_router

    leaky = [dict(_NANGO_ROWS[0], credentials={"access_token": "ya29.SECRET"})]
    monkeypatch.setattr(cloud_router.nango, "list_connections", lambda: leaky)
    monkeypatch.setattr(cloud_router.settings, "cloud_google_enabled", True, raising=False)

    flat = client.get("/cloud/connections").text.lower()
    for forbidden in ("access_token", "credential", "secret", "refresh_token", "ya29"):
        assert forbidden not in flat, f"{forbidden!r} leaked into the connections payload"


def test_nango_unreachable_is_a_502_the_caller_can_degrade_on(client, monkeypatch):
    """Fail-soft belongs to the caller: the account section degrades with a visible message while
    the URL/S3 import — which needs no broker — keeps working."""
    import routers.cloud as cloud_router

    def boom():
        raise CloudFetchError("could not reach Nango: connect timeout")

    monkeypatch.setattr(cloud_router.nango, "list_connections", boom)
    r = client.get("/cloud/connections")
    assert r.status_code == 502
    assert "Nango" in r.json()["detail"]
