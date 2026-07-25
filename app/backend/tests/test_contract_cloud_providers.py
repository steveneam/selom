"""Executable freeze on the ``GET /cloud/providers`` wire contract (next-session-plan P0-03).

This is the ONE surface two parallel worktree lanes share, so it is pinned on ``main`` before either
forks. The point is timing: a lane that "improves" the shared shape goes red **in its own run**, days
before the merge train would surface it as a semantic conflict — and hand-resolving contract drift at
the train, under merge pressure, is how wrong code ships behind a green gate.

**Filename is deliberate.** Lane 2 owns ``tests/test_cloud*.py``; this file is ``test_contract_*`` so
it sits OUTSIDE that glob. A lane editing its own freeze is then a visible scope breach rather than a
routine edit inside its own territory. A lane may ADD conformance tests in its own files; changing
what is asserted here is a re-plan, never a wave-through.

What is frozen: the key set, the key ORDER, the envelope, provider order, and the rule that
``enabled`` is the server's answer. See ``cloud/contract.py`` for the rationale behind each.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cloud.contract import (
    PROVIDER_KEYS,
    PROVIDERS_RESPONSE_KEY,
    provider_payload,
    providers_payload,
)
from cloud.registry import KIND_OAUTH, KIND_URL, get_provider, list_providers

# The FE's half of the contract. Resolved from this file so the guard breaks loudly if the module is
# moved rather than silently passing on a vanished file.
_FE_CONTRACT = (
    Path(__file__).resolve().parents[2] / "frontend" / "lib" / "cloud" / "contract.ts"
)


def _fe_contract_src() -> str:
    """Read the FE contract module, failing with a pointer rather than a bare FileNotFoundError."""
    assert _FE_CONTRACT.is_file(), (
        f"FE contract module missing at {_FE_CONTRACT} — the cross-language guard cannot run. "
        "If it moved, update this path; do not delete the guard."
    )
    return _FE_CONTRACT.read_text(encoding="utf-8")


class _FakeSettings:
    """Only the flags the registry reads. A fake (not the real singleton) so flag-state assertions
    cannot depend on whatever the developer happens to have in ``.env``."""

    def __init__(self, **flags: bool) -> None:
        self.cloud_google_enabled = flags.get("google", False)
        self.cloud_onedrive_enabled = flags.get("onedrive", False)
        self.cloud_dropbox_enabled = flags.get("dropbox", False)


# --------------------------------------------------------------------------- the frozen shape
def test_provider_wire_keys_are_frozen():
    """The literal key set + order. Adding, renaming, dropping or reordering a key lands here first."""
    assert PROVIDER_KEYS == ("id", "label", "kind", "provider_config_key", "enabled")
    assert PROVIDERS_RESPONSE_KEY == "providers"


def test_provider_payload_emits_exactly_the_frozen_keys():
    """Every registered provider serializes to exactly PROVIDER_KEYS — no extras, none missing, in
    order. Catches a lane leaking an internal field (a token, a flag name) onto the wire."""
    settings = _FakeSettings(google=True, dropbox=True)
    for provider in list_providers():
        payload = provider_payload(provider, settings)
        assert tuple(payload.keys()) == PROVIDER_KEYS, (
            f"{provider.id}: wire keys drifted from the freeze: {tuple(payload.keys())}"
        )


def test_envelope_is_an_object_wrapping_the_list():
    """Not a bare array — so the response can gain sibling metadata without breaking a live client."""
    body = providers_payload(_FakeSettings())
    assert isinstance(body, dict)
    assert list(body.keys()) == [PROVIDERS_RESPONSE_KEY]
    assert isinstance(body[PROVIDERS_RESPONSE_KEY], list)


def test_provider_order_is_server_owned_and_stable():
    """The list IS the FE's menu order, so it is frozen here rather than sorted on the client."""
    ids = [p["id"] for p in providers_payload(_FakeSettings())[PROVIDERS_RESPONSE_KEY]]
    assert ids == ["url", "google", "onedrive", "dropbox"]


