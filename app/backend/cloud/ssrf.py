"""SSRF guard for the URL/S3 cloud-import connector (resolve-then-check).

A user-supplied import URL is an SSRF vector: left unchecked it could make the server fetch
``http://169.254.169.254/`` (cloud instance-metadata → credentials), a ``127.0.0.1`` admin port, or
an internal ``10.x`` service. So before any request we:

  1. require an ``http``/``https`` scheme (no ``file://`` / ``gopher://`` / …),
  2. **resolve the host to its IPs** (an IP literal resolves to itself), and
  3. reject if ANY resolved address is not globally routable — loopback, link-local (incl. the
     ``169.254.169.254`` metadata IP), RFC1918 / unique-local private, CGNAT, multicast, reserved,
     or unspecified.

The connector re-runs this on **every redirect hop** (a public URL can 302 to an internal one), so
the check can't be dodged by a redirect. Residual: a TOCTOU DNS-rebind between this check and the
socket connect is not fully closed here (that needs pinning the connection to the vetted IP) — noted
for the hardening pass; the redirect re-check + public-only gate covers the common vectors.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

_ALLOWED_SCHEMES = ("http", "https")


class SsrfError(ValueError):
    """A URL that resolves to a non-public / disallowed target (an SSRF attempt or a mistake)."""


def _is_public(ip: str) -> bool:
    """True only for a globally-routable unicast address. ``is_global`` already excludes private,
    loopback, link-local, CGNAT, reserved and unspecified ranges; the explicit checks are defensive
    (belt-and-suspenders across Python versions) and make the intent readable."""
    addr = ipaddress.ip_address(ip)
    if (
        addr.is_loopback
        or addr.is_link_local      # includes 169.254.169.254 (cloud metadata)
        or addr.is_private         # RFC1918 / unique-local / CGNAT
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        return False
    return addr.is_global


def resolve_public_ips(host: str) -> list[str]:
    """Every A/AAAA the host resolves to, after asserting each is public. Raises ``SsrfError`` if the
    host doesn't resolve or ANY address is non-public. An IP-literal host resolves to itself."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SsrfError(f"could not resolve host: {host!r}") from exc
    ips = sorted({info[4][0] for info in infos})
    if not ips:
        raise SsrfError(f"host resolved to no addresses: {host!r}")
    bad = [ip for ip in ips if not _is_public(ip)]
    if bad:
        raise SsrfError(f"host {host!r} resolves to a non-public address: {', '.join(bad)}")
    return ips


def assert_safe_url(url: str) -> None:
    """Raise ``SsrfError`` unless ``url`` is an ``http(s)`` URL whose host resolves to public IP(s)
    only. Call this before every fetch — including each redirect hop."""
    parts = urlsplit(url)
    if parts.scheme.lower() not in _ALLOWED_SCHEMES:
        raise SsrfError(
            f"unsupported URL scheme {parts.scheme!r} — only http/https imports are allowed"
        )
    host = parts.hostname
    if not host:
        raise SsrfError("URL has no host")
    resolve_public_ips(host)
