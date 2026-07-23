"""Typed failures for the cloud-import/export path, so ``routers/cloud.py`` maps each to the right
HTTP status instead of leaking a bare exception. ``SsrfError`` (cloud/ssrf.py) stays separate — it
subclasses ``ValueError`` — but the router treats it the same as ``CloudFetchError`` (a 400)."""

from __future__ import annotations


class CloudError(Exception):
    """Base for a cloud connector failure."""


class CloudTooLarge(CloudError):
    """The streamed object exceeded the running byte-cap (the tenant's storage headroom)."""


class CloudFetchError(CloudError):
    """The provider source couldn't be fetched (bad URL, non-2xx, too many redirects, provider 4xx/5xx)."""


class ProviderNotConfigured(CloudError):
    """An OAuth provider was requested but its feature flag is off / its client IDs aren't in Nango yet."""
