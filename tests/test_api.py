import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

os.environ["DEAL_SCANNER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEAL_SCANNER_AUTO_CREATE_DB"] = "true"
os.environ["DEAL_SCANNER_AUTH_MODE"] = "development"

from deal_scanner_api.database import session_factory
from deal_scanner_api.db_models import AnalysisJobRow, ListingImageRow
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


def set_job_times(job_id: str, *, expire_lease: bool = False, make_available: bool = False) -> None:
    async def update() -> None:
        async with session_factory() as session:
            job = await session.get(AnalysisJobRow, UUID(job_id))
            assert job is not None
            if expire_lease:
                job.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            if make_available:
                job.available_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()

    asyncio.run(update())


def add_erp_image(listing_id: str, workspace_id: str) -> None:
    async def insert() -> None:
        async with session_factory() as session:
            session.add(
                ListingImageRow(
                    workspace_id=UUID(workspace_id),
                    listing_id=UUID(listing_id),
                    source_url="https://img.kleinanzeigen.de/erp-fixture.png",
                    storage_path="fixture/erp-image.png",
                    sha256_hash="a" * 64,
                    perceptual_hash="b" * 16,
                    width=1280,
                    height=720,
                    mime_type="image/png",
                    analysis_status="COMPLETED",
                )
            )
            await session.commit()

    asyncio.run(insert())


def test_end_to_end_import_feedback_and_worker_lease() -> None:
    with TestClient(app) as client:
        live = client.get("/api/v1/health/live")
        assert live.status_code == 200
        assert live.headers["x-content-type-options"] == "nosniff"
        assert live.headers["x-frame-options"] == "DENY"
        assert live.headers["x-request-id"]
        assert int(live.headers["x-ratelimit-remaining"]) >= 0

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


def test_worker_lease_renew_crash_retry_dead_letter_and_late_completion() -> None:
    headers = {"X-Development-User": "00000000-0000-4000-8000-000000000909"}
    target = payload()
    target["externalId"] = "lease-lifecycle"
    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/manual", headers=headers, json=target)
        assert imported.status_code == 201, imported.text
        first_worker = client.post(
            "/api/v1/workers/register",
            headers=headers,
            json={
                "name": "lease-one",
                "operatingSystem": "test",
                "hostname": "lease-one",
                "capabilities": ["text-small"],
            },
        ).json()
        second_worker = client.post(
            "/api/v1/workers/register",
            headers=headers,
            json={
                "name": "lease-two",
                "operatingSystem": "test",
                "hostname": "lease-two",
                "capabilities": ["text-small"],
            },
        ).json()
        claimed = client.post(
            "/api/v1/jobs/claim",
            headers=headers,
            json={"workerId": first_worker["id"], "capabilities": ["text-small"]},
        ).json()
        original_expiry = claimed["leaseExpiresAt"]
        renewed = client.post(
            f"/api/v1/jobs/{claimed['id']}/renew",
            headers=headers,
            json={"workerId": first_worker["id"]},
        )
        assert renewed.status_code == 200, renewed.text
        assert renewed.json()["leaseExpiresAt"] >= original_expiry

        set_job_times(claimed["id"], expire_lease=True)
        recovery = client.post(
            "/api/v1/jobs/claim",
            headers=headers,
            json={"workerId": second_worker["id"], "capabilities": ["text-small"]},
        )
        assert recovery.status_code == 200
        assert recovery.json() is None
        retry_job = next(
            item
            for item in client.get("/api/v1/jobs?status=RETRY", headers=headers).json()
            if item["id"] == claimed["id"]
        )
        assert retry_job["attempts"] == 1

        set_job_times(claimed["id"], make_available=True)
        second_claim = client.post(
            "/api/v1/jobs/claim",
            headers=headers,
            json={"workerId": second_worker["id"], "capabilities": ["text-small"]},
        ).json()
        assert second_claim["id"] == claimed["id"]
        late = client.post(
            f"/api/v1/jobs/{claimed['id']}/complete",
            headers=headers,
            json={
                "workerId": first_worker["id"],
                "analysisType": "text",
                "modelName": "late",
                "modelVersion": "1",
                "promptVersion": "1",
                "resultSchemaVersion": "1.0.0",
                "inputHash": claimed["inputHash"],
                "result": {},
                "confidence": 0,
            },
        )
        assert late.status_code == 409

        failed = client.post(
            f"/api/v1/jobs/{claimed['id']}/fail",
            headers=headers,
            json={"workerId": second_worker["id"], "error": "simulated crash"},
        )
        assert failed.status_code == 200
        assert failed.json()["status"] == "RETRY"
        set_job_times(claimed["id"], make_available=True)
        third_claim = client.post(
            "/api/v1/jobs/claim",
            headers=headers,
            json={"workerId": second_worker["id"], "capabilities": ["text-small"]},
        ).json()
        assert third_claim["attempts"] == 3
        dead = client.post(
            f"/api/v1/jobs/{claimed['id']}/fail",
            headers=headers,
            json={"workerId": second_worker["id"], "error": "third failure"},
        )
        assert dead.status_code == 200
        assert dead.json()["status"] == "DEAD"


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