# ------------------------------------------------------- values derive from the registry + settings
def test_static_fields_come_from_the_registry_not_a_literal():
    """id/label/kind/provider_config_key are the registry's, so the endpoint cannot drift from the
    table the import/export handlers actually dispatch on."""
    google = get_provider("google")
    assert google is not None
    payload = provider_payload(google, _FakeSettings(google=True))
    assert payload["id"] == google.id
    assert payload["label"] == google.label
    assert payload["kind"] == google.kind == KIND_OAUTH
    assert payload["provider_config_key"] == google.provider_config_key == "google-drive"


def test_enabled_is_the_servers_answer_and_tracks_the_flag():
    """The A20 fix, asserted: `enabled` follows the settings flag in BOTH directions. If this can be
    satisfied by a constant, the FE is back to guessing and the feature goes unreachable again."""
    google = get_provider("google")
    assert google is not None
    assert provider_payload(google, _FakeSettings(google=True))["enabled"] is True
    assert provider_payload(google, _FakeSettings(google=False))["enabled"] is False


def test_url_provider_is_always_enabled_and_carries_no_integration_key():
    url = get_provider("url")
    assert url is not None
    payload = provider_payload(url, _FakeSettings())
    assert payload["kind"] == KIND_URL
    assert payload["enabled"] is True, "URL/S3 has no OAuth flag — it is always on"
    assert payload["provider_config_key"] == ""


def test_no_credential_material_crosses_the_wire():
    """provider_config_key is a PUBLIC Nango integration id. Assert the serialized payload carries
    nothing token-shaped, so a lane cannot 'helpfully' add a client secret to light up a Connect
    button."""
    body = providers_payload(_FakeSettings(google=True, dropbox=True))
    flat = repr(body).lower()
    for forbidden in ("secret", "token", "client_id", "client_secret", "password", "credential"):
        assert forbidden not in flat, f"{forbidden!r} leaked into the providers payload"


# ------------------------------------------------------------------- cross-language drift (the fork)
def _fe_declared_wire_keys() -> list[str]:
    """Parse CLOUD_PROVIDER_WIRE_KEYS out of the FE contract module.

    A regex over TypeScript is crude, but the alternative is what A20 already cost us: two
    hand-maintained tables that agreed only by luck. The FE declaration is a flat list of string
    literals precisely so this stays a two-line parse.
    """
    src = _fe_contract_src()
    match = re.search(r"CLOUD_PROVIDER_WIRE_KEYS\s*=\s*\[(.*?)\]", src, re.DOTALL)
    assert match, "CLOUD_PROVIDER_WIRE_KEYS array literal not found in the FE contract module"
    return re.findall(r"""['"]([^'"]+)['"]""", match.group(1))


def test_frontend_declares_the_same_wire_keys_in_the_same_order():
    """The actual A20 guard: BE and FE declarations must agree. Either side drifting fails here."""
    assert _fe_declared_wire_keys() == list(PROVIDER_KEYS), (
        "FE/BE provider wire keys have diverged — this is the fork the contract exists to prevent"
    )


def test_frontend_declares_the_same_envelope_key():
    src = _fe_contract_src()
    match = re.search(r"""CLOUD_PROVIDERS_RESPONSE_KEY\s*=\s*['"]([^'"]+)['"]""", src)
    assert match, "CLOUD_PROVIDERS_RESPONSE_KEY not found in the FE contract module"
    assert match.group(1) == PROVIDERS_RESPONSE_KEY


# ------------------------------------------------------------------------- the route, once it exists
def test_route_conforms_to_the_freeze_once_implemented():
    """Dormant until Lane 2 (L2-01) adds the route, then a real end-to-end conformance check with no
    further wiring. It asserts the ROUTE's bytes, not just the serializer, so an endpoint that
    bypasses ``providers_payload`` and hand-rolls its own dict is still caught."""
    from fastapi.testclient import TestClient

    from main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    if "/cloud/providers" not in paths:
        pytest.skip("GET /cloud/providers not implemented yet — tracked as L2-01; this activates then")

    body = TestClient(app).get("/cloud/providers").json()
    assert list(body.keys()) == [PROVIDERS_RESPONSE_KEY]
    assert body[PROVIDERS_RESPONSE_KEY], "the registry always has at least the url provider"
    for row in body[PROVIDERS_RESPONSE_KEY]:
        assert tuple(row.keys()) == PROVIDER_KEYS
        assert isinstance(row["enabled"], bool)
        assert row["kind"] in (KIND_URL, KIND_OAUTH)
