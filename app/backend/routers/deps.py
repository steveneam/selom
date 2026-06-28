from fastapi import HTTPException

from library import get_library_repo
from uploads import get_upload_repo


def _uploads_repo():
    """FastAPI dependency → the UploadRepo, or a 503 when no database is configured."""
    try:
        return get_upload_repo()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _library_repo():
    """FastAPI dependency → the LibraryRepo (figures + the account library), 503 when no DB."""
    try:
        return get_library_repo()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
