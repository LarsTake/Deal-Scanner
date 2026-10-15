import asyncio
import json
import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

os.environ["DEAL_SCANNER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEAL_SCANNER_AUTO_CREATE_DB"] = "true"
os.environ["DEAL_SCANNER_AUTH_MODE"] = "development"

from deal_scanner_api.database import session_factory
from deal_scanner_api.db_models import ProviderConfigurationRow
from deal_scanner_api.main import app
from deal_scanner_api.restock_service import parse_availability, validate_shop_url
from deal_scanner_api.routers import restock
from fastapi import HTTPException
from fastapi.testclient import TestClient

URL = "https://www.otto.de/p/test-product"


def page(availability: str, url: str = URL) -> str:
    product = {
        "@type": "Product",
        "name": "Test Product",
        "url": url,
        "offers": {"availability": f"https://schema.org/{availability}"},
    }
    return f'<script type="application/ld+json">{json.dumps(product)}</script>'


def test_availability_requires_unambiguous_product_evidence() -> None:
    assert parse_availability(page("InStock"), URL) == (True, "Test Product")
    assert parse_availability(page("OutOfStock"), URL) == (False, "Test Product")
    assert parse_availability(page("PreOrder"), URL) == (None, "Test Product")
    assert parse_availability("<h1>Captcha</h1>", URL)[0] is None
    assert parse_availability(page("InStock", "https://www.otto.de/p/other-product"), URL)[0] is None


@pytest.mark.parametrize(
    "url",
    [
        "http://www.otto.de/p/product",
        "https://127.0.0.1/p/product",
        "https://www.otto.de.evil.example/p/product",
        "https://www.otto.de:8443/p/product",
        "https://www.otto.de/",
    ],
)
def test_restock_host_boundary(url: str) -> None:
    with pytest.raises(HTTPException):
        validate_shop_url(url)


def test_restock_notifies_only_confirmed_transition_and_keeps_unknown_state(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [page("OutOfStock"), "<html>Unknown layout</html>", page("InStock")]
    requests = 0
    original = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, text=responses.pop(0))

    monkeypatch.setattr(
        restock.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )

    async def expire_interval() -> None:
        async with session_factory() as session:
            row = await session.scalar(
                select(ProviderConfigurationRow).where(ProviderConfigurationRow.provider == "shopRestock")
            )
            assert row is not None
            state = {
                **row.settings_json["states"][URL],
                "checkedAt": (datetime.now(UTC) - timedelta(minutes=10)).isoformat(),
            }
            row.settings_json = {**row.settings_json, "states": {URL: state}}
            await session.commit()

    with TestClient(app) as client:
        assert client.put("/api/v1/restock", json={"urls": [URL], "enabled": True}).status_code == 200
        first = client.post("/api/v1/restock/check").json()
        assert first["notifications"] == 0
        assert first["states"][URL]["available"] is False
        asyncio.run(expire_interval())
        unknown = client.post("/api/v1/restock/check").json()
        assert unknown["notifications"] == 0
        assert unknown["states"][URL]["available"] is None
        assert unknown["states"][URL]["lastKnownAvailable"] is False
        asyncio.run(expire_interval())
        available = client.post("/api/v1/restock/check").json()
        assert available["notifications"] == 1
        pending = client.get("/api/v1/notifications?pending_only=true").json()
        assert len(pending) == 1
        assert pending[0]["reason"]["type"] == "restock"
        assert client.post("/api/v1/restock/check").json()["checked"] == 0
        assert requests == 3


def test_restock_is_inert_without_targets_and_rejects_private_urls() -> None:
    with TestClient(app) as client:
        assert client.post("/api/v1/restock/check").json()["checked"] == 0
        assert (
            client.put("/api/v1/restock", json={"urls": ["https://localhost/private"], "enabled": True}).status_code
            == 422
        )
