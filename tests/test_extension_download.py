from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest
from deal_scanner_api.main import app
from deal_scanner_api.settings import get_settings


@pytest.mark.asyncio
async def test_extension_download_is_public_zip_without_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "extension.zip"
    with ZipFile(archive, "w") as target:
        target.writestr("manifest.json", '{"manifest_version":3}')
    monkeypatch.setattr(get_settings(), "browser_extension_archive", str(archive))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/downloads/browser-extension")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "deal-scanner-chrome.zip" in response.headers["content-disposition"]
    assert response.content == archive.read_bytes()


@pytest.mark.asyncio
async def test_missing_package_returns_actionable_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "browser_extension_archive", str(tmp_path / "missing.zip"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/downloads/browser-extension")
    assert response.status_code == 404
    assert "package" in response.json()["detail"].lower()
