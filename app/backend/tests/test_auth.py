"""Auth seam — JWT verification + the config seam (materialization 7b).

The Clerk verifier is hand-rolled RS256 over a JWKS, so this suite is its security spec: it mints
RS256 tokens with a local keypair + a stub JWKS and asserts the classic JWT attacks fail closed
(``none`` alg, HS256 alg-confusion, tampered signature, wrong issuer/audience, expired/not-yet-valid,
missing/unknown ``kid``). It also pins the dev/clerk config seam + the FastAPI dependency behaviour.
"""

from __future__ import annotations

import base64
import json

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import HTTPException
from starlette.requests import Request

from auth import clerk
from auth.clerk import JwtError, verify_clerk_jwt
from auth.context import (
    ClerkVerifier,
    DevVerifier,
    make_auth_verifier,
)

ISSUER = "https://stub.clerk.accounts.dev"
JWKS_URL = ISSUER + "/.well-known/jwks.json"
KID = "kid-test-1"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _jwk(public_key: rsa.RSAPublicKey, kid: str = KID) -> dict:
    nums = public_key.public_numbers()
    n = nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big")
    e = nums.e.to_bytes((nums.e.bit_length() + 7) // 8, "big")
    return {"kty": "RSA", "kid": kid, "use": "sig", "alg": "RS256", "n": _b64url(n), "e": _b64url(e)}


def _mint(private_key: rsa.RSAPrivateKey, payload: dict, *, alg: str = "RS256", kid: str | None = KID) -> str:
    header: dict = {"alg": alg, "typ": "JWT"}
    if kid is not None:
        header["kid"] = kid
    h = _b64url(json.dumps(header).encode())
    p = _b64url(json.dumps(payload).encode())
    if alg == "none":
        return f"{h}.{p}."
    sig = private_key.sign(f"{h}.{p}".encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    return f"{h}.{p}.{_b64url(sig)}"


@pytest.fixture
def keypair():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def _stub_jwks(keypair, monkeypatch):
    """Serve the test public key from the JWKS without any network call."""
    keys = {KID: _jwk(keypair.public_key())}
    clerk.reset_jwks_cache()
    monkeypatch.setattr(clerk, "_fetch_jwks", lambda url: keys)
    return keys


def _claims(**over) -> dict:
    base = {"iss": ISSUER, "sub": "user_abc", "email": "a@example.com", "exp": 9_999_999_999}
    base.update(over)
    return base


# --- the happy path ---------------------------------------------------------------------------

def test_valid_token_verifies(keypair):
    token = _mint(keypair, _claims())
    vc = verify_clerk_jwt(token, issuer=ISSUER, jwks_url=JWKS_URL)
    assert vc.sub == "user_abc"
    assert vc.email == "a@example.com"
    assert vc.claims["iss"] == ISSUER


# --- the classic attacks all fail closed ------------------------------------------------------

def test_alg_none_rejected(keypair):
    token = _mint(keypair, _claims(), alg="none")
    with pytest.raises(JwtError):
        verify_clerk_jwt(token, issuer=ISSUER, jwks_url=JWKS_URL)


def test_hs256_alg_confusion_rejected(keypair):
    # An HS256 header (the public-key-as-HMAC-secret attack) must be refused at the allowlist,
    # before any key material is touched.
    token = _mint(keypair, _claims(), alg="HS256")
    with pytest.raises(JwtError):
        verify_clerk_jwt(token, issuer=ISSUER, jwks_url=JWKS_URL)


def test_tampered_signature_rejected(keypair):
    token = _mint(keypair, _claims())
    head, payload, sig = token.split(".")
    # flip the payload (a privilege-escalation attempt) — signature no longer matches.
    forged_payload = _b64url(json.dumps(_claims(sub="victim")).encode())
    with pytest.raises(JwtError):
        verify_clerk_jwt(f"{head}.{forged_payload}.{sig}", issuer=ISSUER, jwks_url=JWKS_URL)


def test_wrong_issuer_rejected(keypair):
    token = _mint(keypair, _claims(iss="https://evil.example"))
    with pytest.raises(JwtError):
        verify_clerk_jwt(token, issuer=ISSUER, jwks_url=JWKS_URL)


def test_expired_token_rejected(keypair):
    token = _mint(keypair, _claims(exp=1_000))  # long past
    with pytest.raises(JwtError):
        verify_clerk_jwt(token, issuer=ISSUER, jwks_url=JWKS_URL, _now=2_000)


def test_not_yet_valid_rejected(keypair):
    token = _mint(keypair, _claims(nbf=10_000))
    with pytest.raises(JwtError):
        verify_clerk_jwt(token, issuer=ISSUER, jwks_url=JWKS_URL, _now=1_000)


def test_missing_kid_rejected(keypair):
    token = _mint(keypair, _claims(), kid=None)
    with pytest.raises(JwtError):
        verify_clerk_jwt(token, issuer=ISSUER, jwks_url=JWKS_URL)


def test_unknown_kid_rejected(keypair):
    token = _mint(keypair, _claims(), kid="kid-rotated-away")
    with pytest.raises(JwtError):
        verify_clerk_jwt(token, issuer=ISSUER, jwks_url=JWKS_URL)


def test_audience_enforced_when_configured(keypair):
    token = _mint(keypair, _claims(aud="my-app"))
    assert verify_clerk_jwt(token, issuer=ISSUER, jwks_url=JWKS_URL, audience="my-app").sub == "user_abc"
    with pytest.raises(JwtError):
        verify_clerk_jwt(token, issuer=ISSUER, jwks_url=JWKS_URL, audience="other-app")


def test_missing_sub_rejected(keypair):
    payload = _claims()
    del payload["sub"]
    token = _mint(keypair, payload)
    with pytest.raises(JwtError):
        verify_clerk_jwt(token, issuer=ISSUER, jwks_url=JWKS_URL)


def test_malformed_token_rejected():
    with pytest.raises(JwtError):
        verify_clerk_jwt("not-a-jwt", issuer=ISSUER, jwks_url=JWKS_URL)


# --- the config seam + FastAPI verifiers -------------------------------------------------------

def _request(headers: dict | None = None, aws_event: dict | None = None) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    if aws_event is not None:
        scope["aws.event"] = aws_event
    return Request(scope)


def test_dev_verifier_is_single_tenant():
    v = DevVerifier(user_id="dev-user", email="dev@selom.local")
    ctx = v.verify(_request())  # no header needed
    assert ctx.user_id == "dev-user"
    assert ctx.email == "dev@selom.local"


def test_clerk_verifier_accepts_bearer(keypair):
    v = ClerkVerifier(issuer=ISSUER, jwks_url=JWKS_URL)
    token = _mint(keypair, _claims())
    ctx = v.verify(_request({"Authorization": f"Bearer {token}"}))
    assert ctx.user_id == "user_abc"


def test_clerk_verifier_missing_bearer_is_401():
    v = ClerkVerifier(issuer=ISSUER, jwks_url=JWKS_URL)
    with pytest.raises(HTTPException) as exc:
        v.verify(_request())
    assert exc.value.status_code == 401


def test_clerk_verifier_bad_token_is_401(keypair):
    v = ClerkVerifier(issuer=ISSUER, jwks_url=JWKS_URL)
    token = _mint(keypair, _claims(iss="https://evil.example"))
    with pytest.raises(HTTPException) as exc:
        v.verify(_request({"Authorization": f"Bearer {token}"}))
    assert exc.value.status_code == 401


def test_clerk_verifier_honours_authorizer_context():
    # Prod path: the Lambda authorizer pre-verified the JWT and injected user_id — no bearer needed.
    v = ClerkVerifier(issuer=ISSUER, jwks_url=JWKS_URL)
    event = {"requestContext": {"authorizer": {"user_id": "edge-user"}}}
    ctx = v.verify(_request(aws_event=event))
    assert ctx.user_id == "edge-user"


def test_make_auth_verifier_selects_by_mode():
    class _S:
        auth_mode = "dev"
        dev_user_id = "dev-user"
        dev_user_email = "dev@selom.local"
        clerk_issuer = ISSUER
        clerk_jwks_url = JWKS_URL
        clerk_audience = ""

    assert isinstance(make_auth_verifier(_S()), DevVerifier)
    _S.auth_mode = "clerk"
    assert isinstance(make_auth_verifier(_S()), ClerkVerifier)
