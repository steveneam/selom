"""``LibraryRepo`` — the composed tenant-CRUD repo + its lazy singleton / test seam.

Composes every resource mixin onto one class over one engine (one connection pool, one main.py
dependency). BE-1 ships the figures mixin; BE-2 adds the account-library mixins (workspace / gene
sets / papers / installs / cleaning / reproduction-run pointers) to the bases tuple here.

The singleton mirrors ``get_upload_repo`` / ``set_upload_repo``: built from ``settings.database_url``;
a missing URL surfaces a clear 503 at the handler, never a silent default.
"""

from __future__ import annotations

from library.base import TenantRepo
from library.figures import FigureMixin
from library.papers import PaperMixin
from library.workspace import GeneSetMixin, InstallMixin, WorkspaceMixin


class LibraryRepo(
    FigureMixin, WorkspaceMixin, GeneSetMixin, InstallMixin, PaperMixin, TenantRepo
):
    """Tenant CRUD for the FE stores (figures + the account library) behind ``TenantQuery``.

    Scope note (sub-spec §7): ``cleaning_recipes`` and ``reproduction_runs`` are intentionally NOT
    built here — cleaning steps already round-trip inside ``datasets.qc`` (the QcReport JSON), and the
    reproduction-run pointer is written by the BE reproduction engine (step 8), not an FE store. The
    four resources the FE stores actually persist are figures · workspace · gene sets · papers."""


_repo: LibraryRepo | None = None


def get_library_repo() -> LibraryRepo:
    global _repo
    if _repo is None:
        from config import settings

        if not settings.database_url:
            raise RuntimeError(
                "library requires a database (set SELOM_DATABASE_URL; SELOM_DB_AUTO_CREATE=true for dev)"
            )
        _repo = LibraryRepo(url=settings.database_url, create=settings.db_auto_create)
    return _repo


def set_library_repo(repo: LibraryRepo | None) -> None:
    global _repo
    _repo = repo
