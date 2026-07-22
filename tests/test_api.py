import os

os.environ["DEAL_SCANNER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEAL_SCANNER_AUTO_CREATE_DB"] = "true"
os.environ["DEAL_SCANNER_AUTH_MODE"] = "development"

from deal_scanner_api.main import app
from fastapi.testclient import TestClient


def payload(description: str = "Abholung möglich") -> dict[str, object]:
    return {
        "platform": "kleinanzeigen",
        "externalId": "fixture-listing-1",
        "url": "https://www.kleinanzeigen.de/s-anzeige/gaming-pc/1234567890-228-1234",
        "title": "Gaming PC RTX4070S",
        "description": description,
        "price": "499.00",
        "shippingCost": "0.00",
        "currency": "EUR",
        "categoryProfile": "computer",
        "rawData": {"fixture": True},
    }


def test_end_to_end_import_feedback_and_worker_lease() -> None:
    with TestClient(app) as client:
        assert client.get("/api/v1/health/live").status_code == 200

        profile = client.post(
            "/api/v1/search-profiles",
            json={"name": "Gaming PCs", "query": "RTX 4070 Super", "categoryProfile": "computer"},
        )
        assert profile.status_code == 201, profile.text

        imported = client.post("/api/v1/imports/manual", json=payload())
        assert imported.status_code == 201, imported.text
        body = imported.json()
        assert body["snapshotCreated"] is True
        assert body["listing"]["riskScore"] == 0
        listing_id = body["listing"]["id"]

        duplicate = client.post("/api/v1/imports/manual", json=payload())
        assert duplicate.status_code == 201
        assert duplicate.json()["snapshotCreated"] is False

        changed = client.post("/api/v1/imports/manual", json=payload("Nur PayPal Freunde, muss heute weg"))
        assert changed.status_code == 201
        assert changed.json()["listing"]["version"] == 2
        assert changed.json()["listing"]["riskScore"] > 0

        stale_feedback = client.post(
            f"/api/v1/listings/{listing_id}/feedback",
            json={"feedbackType": "goodDeal", "baseListingVersion": 1},
        )
        assert stale_feedback.status_code == 409

        worker = client.post(
            "/api/v1/workers/register",
            json={
                "name": "test-worker",
                "operatingSystem": "test",
                "hostname": "test-host",
                "capabilities": ["text-small"],
            },
        )
        assert worker.status_code == 201, worker.text
        worker_id = worker.json()["id"]
        job = client.post(
            "/api/v1/jobs/claim",
            json={"workerId": worker_id, "capabilities": ["text-small"]},
        )
        assert job.status_code == 200, job.text
        assert job.json()["status"] == "LEASED"
        rejected = client.post(
            f"/api/v1/jobs/{job.json()['id']}/complete",
            json={
                "workerId": worker_id,
                "analysisType": "text",
                "modelName": "fixture",
                "modelVersion": "1",
                "promptVersion": "1",
                "resultSchemaVersion": "1.0.0",
                "inputHash": job.json()["inputHash"],
                "result": {"inventedPrice": 9999},
                "confidence": 1,
            },
        )
        assert rejected.status_code == 422


def test_idempotency_and_extension_pairing() -> None:
    with TestClient(app) as client:
        request_payload = payload()
        request_payload["externalId"] = "idempotent-listing"
        first = client.post(
            "/api/v1/imports/manual",
            headers={"Idempotency-Key": "stable-key"},
            json=request_payload,
        )
        assert first.status_code == 201, first.text
        repeated = client.post(
            "/api/v1/imports/manual",
            headers={"Idempotency-Key": "stable-key"},
            json=request_payload,
        )
        assert repeated.status_code == 201
        assert repeated.json()["snapshotCreated"] is False

        changed_payload = {**request_payload, "price": "599.00"}
        conflict = client.post(
            "/api/v1/imports/manual",
            headers={"Idempotency-Key": "stable-key"},
            json=changed_payload,
        )
        assert conflict.status_code == 409

        pairing = client.post("/api/v1/extension/pairings")
        assert pairing.status_code == 201, pairing.text
        browser_payload = payload()
        browser_payload["externalId"] = "browser-paired-listing"
        paired_import = client.post(
            "/api/v1/imports/browser",
            headers={"X-Extension-Pairing": pairing.json()["token"]},
            json=browser_payload,
        )
        assert paired_import.status_code == 201, paired_import.text