def test_system_status_reports_all_required_components_without_secrets() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/system/status")
        assert response.status_code == 200, response.text
        body = response.json()
        assert set(body["components"]) == {
            "api",
            "database",
            "supabase",
            "emailImporter",
            "ebay",
            "worker",
            "ollama",
            "storage",
        }
        serialized = response.text.lower()
        assert "secret" not in serialized
        assert "token" not in serialized


def test_new_external_id_with_copied_description_creates_duplicate_signal() -> None:
    copied_text = (
        "Einmaliger Fixture-Text für die Dublettenprüfung mit Rechnung, Originalverpackung, "
        "vollständigem Zubehör und Abholung nach vorheriger Funktionsprüfung vor Ort."
    )
    first = payload(copied_text)
    first["externalId"] = "copy-source-listing"
    first["url"] = "https://www.kleinanzeigen.de/s-anzeige/gaming-pc/2234567890-228-1234"
    second = payload(copied_text)
    second["externalId"] = "copy-target-listing"
    second["url"] = "https://www.kleinanzeigen.de/s-anzeige/gaming-pc/3234567890-228-1234"
    with TestClient(app) as client:
        assert client.post("/api/v1/imports/manual", json=first).status_code == 201
        imported = client.post("/api/v1/imports/manual", json=second)
        assert imported.status_code == 201, imported.text
        listing = imported.json()["listing"]
        duplicate = next(signal for signal in listing["riskSignals"] if signal["type"] == "duplicate_description")
        assert duplicate["source"] == "deduplication-v1"
        assert duplicate["confidence"] == 0.95
        assert listing["riskScore"] > 0


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
        notification = next(item for item in notifications.json() if item["listingId"] == listing_id)
        delivered = client.post(f"/api/v1/notifications/{notification['id']}/delivered")
        assert delivered.status_code == 204, delivered.text
        summary = next(item for item in client.get("/api/v1/listings").json()["items"] if item["id"] == listing_id)
        assert summary["marketValueMedian"] == "1000.00"
        assert summary["dataQualityScore"] > 0
        assert isinstance(summary["detectedProducts"], list)
        assert isinstance(summary["warnings"], list)


