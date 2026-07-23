"""SSRF guard (cloud/ssrf.py) — the deny-list that keeps a user-supplied import URL from reaching the
cloud metadata IP, a private RFC1918 host, or loopback. IP-literal hosts are used throughout so the
resolver never touches the network (getaddrinfo on a numeric host does no DNS)."""

from __future__ import annotations

import pytest

from cloud.ssrf import SsrfError, assert_safe_url

# Every one of these must be rejected (an SSRF attempt or a mistake).
BLOCKED = [
    "http://169.254.169.254/latest/meta-data/",   # cloud instance-metadata (link-local)
    "http://[fd00::1]/x",                          # IPv6 unique-local (private)
    "http://10.0.0.5/data.csv",                    # RFC1918
    "https://172.16.9.9/x",                        # RFC1918
    "http://192.168.1.1/x",                        # RFC1918
    "http://127.0.0.1:8000/x",                     # loopback
    "http://[::1]/x",                              # IPv6 loopback
    "http://0.0.0.0/x",                            # unspecified
    "http://100.64.0.1/x",                         # CGNAT (not globally routable)
    "file:///etc/passwd",                          # non-http scheme
    "ftp://93.184.216.34/x",                       # non-http scheme
    "http:///nohost",                              # no host
]


@pytest.mark.parametrize("url", BLOCKED)
def test_rejects_non_public_or_bad_scheme(url):
    with pytest.raises(SsrfError):
        assert_safe_url(url)


@pytest.mark.parametrize("url", [
    "http://93.184.216.34/file.csv",     # a public IPv4 literal
    "https://8.8.8.8/x",                 # a public IPv4 literal
])
def test_allows_public_ip_literal(url):
    # Must NOT raise (no DNS: numeric host).
    assert_safe_url(url)