def test_market_data_csv_import() -> None:
    csv_content = (
        "platform;observedPrice;shippingCost;currency;observationKind;observedAt;sourceQuality\n"
        "manual;540.00;0;EUR;soldConfirmed;2026-07-20T12:00:00Z;1.0\n"
        "manual;515.00;5;EUR;manualSold;2026-07-18T12:00:00Z;0.8\n"
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/market-data/imports/csv",
            files={"file": ("market.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 201, response.text
        assert response.json()["rowsImported"] == 2


def test_workspace_isolation_at_api_boundary() -> None:
    first_user = {"X-Development-User": "00000000-0000-4000-8000-000000000101"}
    second_user = {"X-Development-User": "00000000-0000-4000-8000-000000000202"}
    isolated_payload = payload()
    isolated_payload["externalId"] = "workspace-one-only"
    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/manual", headers=first_user, json=isolated_payload)
        assert imported.status_code == 201
        first_list = client.get("/api/v1/listings", headers=first_user).json()
        second_list = client.get("/api/v1/listings", headers=second_user).json()
        assert any(item["externalId"] == "workspace-one-only" for item in first_list["items"])
        assert all(item["externalId"] != "workspace-one-only" for item in second_list["items"])


def test_evaluation_keeps_risk_separate_and_creates_notification() -> None:
    evaluation_payload = payload("Abholung und Test möglich")
    evaluation_payload["externalId"] = "evaluation-listing"
    evaluation_payload["price"] = "100.00"
    with TestClient(app) as client:
        listing_id = client.post("/api/v1/imports/manual", json=evaluation_payload).json()["listing"]["id"]
        for index, price in enumerate(("900.00", "1000.00", "1100.00")):
            observed = client.post(
                "/api/v1/price-observations",
                json={
                    "listingId": listing_id,
                    "platform": "manual",
                    "observedPrice": price,
                    "currency": "EUR",
                    "observationKind": "soldConfirmed",
                    "observedAt": f"2026-07-{18 + index}T12:00:00Z",
                },
            )
            assert observed.status_code == 201, observed.text
        evaluated = client.post(f"/api/v1/listings/{listing_id}/evaluate")
        assert evaluated.status_code == 200, evaluated.text
        assert evaluated.json()["dealScore"] >= 75
        assert evaluated.json()["riskScore"] == 0
        assert evaluated.json()["notificationCreated"] is True
        notifications = client.get("/api/v1/notifications")
        assert any(item["listingId"] == listing_id for item in notifications.json())


def test_worker_completion_canonicalizes_product_and_evaluates_automatically() -> None:
    target = payload("Abholung und Funktionstest möglich")
    target["externalId"] = "automatic-evaluation-listing"
    target["price"] = "100.00"
    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/manual", json=target)
        assert imported.status_code == 201, imported.text
        listing_id = imported.json()["listing"]["id"]

        products = client.get("/api/v1/products")
        assert products.status_code == 200, products.text
        gpu = next(item for item in products.json()["items"] if item["model"] == "RTX 4070 Super")
        for index, price in enumerate(("900.00", "1000.00", "1100.00")):
            observed = client.post(
                "/api/v1/price-observations",
                json={
                    "canonicalProductId": gpu["id"],
                    "platform": "manual",
                    "observedPrice": price,
                    "currency": "EUR",
                    "observationKind": "soldConfirmed",
                    "observedAt": f"2026-07-{18 + index}T12:00:00Z",
                },
            )
            assert observed.status_code == 201, observed.text

        reanalysis = client.post(f"/api/v1/listings/{listing_id}/reanalyze")
        assert reanalysis.status_code == 201, reanalysis.text
        worker = client.post(
            "/api/v1/workers/register",
            json={
                "name": "automatic-worker",
                "operatingSystem": "test",
                "hostname": "automatic-host",
                "capabilities": ["text-small"],
            },
        )
        worker_id = worker.json()["id"]
        job = client.post(
            "/api/v1/jobs/claim",
            json={"workerId": worker_id, "capabilities": ["text-small"]},
        )
        assert job.status_code == 200, job.text
        assert job.json()["listingId"] == listing_id
        completed = client.post(
            f"/api/v1/jobs/{job.json()['id']}/complete",
            json={
                "workerId": worker_id,
                "analysisType": "text",
                "modelName": "fixture",
                "modelVersion": "1",
                "promptVersion": "1",
                "resultSchemaVersion": "1.0.0",
                "inputHash": job.json()["inputHash"],
                "result": {
                    "category": "computer",
                    "products": [
                        {
                            "productType": "gpu",
                            "manufacturer": "NVIDIA",
                            "model": "RTX 4070S",
                            "quantity": 1,
                            "confidence": 0.99,
                            "sources": ["title"],
                            "evidence": "RTX4070S",
                        }
                    ],
                    "attributes": [],
                    "riskSignals": [],
                    "contradictions": [],
                    "missingInformation": [],
                    "overallConfidence": 0.99,
                    "schemaVersion": "1.0.0",
                },
                "confidence": 0.99,
            },
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "COMPLETE"

        detail = client.get(f"/api/v1/listings/{listing_id}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["analysisStatus"] == "COMPLETE"
        assert detail.json()["dealScore"] >= 75
        notifications = client.get("/api/v1/notifications").json()
        assert any(item["listingId"] == listing_id for item in notifications)

        duplicate_evaluation = client.post(f"/api/v1/listings/{listing_id}/evaluate")
        assert duplicate_evaluation.status_code == 200, duplicate_evaluation.text
        assert duplicate_evaluation.json()["notificationCreated"] is False


def test_provider_sync_and_mail_import_history_are_persisted() -> None:
    with TestClient(app) as client:
        profile = client.post(
            "/api/v1/search-profiles",
            json={"name": "Persisted sync", "query": "RTX 4070 Super", "categoryProfile": "computer"},
        )
        assert profile.status_code == 201, profile.text
        profile_id = profile.json()["id"]
        created = client.post(
            "/api/v1/provider-sync-runs",
            json={"searchProfileId": profile_id, "provider": "ebay", "cursor": "50"},
        )
        assert created.status_code == 201, created.text
        run_id = created.json()["id"]
        completed = client.patch(
            f"/api/v1/provider-sync-runs/{run_id}",
            json={
                "status": "COMPLETED",
                "cursor": "100",
                "discoveredCount": 50,
                "importedCount": 47,
            },
        )
        assert completed.status_code == 200, completed.text
        history = client.get(
            "/api/v1/provider-sync-runs",
            params={"provider": "ebay", "searchProfileId": profile_id, "limit": 1},
        )
        assert history.status_code == 200, history.text
        assert history.json()["items"][0]["cursor"] == "100"
        assert history.json()["items"][0]["importedCount"] == 47
        assert (
            client.patch(
                f"/api/v1/provider-sync-runs/{run_id}",
                json={"status": "FAILED"},
            ).status_code
            == 409
        )

        mail_payload = {
            "messageId": "<fixture-history@example.test>",
            "sender": "Kleinanzeigen <mail@kleinanzeigen.de>",
            "subject": "Neue Treffer",
            "receivedAt": "2026-07-22T12:00:00Z",
            "rawStoragePath": "workspace/mail.eml",
            "rawSha256": "a" * 64,
            "parserVersion": "kleinanzeigen-mail-v1",
            "status": "IMPORTED",
            "parsedData": {"listingUrl": "https://www.kleinanzeigen.de/s-anzeige/test/1-2-3"},
        }
        recorded = client.post("/api/v1/mail-imports", json=mail_payload)
        assert recorded.status_code == 201, recorded.text
        repeated = client.post("/api/v1/mail-imports", json=mail_payload)
        assert repeated.status_code == 201, repeated.text
        assert repeated.json()["id"] == recorded.json()["id"]
        mail_history = client.get("/api/v1/mail-imports")
        assert mail_history.status_code == 200, mail_history.text
        assert any(item["messageId"] == mail_payload["messageId"] for item in mail_history.json())


def test_listing_views_follow_versioned_favorite_and_hidden_feedback() -> None:
    view_payload = payload()
    view_payload["externalId"] = "listing-view-state"
    with TestClient(app) as client:
        listing = client.post("/api/v1/imports/manual", json=view_payload).json()["listing"]
        listing_id = listing["id"]
        favorite = client.post(
            f"/api/v1/listings/{listing_id}/feedback",
            json={"feedbackType": "favorite", "baseListingVersion": listing["version"]},
        )
        assert favorite.status_code == 201, favorite.text
        assert favorite.json()["version"] == 2
        favorites = client.get("/api/v1/listings", params={"view": "favorites"}).json()["items"]
        assert any(item["id"] == listing_id and item["isFavorite"] for item in favorites)

        hidden = client.post(
            f"/api/v1/listings/{listing_id}/feedback",
            json={"feedbackType": "hide", "baseListingVersion": 2},
        )
        assert hidden.status_code == 201, hidden.text
        assert hidden.json()["version"] == 3
        assert all(item["id"] != listing_id for item in client.get("/api/v1/listings").json()["items"])
        hidden_items = client.get("/api/v1/listings", params={"view": "hidden"}).json()["items"]
        assert any(item["id"] == listing_id and item["isHidden"] for item in hidden_items)

        unhidden = client.post(
            f"/api/v1/listings/{listing_id}/feedback",
            json={"feedbackType": "unhide", "baseListingVersion": 3},
        )
        assert unhidden.status_code == 201, unhidden.text
        assert any(item["id"] == listing_id for item in client.get("/api/v1/listings").json()["items"])