def test_erp_mock_uses_stable_purchase_contract() -> None:
    target = payload()
    target["externalId"] = "erp-contract-listing"
    target["seller"] = {
        "externalId": "erp-seller-1",
        "displayName": "ERP Testverkäufer",
        "location": "Berlin",
        "ratingScore": "99.50",
        "reviewCount": 42,
    }
    with TestClient(app) as client:
        listing = client.post("/api/v1/imports/manual", json=target).json()["listing"]
        listing_id = listing["id"]
        add_erp_image(listing_id, listing["workspaceId"])
        response = client.post(f"/api/v1/erp/exports/{listing_id}")
        assert response.status_code == 200, response.text
        export = response.json()
        assert export["status"] == "mocked"
        assert export["purchasePayload"]["formatVersion"] == "erp-purchase-v1"
        assert export["purchasePayload"]["relationships"]["listingId"] == listing_id
        assert export["purchasePayload"]["seller"]["externalId"] == "erp-seller-1"
        assert export["purchasePayload"]["seller"]["ratingScore"] == "99.50"
        assert export["purchasePayload"]["images"][0]["sha256Hash"] == "a" * 64
        assert any(component["model"] == "RTX 4070 Super" for component in export["purchasePayload"]["components"])
        assert export["purchasePayload"]["marketValue"]["riskScore"] == 0


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
                    "riskSignals": [
                        {
                            "signalType": "external_payment_link",
                            "severity": "high",
                            "confidence": 0.99,
                            "source": "description",
                            "evidence": "externer Zahlungslink",
                        }
                    ],
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
        assert detail.json()["riskScore"] > 0
        assert any(signal["type"] == "external_payment_link" for signal in detail.json()["riskSignals"])
        components = detail.json()["evaluations"][0]["explanation"]["deal"]["components"]
        assert components["condition"] != 50
        assert components["completeness"] != 50
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


def test_manual_product_correction_updates_canonical_detail_and_preserves_history() -> None:
    correction_payload = payload()
    correction_payload["externalId"] = "manual-product-correction"
    correction_payload["title"] = "Unklar bezeichnetes Simracing Bundle"
    correction_payload["description"] = "Vom Nutzer später geprüft"
    correction_payload["categoryProfile"] = "simracing"
    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/manual", json=correction_payload)
        assert imported.status_code == 201, imported.text
        listing = imported.json()["listing"]
        corrected = client.post(
            f"/api/v1/listings/{listing['id']}/feedback",
            json={
                "feedbackType": "correctedComponents",
                "baseListingVersion": listing["version"],
                "correctedProducts": [
                    {
                        "productType": "quick_release",
                        "manufacturer": "Fanatec",
                        "model": "QR2",
                        "quantity": 1,
                        "evidence": "QR2 am Produkt fotografisch geprüft",
                    }
                ],
                "correctedAttributes": [{"productIndex": 0, "key": "material", "value": "Metall", "unit": None}],
                "note": "Manuelle Korrektur im Detaildialog",
            },
        )
        assert corrected.status_code == 201, corrected.text
        assert corrected.json()["version"] == listing["version"] + 1

        detail = client.get(f"/api/v1/listings/{listing['id']}")
        assert detail.status_code == 200, detail.text
        body = detail.json()
        corrected_product = next(
            product for product in body["products"] if product["detectionSource"].startswith("user-correction:")
        )
        assert corrected_product["model"] == "QR2"
        assert corrected_product["confidence"] == 1
        assert corrected_product["attributes"][0]["attributeKey"] == "material"
        assert corrected_product["attributes"][0]["value"] == "Metall"
        assert any(result["analysisType"] == "user_correction" for result in body["analysisResults"])
        assert any(entry["feedbackType"] == "correctedComponents" for entry in body["feedback"])
        assert len(body["snapshots"]) == 1
        assert body["evaluations"]


