"""Cloud-storage integrations — import a provider file into Selom's existing intake pipeline, and
(scaffolded) export a figure/dataset out to a provider.

The seam: a native "Connect via Nango" on the FE brokers the OAuth token; a BACKEND import endpoint
streams the file provider→object-store and hands it to the SAME ``intake → confirm → parse`` pipeline
the local drop-zone uses (``uploads/``), so there is no parallel ingest. URL/S3 needs no OAuth and
works today; Google Drive / OneDrive / Dropbox are scaffolded against Nango and light up per feature
flag once the owner's client IDs exist. Provenance of an imported file is stamped on ``datasets.source``.

Pieces: ``ssrf`` (deny-list guard for the URL fetch), ``connectors/`` (one ``CloudConnector`` per
provider), ``registry`` (provider table + flag gating), ``nango`` (thin client to the local Nango).
"""

from cloud.errors import (
    CloudError,
    CloudFetchError,
    CloudTooLarge,
    ProviderNotConfigured,
)

__all__ = ["CloudError", "CloudFetchError", "CloudTooLarge", "ProviderNotConfigured"]
