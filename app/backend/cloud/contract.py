"""The FROZEN ``GET /cloud/providers`` wire contract — the one cross-lane surface.

Why this module exists (next-session-plan P0-03). The FE and BE each kept their own provider table:
``cloud/registry.py`` here and ``lib/cloud/providers.ts`` there, with the FE hardcoding
``comingSoon: true`` because nothing told it otherwise. Both OAuth providers are live and connected,
yet the feature is unreachable — the FE cannot know a provider is enabled, so it refuses to offer it
(review finding A20, [[selom-shipped-not-reachable]]). One endpoint fed by the registry kills the
fork: the server owns provider state, the FE renders what it is told.

This shape is FROZEN. It is the only contract two parallel worktree lanes share, so it ships pinned
on ``main`` before either forks, and drift is caught by an executable guard
(``tests/test_contract_cloud_providers.py``) rather than at the merge train — where a semantic
conflict hand-resolved under merge pressure is how wrong code ships behind a green gate.

    GET /cloud/providers  ->  200
    {
      "providers": [
        {"id": "url",      "label": "URL / S3",     "kind": "url",   "provider_config_key": "",             "enabled": true},
        {"id": "google",   "label": "Google Drive", "kind": "oauth", "provider_config_key": "google-drive", "enabled": true},
        {"id": "onedrive", "label": "OneDrive",     "kind": "oauth", "provider_config_key": "onedrive",     "enabled": false},
        {"id": "dropbox",  "label": "Dropbox",      "kind": "oauth", "provider_config_key": "dropbox",      "enabled": true}
      ]
    }

Rules that make it a contract rather than a suggestion:

* **Keys are exact.** Exactly :data:`PROVIDER_KEYS`, in that order, no more and no fewer. Adding a
  key is a contract change, which is a re-plan — never a wave-through.
* **Order is part of the shape.** The list is the FE's menu order, so it is server-owned and stable
  (:func:`cloud.registry.list_providers`). The FE must not re-sort.
* **``enabled`` is the server's answer, never the client's guess.** It is
  :func:`cloud.registry.is_enabled` — ``url`` always on, an OAuth provider on only when its settings
  flag is set. The FE renders a disabled affordance from this field; it must not carry its own
  ``comingSoon`` truth.
* **No secrets cross this line.** ``provider_config_key`` is a Nango *integration id* (public, e.g.
  ``google-drive``), not a key or token. Nothing here is credential material.
* **Unknown keys are additive-safe for the FE.** The FE maps the keys it knows and ignores the rest,
  so a future additive field cannot break a deployed client.
"""

from __future__ import annotations

from typing import Any

from cloud.registry import Provider, is_enabled, list_providers

#: The response envelope key. The payload is an OBJECT, not a bare array, so the response can gain
#: sibling metadata later without breaking a deployed client.
PROVIDERS_RESPONSE_KEY = "providers"

#: The frozen per-provider wire keys, in wire order. Snake_case: this is the wire, and the FE maps to
#: camelCase at its boundary (the house style — see ``lib/cloud/api.ts``).
PROVIDER_KEYS: tuple[str, ...] = ("id", "label", "kind", "provider_config_key", "enabled")


def provider_payload(provider: Provider, settings: Any) -> dict[str, Any]:
    """Serialize ONE provider to the frozen wire shape.

    The endpoint MUST build its response through this function rather than assembling dicts inline —
    that is what keeps the guard test's key assertion meaningful instead of testing a copy of the
    shape that the route does not actually use.
    """
    return {
        "id": provider.id,
        "label": provider.label,
        "kind": provider.kind,
        "provider_config_key": provider.provider_config_key,
        "enabled": is_enabled(provider, settings),
    }


def providers_payload(settings: Any) -> dict[str, Any]:
    """Serialize the FULL ``GET /cloud/providers`` response body."""
    return {PROVIDERS_RESPONSE_KEY: [provider_payload(p, settings) for p in list_providers()]}