def test_search_profile_filters_and_notification_age_threshold_roundtrip() -> None:
    with TestClient(app) as client:
        profile = client.post(
            "/api/v1/search-profiles",
            json={
                "name": "Regional und aktuell",
                "query": "RTX 4070 Super",
                "categoryProfile": "computer",
                "location": "Hamburg",
                "radiusKm": 50,
                "requiredTerms": ["Rechnung"],
                "excludedTerms": ["defekt"],
                "requiredProducts": ["RTX 4070 Super"],
                "excludedProducts": ["RTX 4070 Ti"],
                "notificationSettings": {
                    "minimumMarketAdvantagePercent": "15",
                    "maximumListingAgeHours": 24,
                    "desktopEnabled": True,
                    "ntfyEnabled": False,
                },
            },
        )
        assert profile.status_code == 201, profile.text
        created_profile = profile.json()
        assert created_profile["location"] == "Hamburg"
        assert created_profile["requiredProducts"] == ["RTX 4070 Super"]
        assert created_profile["notificationSettings"]["maximumListingAgeHours"] == 24

        target = payload("Rechnung vorhanden")
        target["externalId"] = "notification-age-filter"
        target["price"] = "100.00"
        target["publishedAt"] = "2026-01-01T00:00:00Z"
        target["searchProfileId"] = created_profile["id"]
        listing_id = client.post("/api/v1/imports/manual", json=target).json()["listing"]["id"]
        for index, price in enumerate(("900.00", "1000.00", "1100.00")):
            response = client.post(
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
            assert response.status_code == 201, response.text
        evaluated = client.post(f"/api/v1/listings/{listing_id}/evaluate")
        assert evaluated.status_code == 200, evaluated.text
        assert evaluated.json()["dealScore"] >= 75
        assert evaluated.json()["notificationCreated"] is False


def test_visible_seller_data_is_upserted_without_penalizing_missing_data() -> None:
    seller_payload = payload()
    seller_payload["externalId"] = "seller-roundtrip"
    seller_payload["seller"] = {
        "externalId": "visible-seller-42",
        "displayName": "Privater Anbieter",
        "accountAgeText": "Aktiv seit 2018",
        "ratingText": "Sehr zufrieden",
        "ratingScore": "98.5",
        "reviewCount": 123,
        "location": "Hamburg",
        "rawData": {"visible": True},
    }
    with TestClient(app) as client:
        imported = client.post("/api/v1/imports/manual", json=seller_payload)
        assert imported.status_code == 201, imported.text
        listing_id = imported.json()["listing"]["id"]
        detail = client.get(f"/api/v1/listings/{listing_id}").json()
        assert detail["seller"]["externalId"] == "visible-seller-42"
        assert detail["seller"]["reviewCount"] == 123
        assert detail["seller"]["ratingScore"] == "98.50"
        assert detail["riskScore"] == 0

        seller_payload["description"] = "Aktualisierte sichtbare Daten"
        seller_payload["seller"]["reviewCount"] = 124
        updated = client.post("/api/v1/imports/manual", json=seller_payload)
        assert updated.status_code == 201, updated.text
        refreshed = client.get(f"/api/v1/listings/{listing_id}").json()
        assert refreshed["seller"]["id"] == detail["seller"]["id"]
        assert refreshed["seller"]["reviewCount"] == 124


def test_provider_configuration_references_but_never_accepts_secrets() -> None:
    with TestClient(app) as client:
        configured = client.put(
            "/api/v1/provider-configurations/ebay",
            json={
                "enabled": True,
                "settings": {"environment": "sandbox", "marketplaceId": "EBAY_DE"},
                "secretReference": "env:DEAL_SCANNER_EBAY_CLIENT_SECRET",
            },
        )
        assert configured.status_code == 200, configured.text
        assert configured.json()["settings"]["marketplaceId"] == "EBAY_DE"
        listed = client.get("/api/v1/provider-configurations")
        assert listed.status_code == 200, listed.text
        assert any(item["provider"] == "ebay" for item in listed.json())

        rejected = client.put(
            "/api/v1/provider-configurations/ebay",
            json={"enabled": True, "settings": {"clientSecret": "must-not-be-stored"}},
        )
        assert rejected.status_code == 422
        unsupported = client.put(
            "/api/v1/provider-configurations/unknown",
            json={"enabled": True},
        )
        assert unsupported.status_code == 422
