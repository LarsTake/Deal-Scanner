import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest

os.environ["DEAL_SCANNER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEAL_SCANNER_AUTO_CREATE_DB"] = "true"
os.environ["DEAL_SCANNER_AUTH_MODE"] = "development"

from deal_scanner_api import notification_service
from deal_scanner_api.database import session_factory
from deal_scanner_api.db_models import ListingRow, NotificationDeliveryRow, NotificationRow
from deal_scanner_api.main import app
from fastapi.testclient import TestClient


def offer(external_id: str, profile_id: str, run_id: str | None = None) -> dict[str, object]:
    return {
        "platform": "kleinanzeigen",
        "externalId": external_id,
        "url": "https://www.kleinanzeigen.de/s-anzeige/gaming/1234567890-228-1234",
        "title": "Gaming PC RTX 4070",
        "description": "Abholung und Test möglich",
        "price": "100.00",
        "categoryProfile": "computer",
        "searchProfileId": profile_id,
        "providerSyncRunId": run_id,
    }


def observations(client: TestClient, listing_id: str) -> None:
    for amount in ("900", "1000", "1100"):
        response = client.post(
            "/api/v1/price-observations",
            json={
                "listingId": listing_id,
                "platform": "manual",
                "observedPrice": amount,
                "currency": "EUR",
                "observationKind": "soldConfirmed",
                "observedAt": datetime.now(UTC).isoformat(),
            },
        )
        assert response.status_code == 201, response.text


def test_first_scan_is_silent_but_price_change_after_completed_scan_can_notify() -> None:
    with TestClient(app) as client:
        profile = client.post(
            "/api/v1/search-profiles",
            json={
                "name": "Baseline",
                "query": "gaming",
                "minimumDealScore": 0,
            },
        ).json()
        first = client.post(
            "/api/v1/provider-sync-runs",
            json={
                "provider": "kleinanzeigen",
                "searchProfileId": profile["id"],
            },
        ).json()
        body = offer("baseline", profile["id"], first["id"])
        imported = client.post("/api/v1/imports/manual", json=body)
        assert imported.status_code == 201, imported.text
        listing_id = imported.json()["listing"]["id"]
        observations(client, listing_id)
        result = client.post(f"/api/v1/listings/{listing_id}/evaluate").json()
        assert result["dealScore"] is not None
        assert result["notificationCreated"] is False
        assert (
            client.patch(
                f"/api/v1/provider-sync-runs/{first['id']}",
                json={
                    "status": "COMPLETED",
                    "discoveredCount": 1,
                    "importedCount": 1,
                },
            ).status_code
            == 200
        )
        second = client.post(
            "/api/v1/provider-sync-runs",
            json={
                "provider": "kleinanzeigen",
                "searchProfileId": profile["id"],
            },
        ).json()
        body["providerSyncRunId"] = second["id"]
        assert client.post("/api/v1/imports/manual", json=body).json()["snapshotCreated"] is False
        body["price"] = "90.00"
        assert client.post("/api/v1/imports/manual", json=body).json()["snapshotCreated"] is True
        assert client.post(f"/api/v1/listings/{listing_id}/evaluate").json()["notificationCreated"] is True
        pending = client.get("/api/v1/notifications?pending_only=true").json()
        item = next(item for item in pending if item["listingId"] == listing_id)
        assert client.post(f"/api/v1/notifications/{item['id']}/delivered").status_code == 204
        assert not any(
            item["listingId"] == listing_id for item in client.get("/api/v1/notifications?pending_only=true").json()
        )


def test_notify_on_first_run_is_configurable_and_invalid_run_is_rejected() -> None:
    with TestClient(app) as client:
        profile = client.post(
            "/api/v1/search-profiles",
            json={
                "name": "Notify first",
                "query": "gaming",
                "minimumDealScore": 0,
                "notificationSettings": {"notifyOnFirstRun": True},
            },
        ).json()
        run = client.post(
            "/api/v1/provider-sync-runs",
            json={
                "provider": "kleinanzeigen",
                "searchProfileId": profile["id"],
            },
        ).json()
        body = offer("notify-first", profile["id"], run["id"])
        imported = client.post("/api/v1/imports/manual", json=body).json()
        listing_id = imported["listing"]["id"]
        observations(client, listing_id)
        assert client.post(f"/api/v1/listings/{listing_id}/evaluate").json()["notificationCreated"] is True
        body["providerSyncRunId"] = "00000000-0000-4000-8000-000000000999"
        assert client.post("/api/v1/imports/manual", json=body).status_code == 422


def test_archive_preserves_favorites_manual_hides_and_restores_reappearing_offers() -> None:
    with TestClient(app) as client:
        profile = client.post("/api/v1/search-profiles", json={"name": "Archive", "query": "pc"}).json()
        bodies = [offer(f"archive-{index}", profile["id"]) for index in range(3)]
        ids = [client.post("/api/v1/imports/manual", json=body).json()["listing"]["id"] for body in bodies]

        async def age() -> None:
            async with session_factory() as session:
                for index, listing_id in enumerate(ids):
                    row = await session.get(ListingRow, UUID(listing_id))
                    assert row is not None
                    row.first_seen_at = datetime.now(UTC) - timedelta(days=30)
                    row.last_seen_at = datetime.now(UTC) - timedelta(days=3)
                    row.is_favorite = index == 1
                    row.is_hidden = index == 2
                await session.commit()

        asyncio.run(age())
        result = client.post("/api/v1/listings/maintenance/archive")
        assert result.status_code == 200
        assert result.json()["archived"] == 1
        assert client.get(f"/api/v1/listings/{ids[0]}").json()["isHidden"] is True
        assert client.get(f"/api/v1/listings/{ids[1]}").json()["isHidden"] is False
        client.post("/api/v1/imports/manual", json=bodies[0])
        client.post("/api/v1/imports/manual", json=bodies[2])
        assert client.get(f"/api/v1/listings/{ids[0]}").json()["isHidden"] is False
        assert client.get(f"/api/v1/listings/{ids[2]}").json()["isHidden"] is True


def test_ntfy_dispatch_batches_large_burst_and_does_not_repeat(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[httpx.Request] = []
    original_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    monkeypatch.setattr(notification_service.get_settings(), "ntfy_url", "https://ntfy.example.test/topic")
    monkeypatch.setattr(
        notification_service.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    with TestClient(app) as client:
        workspace = client.post("/api/v1/search-profiles", json={"name": "Dispatch", "query": "pc"}).json()[
            "workspaceId"
        ]

        async def enqueue() -> None:
            async with session_factory() as session:
                for index in range(6):
                    row = NotificationRow(workspace_id=UUID(workspace), reason={"title": f"Offer {index}"})
                    session.add(row)
                    await session.flush()
                    session.add(
                        NotificationDeliveryRow(
                            workspace_id=UUID(workspace),
                            notification_id=row.id,
                            channel="ntfy",
                            status="PENDING",
                            attempts=0,
                        )
                    )
                await session.commit()

        asyncio.run(enqueue())
        assert client.post("/api/v1/notifications/dispatch").json()["delivered"] == 6
        assert len(requests) == 1
        assert "6" in requests[0].headers["Title"]
        assert client.post("/api/v1/notifications/dispatch").json()["delivered"] == 0
        assert len(requests) == 1
