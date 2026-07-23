import ssl
from io import BytesIO
from unittest.mock import AsyncMock

import httpx
import pytest
from deal_scanner_api.image_service import download_provider_image, system_ssl_context, validate_image_url
from deal_scanner_api.main import app
from deal_scanner_extraction import fingerprint_image, perceptually_similar
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw


def _image(changed: bool = False) -> bytes:
    image = Image.new("RGB", (128, 128), "#132a24")
    draw = ImageDraw.Draw(image)
    draw.ellipse((24, 24, 104, 104), outline="#72f2bd", width=8)
    draw.line((64, 64, 98, 30), fill="#72f2bd", width=7)
    if changed:
        draw.rectangle((3, 3, 8, 8), fill="#152c26")
    target = BytesIO()
    image.save(target, format="PNG")
    return target.getvalue()


def test_exact_and_perceptual_image_duplicates() -> None:
    original = fingerprint_image(_image())
    same = fingerprint_image(_image())
    changed = fingerprint_image(_image(changed=True))
    assert original.sha256 == same.sha256
    assert original.sha256 != changed.sha256
    assert perceptually_similar(original.perceptual_hash, changed.perceptual_hash)
    assert original.mime_type == "image/png"


def test_provider_download_uses_the_system_certificate_store() -> None:
    assert isinstance(system_ssl_context(), ssl.SSLContext)


@pytest.mark.asyncio
async def test_provider_image_download_rejects_unknown_hosts_and_redirects() -> None:
    validate_image_url("https://i.ebayimg.com/images/example.png", "ebay")
    with pytest.raises(HTTPException):
        validate_image_url("https://127.0.0.1/private.png", "ebay")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "i.ebayimg.com"
        return httpx.Response(200, content=_image(), headers={"Content-Type": "image/png"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        content, fingerprint = await download_provider_image(
            "https://i.ebayimg.com/images/example.png",
            "ebay",
            client=client,
        )
    assert content == _image()
    assert fingerprint.mime_type == "image/png"


def test_image_import_queues_ocr_and_marks_exact_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    fingerprint = fingerprint_image(_image())
    monkeypatch.setattr(
        "deal_scanner_api.routers.images.download_provider_image",
        AsyncMock(return_value=(_image(), fingerprint)),
    )
    monkeypatch.setattr(
        "deal_scanner_api.routers.images.store_private_image",
        AsyncMock(return_value=f"fixture/{fingerprint.sha256}.png"),
    )
    with TestClient(app) as client:
        imported = client.post(
            "/api/v1/imports/manual",
            json={
                "platform": "ebay",
                "externalId": "image-fixture-listing",
                "url": "https://www.ebay.de/itm/123456789012",
                "title": "Gaming PC RTX 4070 Super",
                "description": "Abholung möglich",
                "price": "500.00",
                "currency": "EUR",
                "categoryProfile": "computer",
                "providerVersion": "browse-v1",
            },
        )
        listing_id = imported.json()["listing"]["id"]
        image_payload = {"sourceUrls": ["https://i.ebayimg.com/images/example.png"]}
        first = client.post(f"/api/v1/listings/{listing_id}/images", json=image_payload)
        assert first.status_code == 201, first.text
        assert first.json()[0]["analysisStatus"] == "PENDING"
        second = client.post(f"/api/v1/listings/{listing_id}/images", json=image_payload)
        assert second.status_code == 201, second.text
        assert second.json()[0]["analysisStatus"] == "DUPLICATE"
        assert second.json()[0]["exactDuplicateOf"] == first.json()[0]["id"]
        jobs = client.get("/api/v1/jobs").json()
        assert sum(job["jobType"] == "image_ocr" and job["listingId"] == listing_id for job in jobs) == 1
