import os

os.environ["DEAL_SCANNER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEAL_SCANNER_AUTO_CREATE_DB"] = "true"
os.environ["DEAL_SCANNER_AUTH_MODE"] = "development"

import pytest
from deal_scanner_api.main import app
from deal_scanner_core.market_identity import model_identity
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "title", ["Gaming PC RTX 4070 12GB", "Karton RTX4070 12GB", "Icy Dock Konvolut MB522SP", "SSD Adapter"]
)
def test_unclear_or_accessory_offers_are_not_comparable(title: str) -> None:
    assert model_identity(title) is None


def test_exact_model_variants_are_separate() -> None:
    assert model_identity("IcyDock Flexidock MB522SP") == "icy dock mb522sp"
    assert model_identity("ICY DOCK MB982SP-1S1") != model_identity("Icy Dock MB982IP-1S-1")
    assert model_identity("RTX4070 12GB") != model_identity("RTX 4070 Super 12GB")


def test_research_validates_deduplicates_and_recalculates() -> None:
    with TestClient(app, client=("market-research-tests", 50000)) as client:
        imported = client.post(
            "/api/v1/imports/manual",
            json={
                "platform": "kleinanzeigen",
                "externalId": "research-target",
                "url": "https://www.kleinanzeigen.de/s-anzeige/target/999-1-1",
                "title": "Icy Dock MB522SP gebraucht",
                "description": "gebraucht",
                "price": "10.00",
                "shippingCost": "0",
                "currency": "EUR",
                "categoryProfile": "general",
            },
        )
        assert imported.status_code == 201, imported.text
        listing_id = imported.json()["listing"]["id"]
        candidates = [
            {
                "platform": "kleinanzeigen",
                "url": f"https://www.kleinanzeigen.de/s-anzeige/offer/{i}-1-1",
                "title": "Icy Dock MB522SP gebraucht",
                "price": str(30 + i),
                "currency": "EUR",
            }
            for i in range(1, 4)
        ]
        rejected = [
            dict(candidates[0], title="Icy Dock MB982SP gebraucht"),
            dict(candidates[0], url="https://evil.example/test"),
            dict(candidates[0], url="https://www.kleinanzeigen.de/s-anzeige/target/999-1-1"),
            dict(candidates[0], title="Icy Dock MB522SP neu"),
        ]
        result = client.post(
            f"/api/v1/listings/{listing_id}/market-research", json={"candidates": rejected + candidates}
        )
        assert result.status_code == 200, result.text
        assert result.json()["accepted"] == 3
        detail = client.get(f"/api/v1/listings/{listing_id}").json()
        assert detail["marketValueMedian"] is not None
        assert detail["dealScore"] is not None
        result = client.post(f"/api/v1/listings/{listing_id}/market-research", json={"candidates": candidates})
        assert result.status_code == 200
        rows = client.get("/api/v1/price-observations", params={"listingId": listing_id}).json()
        researched = [row for row in rows if row["metadata"].get("researchVersion")]
        assert len(researched) == 3
        assert all(row["observationKind"] == "active" and not row["metadata"]["verifiedSale"] for row in researched)
        targets = client.get("/api/v1/market-research/targets").json()
        assert listing_id not in [target["id"] for target in targets]
        import asyncio
        from datetime import UTC, datetime, timedelta
        from uuid import UUID

        from deal_scanner_api.database import session_factory
        from deal_scanner_api.db_models import PriceObservationRow
        from sqlalchemy import select

        async def expire() -> None:
            async with session_factory() as session:
                rows = await session.scalars(
                    select(PriceObservationRow).where(PriceObservationRow.listing_id == UUID(listing_id))
                )
                for row in rows:
                    row.observed_at = datetime.now(UTC) - timedelta(days=15)
                await session.commit()

        asyncio.run(expire())
        evaluation = client.post(f"/api/v1/listings/{listing_id}/evaluate")
        assert evaluation.status_code == 200
        assert evaluation.json()["market"]["median"] is None


@pytest.mark.asyncio
async def test_scheduler_research_is_bounded_and_has_no_purchase_price_corridor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    import httpx
    from deal_scanner_scheduler import main

    profiles = []
    requests = []
    closed = []

    class FakeProvider:
        platform = "ebay"

        async def discover(self, profile):
            profiles.append(profile)
            for _ in range(60):
                yield None

        async def normalize(self, snapshot):
            return SimpleNamespace(
                platform="ebay",
                url="https://www.ebay.de/itm/123",
                title="Icy Dock MB522SP gebraucht",
                description="",
                shipping_cost=None,
                price=SimpleNamespace(amount=30, currency="EUR"),
            )

        async def close(self):
            closed.append(True)

    def handler(request):
        if request.url.path.endswith("provider-configurations"):
            return httpx.Response(200, json=[])
        if request.url.path.endswith("targets"):
            return httpx.Response(200, json=[{"id": "test", "query": "icy dock mb522sp"}])
        import json

        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, json={"accepted": 0, "examined": len(body["candidates"])})

    monkeypatch.setattr(main, "EbayProvider", lambda settings: FakeProvider())
    scheduler = main.Scheduler(
        main.SchedulerSettings(
            ebay_client_id="fixture",
            ebay_client_secret="fixture",  # noqa: S106 -- non-secret test credential
            ebay_environment="production",
            kleinanzeigen_web_enabled=False,
        )
    )
    await scheduler.client.aclose()
    scheduler.client = httpx.AsyncClient(base_url="https://scanner.test", transport=httpx.MockTransport(handler))
    try:
        await scheduler.research_market_prices()
    finally:
        await scheduler.client.aclose()
    assert len(requests[0]["candidates"]) == 20
    assert profiles[0].minimum_price is None and profiles[0].maximum_price is None
    assert closed == [True]
