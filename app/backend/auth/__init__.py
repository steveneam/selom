"""Auth / tenancy package (AWS materialization step 7b).

The verified tenant identity behind a config seam: ``dev`` (a fixed offline user) or ``clerk``
(verify the Clerk JWT → ``sub`` = tenant). The tenant is always the verified claim, never a request
param (spec §4.3, §6.2). Pairs with ``db/tenant.py`` (``TenantQuery`` + RLS) for data access.
"""

from auth.context import AuthContext, get_verifier, make_auth_verifier, require_user

__all__ = ["AuthContext", "get_verifier", "make_auth_verifier", "require_user"]
