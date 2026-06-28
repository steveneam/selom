"""Clerk JWT verification — dependency-free RS256 over the standard JWKS (materialization 7b).

Clerk issues an RS256 JWT to the Next.js frontend; the API Gateway Lambda authorizer (prod) — or a
FastAPI dependency (local ``clerk`` mode) — verifies it and derives the tenant from the verified
``sub`` claim, never a request param (spec §4.3, §6.2). We verify in-process rather than pull a JWT
library: the only crypto primitive needed is RSASSA-PKCS1-v1_5 / SHA-256, which ``cryptography``
(already a dependency) provides as a vetted routine — we only parse the JWT envelope and check the
claims around it. This keeps the *light* Lambda zip small (spec §5) and matches the hand-rolled-TOON
precedent (no venv dep where a few lines of stdlib + an existing primitive do it).

Security posture (the classic JWT pitfalls, each covered by a test in ``tests/test_auth.py``):
  * **alg allowlist** — only ``RS256`` is accepted. ``none`` and the HS256 *alg-confusion* attack
    (signing with the RSA *public* key as an HMAC secret) are rejected before any verification.
  * **kid binding** — the signing key is chosen by the token's ``kid`` against the JWKS, not by the
    token's self-declared key material. An unknown ``kid`` triggers ONE JWKS refetch (key rotation),
    then fails closed.
  * **claims** — ``exp`` (expired), ``nbf``/``iat`` (not-yet-valid, small leeway), ``iss`` (exact
    issuer match), and ``aud`` (only when an audience is configured) are all enforced.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.request
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

_ALLOWED_ALGS = frozenset({"RS256"})
_LEEWAY_S = 60  # clock-skew tolerance for exp/nbf/iat
_JWKS_TTL_S = 600  # cache a fetched JWKS for 10 min; a kid miss forces an early refetch (rotation)


class JwtError(Exception):
    """Any verification failure — a bad signature, a stale token, a wrong issuer, a malformed JWT.

    One opaque type on purpose: the caller turns it into a 401 without leaking *which* check failed.
    """


@dataclass(frozen=True)
class VerifiedClaims:
    sub: str
    email: str | None
    claims: dict


def _b64url_decode(segment: str) -> bytes:
    pad = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + pad)


# --- JWKS cache -------------------------------------------------------------------------------
# {jwks_url: (fetched_at, {kid: jwk_dict})}. Process-local; a Lambda cold start refetches, which is
# correct (one fetch amortized over the instance's lifetime).
_jwks_cache: dict[str, tuple[float, dict[str, dict]]] = {}


def _fetch_jwks(jwks_url: str) -> dict[str, dict]:
    with urllib.request.urlopen(jwks_url, timeout=10) as resp:  # noqa: S310 — fixed https config URL
        doc = json.loads(resp.read().decode("utf-8"))
    keys = {k["kid"]: k for k in doc.get("keys", []) if k.get("kid")}
    if not keys:
        raise JwtError("JWKS has no usable keys")
    _jwks_cache[jwks_url] = (time.time(), keys)
    return keys


def _jwk_for_kid(jwks_url: str, kid: str) -> dict:
    cached = _jwks_cache.get(jwks_url)
    fresh = cached is not None and (time.time() - cached[0]) < _JWKS_TTL_S
    keys = cached[1] if cached is not None else {}
    if not fresh or kid not in keys:
        # stale, or a kid we've never seen (rotation) → refetch once, then fail closed.
        keys = _fetch_jwks(jwks_url)
    jwk = keys.get(kid)
    if jwk is None:
        raise JwtError(f"no JWKS key for kid {kid!r}")
    if jwk.get("kty") != "RSA":
        raise JwtError("unsupported key type (only RSA)")
    return jwk


def reset_jwks_cache() -> None:
    """Test hygiene — drop the cached JWKS so a stub server is refetched."""
    _jwks_cache.clear()


def _public_key(jwk: dict) -> rsa.RSAPublicKey:
    n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    return rsa.RSAPublicNumbers(e, n).public_key()


def verify_clerk_jwt(
    token: str,
    *,
    issuer: str,
    jwks_url: str,
    audience: str | None = None,
    _now: float | None = None,
) -> VerifiedClaims:
    """Verify a Clerk RS256 JWT and return its claims, or raise ``JwtError``.

    ``_now`` is an injection seam for the tests (expiry/nbf) — production passes nothing.
    """
    now = time.time() if _now is None else _now
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise JwtError("token is not a well-formed JWT") from exc

    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(sig_b64)
    except (ValueError, json.JSONDecodeError) as exc:
        raise JwtError("token segments are not valid base64url/JSON") from exc

    # --- envelope: alg allowlist (reject `none` + HS256 alg-confusion before touching the key) ---
    alg = header.get("alg")
    if alg not in _ALLOWED_ALGS:
        raise JwtError(f"unsupported or unsafe alg {alg!r}")
    kid = header.get("kid")
    if not kid:
        raise JwtError("token header has no kid")

    # --- signature (the vetted cryptography primitive does the math) ---
    jwk = _jwk_for_kid(jwks_url, kid)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    try:
        _public_key(jwk).verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
    except InvalidSignature as exc:
        raise JwtError("signature does not verify") from exc

    # --- claims (only after the signature is proven) ---
    if payload.get("iss") != issuer:
        raise JwtError("issuer mismatch")
    if audience:
        aud = payload.get("aud")
        ok = audience == aud or (isinstance(aud, list) and audience in aud)
        if not ok:
            raise JwtError("audience mismatch")
    exp = payload.get("exp")
    if exp is not None and now > float(exp) + _LEEWAY_S:
        raise JwtError("token expired")
    nbf = payload.get("nbf")
    if nbf is not None and now < float(nbf) - _LEEWAY_S:
        raise JwtError("token not yet valid")
    iat = payload.get("iat")
    if iat is not None and now < float(iat) - _LEEWAY_S:
        raise JwtError("token issued in the future")
    sub = payload.get("sub")
    if not sub:
        raise JwtError("token has no sub claim")

    return VerifiedClaims(sub=sub, email=payload.get("email"), claims=payload)


def default_jwks_url(issuer: str) -> str:
    """Clerk's conventional JWKS endpoint for an instance issuer."""
    return issuer.rstrip("/") + "/.well-known/jwks.json"
