"""Tenant-CRUD repos behind the FE stores (AWS materialization step 7c).

See ``library/base.py`` for the shared pattern. ``LibraryRepo`` composes every resource mixin; the
endpoints in ``main.py`` reach it through ``get_library_repo`` (a 503 when no DB is configured).
"""

from library.figures import figure_public
from library.repo import LibraryRepo, get_library_repo, set_library_repo

__all__ = [
    "LibraryRepo", "get_library_repo", "set_library_repo",
    "figure_public",
]
