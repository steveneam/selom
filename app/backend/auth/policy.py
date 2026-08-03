"""Deny-by-default route authorization — the public allow-list (auth-multitenancy spec D2).

WHY THIS EXISTS. The audit that found the gap worked by *searching for what was missing*: it read
every route and asked "does this one take an ``AuthContext``?". 39 of 78 did not. That method finds
today's holes and is guaranteed to miss tomorrow's, because a new route is born unprotected and
nothing complains.

So the rule is inverted here. :func:`enforce_auth` is attached ONCE, to the app, and runs for every
route. A route is **private unless its (method, path) is written down below** — which moves the
invariant from a documentary "remember to add ``require_user``" up to the structural rung of the
ratchet ladder. Adding a public route becomes a deliberate, reviewable act, and
``tests/test_route_authorization.py`` fails on any route that is neither listed here nor private.

WHY THIS CHANGES NOTHING LOCALLY. In ``dev`` mode the verifier is ``DevVerifier``, whose ``verify``
returns a fixed tenant and never raises. So enforcing auth on every route is a no-op for the inner
loop, ``verify.sh`` and ``browser-verify.sh`` (spec D3) — the enforcement only bites under
``SELOM_AUTH_MODE=clerk``, which is what the deployed app sets and what the isolation test drives.

WHAT THIS DOES *NOT* DO. Authentication is not authorization. This makes a caller prove *who they
are* on a private route; it does not stop tenant A from reading tenant B's row by id. That is the
separate scoping work (spec §4 step 2) — see ``engine/lineage.py``'s tenant-prefixed keys.
"""

from __future__ import annotations

from fastapi import Depends, Request

from auth.context import AuthContext, AuthVerifier, get_verifier

# The public set, stated once (spec D2). Each entry is (METHOD, route path template) — the template,
# not the concrete URL, so "/papers/{slug}" covers every slug and cannot be widened by a crafted path.
#
# The test for "is this really public?" is: it returns the SAME bytes for every caller, and holds no
# tenant data. Anything that reads or writes a user's own row belongs off this list.
PUBLIC_ROUTES: frozenset[tuple[str, str]] = frozenset({
    # Liveness — must answer without a token or the platform cannot health-check the service.
    ("GET", "/health"),
    ("GET", "/ready"),
    # The skill catalog is product surface: identical for everyone, no tenant data.
    # NOTE: POST /skills/{id}/run is deliberately NOT here — running a skill is compute.
    ("GET", "/skills"),
    ("GET", "/skills/{skill_id}"),
    # The frozen provider contract — server-owned capability advertisement, no tenant data.
    ("GET", "/cloud/providers"),
    # Static reference data for the export/style pickers.
    ("GET", "/figures/export/presets"),
    ("GET", "/figures/styles"),
    # External bibliographic lookups — they proxy a public index and store nothing per tenant.
    ("GET", "/citations/search"),
    ("GET", "/citations/by-doi"),
    ("GET", "/papers/metadata/by-doi"),
    # The CURATED reproduction catalog shipped with the product — not user papers. A user's own
    # papers live under /workspace/papers, which is authenticated. If these ever start carrying
    # per-tenant content they move off this list (spec D2).
    ("GET", "/papers"),
    ("GET", "/papers/{slug}"),
    ("GET", "/papers/{slug}/scorecard"),
    ("GET", "/papers/{slug}/methods"),
    ("GET", "/papers/{slug}/legends"),
})


def route_key(request: Request) -> tuple[str, str]:
    """``(METHOD, path template)`` for the matched route, falling back to the raw path.

    The template comes from the route FastAPI actually matched, so the lookup cannot be fooled by
    path tricks (encoded separators, a crafted id that reads like a literal segment) — an unmatched
    request has no template, falls back to its raw path, misses the allow-list, and is therefore
    treated as private. Failing closed is the point.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None) or request.url.path
    return (request.method.upper(), path)


def is_public(request: Request) -> bool:
    """True when the matched route is on the allow-list. HEAD rides with GET (Starlette answers HEAD
    from the GET route), and OPTIONS is the CORS preflight, which carries no credentials by design."""
    method, path = route_key(request)
    if method == "OPTIONS":
        return True
    if method == "HEAD":
        method = "GET"
    return (method, path) in PUBLIC_ROUTES


async def enforce_auth(
    request: Request, verifier: AuthVerifier = Depends(get_verifier)
) -> AuthContext | None:
    """App-level dependency: verify the caller on every route that is not on the allow-list.

    The resolved context is cached on ``request.state`` so a handler's own ``require_user`` reuses
    it instead of verifying the JWT a second time on the same request.
    """
    if is_public(request):
        return None
    ctx = verifier.verify(request)
    request.state.auth = ctx
    return ctx
