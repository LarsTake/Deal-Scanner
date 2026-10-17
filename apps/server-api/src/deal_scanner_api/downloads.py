from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .settings import get_settings

router = APIRouter()


@router.get("/downloads/browser-extension", include_in_schema=False)
def browser_extension_download() -> FileResponse:
    """Public software download; the archive contains no device/account configuration."""
    archive = Path(get_settings().browser_extension_archive)
    if not archive.is_file():
        raise HTTPException(
            status_code=404,
            detail="Extension package missing. Rebuild the API image or run the browser-extension:package script.",
        )
    return FileResponse(
        archive,
        media_type="application/zip",
        filename="deal-scanner-chrome.zip",
        headers={"Cache-Control": "no-cache"},
    )
