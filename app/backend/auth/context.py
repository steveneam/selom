"""Auth context seam — the tenant identity behind a config seam (materialization 7b).

Mirrors ``make_object_store`` / ``make_job_store``: one seam, the dev default unchanged. ``dev`` mode
trusts a fixed ``dev_user_id`` so the inner loop stays offline + single-tenant (every request is the
same dev tenant, no header needed — nothing changes locally). ``clerk`` mode verifies the bearer JWT
(``auth/clerk.py``) and derives the tenant from the verified ``sub`` claim.

**The tenant is ALWAYS the verified claim, never a request param or body** (spec §6.2) — the verifier
reads only the ``Authorization`` header / the dev config, so a handler literally cannot source a
``user_id`` from user input. Handlers depend on ``require_user`` → ``AuthContext``; the per-request DB
transaction then runs ``SET LOCAL app.user_id`` + hands the route a ``TenantQuery`` (``db/tenant.py``).

Prod note: on AWS the API Gateway *Lambda authorizer* verifies the JWT once at the edge and injects
``user_id`` into the request context; ``ClerkVerifier`` also honours that pre-verified context when
present, so the same FastAPI app runs both behind the authorizer (prod) and verifying inline (local).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from fastapi import Depends, HTTPException, Request

from auth.clerk import JwtError, default_jwks_url, verify_clerk_jwt


@dataclass(frozen=True)
class AuthContext:
    """The verified tenant for one request. ``user_id`` is the Clerk ``sub`` (or the dev id)."""

    user_id: str
    email: str | None = None
    claims: dict = field(default_factory=dict)


class AuthVerifier(Protocol):
    def verify(self, request: Request) -> AuthContext: ...


class DevVerifier:
    """Single-tenant dev/offline mode — every request is the same configured dev user."""

    def __init__(self, user_id: str, email: str) -> None:
        self._ctx = AuthContext(user_id=user_id, email=email, claims={"mode": "dev"})

    def verify(self, request: Request) -> AuthContext:  # noqa: ARG002 — request unused by design
        return self._ctx


class ClerkVerifier:
    """Verify a Clerk JWT (inline) or honour the Lambda authorizer's pre-verified context (prod)."""

    def __init__(self, issuer: str, jwks_url: str, audience: str = "") -> None:
        if not issuer:
            raise ValueError("clerk auth requires SELOM_CLERK_ISSUER")
        self._issuer = issuer
        self._jwks_url = jwks_url or default_jwks_url(issuer)
        self._audience = audience or None

    def verify(self, request: Request) -> AuthContext:
        # 1) Prod: the API Gateway Lambda authorizer already verified the JWT and injected user_id.
        injected = _authorizer_user_id(request)
        if injected:
            return AuthContext(user_id=injected, email=None, claims={"mode": "authorizer"})
        # 2) Local clerk mode: verify the bearer token inline.
        token = _bearer_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="authentication required")
        try:
            vc = verify_clerk_jwt(
                token, issuer=self._issuer, jwks_url=self._jwks_url, audience=self._audience
            )
        except JwtError as exc:
            # Opaque 401 — never leak which check failed.
            raise HTTPException(status_code=401, detail="invalid or expired token") from exc
        return AuthContext(user_id=vc.sub, email=vc.email, claims=vc.claims)


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _authorizer_user_id(request: Request) -> str | None:
    """Pull a user_id the API Gateway Lambda authorizer injected (Mangum maps it onto the scope)."""
    event = request.scope.get("aws.event")
    if not isinstance(event, dict):
        return None
    rc = event.get("requestContext", {})
    authz = rc.get("authorizer", {}) if isinstance(rc, dict) else {}
    # REST API authorizers nest claims under `authorizer`; HTTP API JWT authorizers under `.jwt.claims`.
    if isinstance(authz, dict):
        jwt = authz.get("jwt", {})
        claims = jwt.get("claims", {}) if isinstance(jwt, dict) else {}
        return authz.get("user_id") or authz.get("sub") or claims.get("sub")
    return None


def make_auth_verifier(settings) -> AuthVerifier:
    """Select the verifier by config — the dev default needs no external setup."""
    if settings.auth_mode.strip().lower() == "clerk":
        return ClerkVerifier(
            issuer=settings.clerk_issuer,
            jwks_url=settings.clerk_jwks_url,
            audience=settings.clerk_audience,
        )
    return DevVerifier(user_id=settings.dev_user_id, email=settings.dev_user_email)


# --- FastAPI wiring ---------------------------------------------------------------------------
# One verifier per process (the Clerk variant caches the JWKS). `get_verifier` is a dependency so a
# test can override it via `app.dependency_overrides[get_verifier]` to inject a fake tenant.
_verifier: AuthVerifier | None = None


def get_verifier() -> AuthVerifier:
    global _verifier
    if _verifier is None:
        from config import settings

        _verifier = make_auth_verifier(settings)
    return _verifier


def reset_verifier() -> None:
    """Test hygiene — force a rebuild from current settings."""
    global _verifier
    _verifier = None


async def require_user(
    request: Request, verifier: AuthVerifier = Depends(get_verifier)
) -> AuthContext:
    """FastAPI dependency → the verified ``AuthContext``. Raises 401 if auth is required and absent.

    Reuses the context the app-level ``enforce_auth`` (``auth/policy.py``) already resolved for this
    request when there is one — otherwise a private route with its own ``require_user`` would verify
    the same JWT twice per request. Falls through to verifying directly so this dependency still
    stands alone (a test that calls it without the app-level guard, or a public route that
    additionally wants the caller's identity).
    """
    cached = getattr(request.state, "auth", None)
    if isinstance(cached, AuthContext):
        return cached
    ctx = verifier.verify(request)
    request.state.auth = ctx
    return ctx
