"""Deny-by-default route authorization — the guard behind `auth/policy.py` (spec D2 / §4 step 1).

The audit that found this gap searched for what was MISSING (which routes lack an `AuthContext`).
That method finds today's holes and misses tomorrow's. These tests invert it: every route the app
serves must be *classified*, the allow-list may not contain routes that no longer exist, and a
private route must actually 401 without a token in `clerk` mode.

Same shape as `test_reachability_guard.py`: enumerate from the app itself, so a new route joins the
guard automatically instead of relying on someone remembering.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from auth.context import AuthContext, get_verifier
from auth.policy import PUBLIC_ROUTES, is_public
from main import app

# Routes FastAPI/Starlette mounts for itself — not Selom surface, never tenant data.
_FRAMEWORK_PATHS = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


def _app_routes() -> list[tuple[str, str]]:
    """Every (METHOD, path template) the app actually serves — read off the app, not a doc."""
    out: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in _FRAMEWORK_PATHS:
            continue
        for method in route.methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            out.append((method, route.path))
    return sorted(set(out))


def test_the_allow_list_has_no_stale_entries():
    """A public entry for a route that no longer exists is dead config that quietly grants nothing
    today and could grant the wrong thing when a path is reused."""
    served = set(_app_routes())
    stale = sorted(PUBLIC_ROUTES - served)
    assert not stale, f"allow-list names routes the app does not serve: {stale}"


def test_a_brand_new_route_is_born_private():
    """The property the whole inversion exists for, proved rather than asserted by construction:
    mount a route nobody wrote down, and it must demand a token.

    This is what a "remember to add require_user" convention cannot give you — the previous design
    would have served this new route to anyone, silently."""
    from fastapi import APIRouter

    probe = APIRouter()

    @probe.get("/__probe_brand_new_route")
    def _probe():
        return {"ok": True}

    app.include_router(probe)
    app.dependency_overrides[get_verifier] = lambda: _RejectingVerifier()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/__probe_brand_new_route")
        assert resp.status_code == 401, (
            "a route added without touching the allow-list answered unauthenticated — "
            "deny-by-default is not in force"
        )
    finally:
        app.dependency_overrides.pop(get_verifier, None)
        app.routes[:] = [r for r in app.routes
                         if getattr(r, "path", None) != "/__probe_brand_new_route"]


def test_the_public_set_stays_small_and_named():
    """Every public route is one someone wrote down, and the list is short enough to read. The
    allow-list growing quietly is the failure mode that would undo this."""
    assert PUBLIC_ROUTES <= set(_app_routes())
    assert len(PUBLIC_ROUTES) <= 20, (
        f"{len(PUBLIC_ROUTES)} public routes — if this is genuinely right, raise the bound "
        f"deliberately; it exists so the set cannot creep."
    )


def test_no_route_that_writes_is_public():
    """A mutation can never be public. Cheap, absolute, and it would have caught
    `PUT /uploads/local/{key:path}` had that ever been proposed for the list."""
    writes = sorted((m, p) for m, p in PUBLIC_ROUTES if m in ("POST", "PUT", "PATCH", "DELETE"))
    assert not writes, f"mutating routes on the public allow-list: {writes}"


@pytest.mark.parametrize("path", [
    "/artifacts/{artifact_id}",
    "/artifacts/{artifact_id}/table",
    "/reproduction-runs/{run_id}",
    "/reproduction-runs/{run_id}/events",
    "/skills/{skill_id}/run",
    "/data/inspect",
    "/data/combine",
    "/data/assemble-scrna",
    "/extract/chart",
    "/figures/export",
    "/papers/{paper_id}/reproduce",
    "/papers/{paper_id}/assess-data",
])
def test_the_named_holes_are_private(path):
    """The specific routes §1 of the spec called out. Named individually so a well-meaning future
    edit that adds one back to the allow-list fails with the route's own name."""
    served = {p for _m, p in _app_routes()}
    assert path in served, f"{path} is no longer served — update this guard"
    assert not any(p == path for _m, p in PUBLIC_ROUTES), f"{path} must not be public"


def test_uploads_local_put_is_private():
    """The dev-only presigned-PUT stand-in. It accepts any key under uploads/ — including another
    tenant's prefix — so it must never be reachable without a verified caller."""
    assert not any(p.startswith("/uploads/local") for _m, p in PUBLIC_ROUTES)


# --- behaviour, not just classification ----------------------------------------------------------
class _RejectingVerifier:
    """Stands in for ClerkVerifier with no valid token: every verify is a 401."""

    def verify(self, request):  # noqa: ARG002 — signature is the Protocol's
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="authentication required")


@pytest.fixture
def unauthenticated():
    """The app as a caller with no credentials sees it under `clerk` mode."""
    app.dependency_overrides[get_verifier] = lambda: _RejectingVerifier()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.pop(get_verifier, None)


@pytest.mark.parametrize("method,path", [
    ("GET", "/artifacts/abc123"),
    ("GET", "/artifacts/abc123/table"),
    ("GET", "/reproduction-runs/r1"),
    ("POST", "/data/inspect"),
    ("POST", "/extract/chart"),
])
def test_private_routes_401_without_a_token(unauthenticated, method, path):
    """The enforcement is REAL, not just declared: these answered anyone before this change."""
    resp = unauthenticated.request(method, path)
    assert resp.status_code == 401, f"{method} {path} answered {resp.status_code} unauthenticated"


@pytest.mark.parametrize("path", ["/health", "/ready", "/skills", "/cloud/providers"])
def test_public_routes_still_answer_without_a_token(unauthenticated, path):
    """Deny-by-default must not take the liveness probes and the catalog down with it."""
    resp = unauthenticated.get(path)
    assert resp.status_code != 401, f"{path} is on the allow-list but demanded a token"


def test_dev_mode_is_unaffected():
    """Spec D3: the whole point of the dev verifier is that turning this on changes nothing locally.
    A fixed-tenant verifier never raises, so a private route answers exactly as it did before."""

    class _DevLike:
        def verify(self, request):  # noqa: ARG002
            return AuthContext(user_id="dev-user", email="dev@example.com", claims={"mode": "dev"})

    app.dependency_overrides[get_verifier] = lambda: _DevLike()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            assert client.get("/artifacts/does-not-exist").status_code == 404  # not 401
    finally:
        app.dependency_overrides.pop(get_verifier, None)


def test_is_public_fails_closed_on_an_unmatched_request():
    """An unmatched path has no route template, so it falls back to its raw path, misses the
    allow-list, and is treated as private. Failing closed is the design."""

    class _Req:
        method = "GET"
        scope: dict = {}

        class url:  # noqa: N801 — mimicking Starlette's request.url.path
            path = "/nope/../health"

    assert is_public(_Req()) is False
