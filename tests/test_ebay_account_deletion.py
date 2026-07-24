from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

os.environ["DEAL_SCANNER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEAL_SCANNER_AUTO_CREATE_DB"] = "true"
os.environ["DEAL_SCANNER_AUTH_MODE"] = "development"

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from deal_scanner_api.database import session_factory
from deal_scanner_api.db_models import (
    EbayAccountDeletionEventRow,
    ListingImageRow,
    ListingRow,
    SellerRow,
)
from deal_scanner_api.ebay_account_deletion import EbayNotificationVerifier, challenge_response
from deal_scanner_api.main import app
from deal_scanner_api.routers import ebay_notifications
from deal_scanner_api.settings import Settings
from fastapi.testclient import TestClient
from sqlalchemy import select

ENDPOINT_URL = "https://graper.example/api/v1/webhooks/ebay/account-deletion"
VERIFICATION_TOKEN = "account_deletion_fixture_token_123456789"  # noqa: S105


class StaticKeyVerifier(EbayNotificationVerifier):
    def __init__(self, settings: Settings, public_key: bytes) -> None:
        super().__init__(settings)
        self._fixture_public_key = public_key

    async def _get_public_key(self, key_id: str) -> bytes:
        assert key_id == "fixture-key"
        return self._fixture_public_key


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        ebay_deletion_endpoint_url=ENDPOINT_URL,
        ebay_deletion_verification_token=VERIFICATION_TOKEN,
        image_storage_dir=str(tmp_path),
    )


def _signature_header(payload: dict[str, Any], private_key: ec.EllipticCurvePrivateKey) -> str:
    message = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    signature = private_key.sign(message, ec.ECDSA(hashes.SHA1()))  # noqa: S303
    envelope = {
        "kid": "fixture-key",
        "signature": base64.b64encode(signature).decode(),
    }
    return base64.b64encode(json.dumps(envelope, separators=(",", ":")).encode()).decode()


def _event(notification_id: str, username: str) -> dict[str, Any]:
    return {
        "metadata": {
            "topic": "MARKETPLACE_ACCOUNT_DELETION",
            "schemaVersion": "1.0",
        },
        "notification": {
            "notificationId": notification_id,
            "eventDate": "2026-07-24T12:00:00Z",
            "publishDate": "2026-07-24T12:00:01Z",
            "publishAttemptCount": 1,
            "data": {
                "username": username,
                "userId": f"{username}-id",
                "eiasToken": f"{username}-eias",
            },
        },
    }


def test_challenge_response_uses_the_exact_configured_endpoint(monkeypatch: Any, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(ebay_notifications, "get_settings", lambda: settings)
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/webhooks/ebay/account-deletion",
            params={"challenge_code": "ebay-challenge"},
        )
    assert response.status_code == 200
    assert response.json() == {
        "challengeResponse": challenge_response(
            "ebay-challenge",
            VERIFICATION_TOKEN,
            ENDPOINT_URL,
        )
    }


def test_signed_notification_deletes_account_data_and_is_idempotent(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    verifier = StaticKeyVerifier(settings, public_key)
    monkeypatch.setattr(ebay_notifications, "get_settings", lambda: settings)
    app.dependency_overrides[ebay_notifications.get_ebay_notification_verifier] = lambda: verifier
    username = "account-deletion-fixture"
    listing_external_id = "account-deletion-listing"
    event = _event("account-deletion-notification-1", username)
    signature = _signature_header(event, private_key)
    user_headers = {"X-Development-User": "00000000-0000-4000-8000-000000000777"}

    try:
        with TestClient(app) as client:
            imported = client.post(
                "/api/v1/imports/manual",
                headers=user_headers,
                json={
                    "platform": "ebay",
                    "externalId": listing_external_id,
                    "url": "https://www.ebay.de/itm/123456789012",
                    "title": "Account deletion fixture",
                    "description": "Fixture",
                    "price": "25.00",
                    "currency": "EUR",
                    "providerVersion": "browse-fixture",
                    "rawData": {"seller": {"username": username, "userId": f"{username}-id"}},
                    "seller": {
                        "externalId": username,
                        "displayName": username,
                        "rawData": {"username": username, "eiasToken": f"{username}-eias"},
                    },
                },
            )
            assert imported.status_code == 201, imported.text
            listing = imported.json()["listing"]
            stored_image = tmp_path / listing["workspaceId"] / "account-deletion-image.jpg"
            stored_image.parent.mkdir(parents=True)
            stored_image.write_bytes(b"fixture")
            asyncio.run(
                _add_image(
                    UUID(listing["id"]),
                    UUID(listing["workspaceId"]),
                    stored_image.relative_to(tmp_path).as_posix(),
                )
            )

            deleted = client.post(
                "/api/v1/webhooks/ebay/account-deletion",
                headers={"X-EBAY-SIGNATURE": signature},
                json=event,
            )
            assert deleted.status_code == 204, deleted.text
            assert not stored_image.exists()
            remaining_rows = asyncio.run(
                _account_rows(
                    listing_external_id,
                    username,
                    event["notification"]["notificationId"],
                )
            )
            assert remaining_rows == (
                False,
                False,
                True,
            )

            repeated = client.post(
                "/api/v1/webhooks/ebay/account-deletion",
                headers={"X-EBAY-SIGNATURE": signature},
                json=event,
            )
            assert repeated.status_code == 204, repeated.text
    finally:
        app.dependency_overrides.pop(ebay_notifications.get_ebay_notification_verifier, None)


def test_invalid_signature_is_rejected_before_deletion(monkeypatch: Any, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    trusted_key = ec.generate_private_key(ec.SECP256R1())
    attacker_key = ec.generate_private_key(ec.SECP256R1())
    public_key = trusted_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    verifier = StaticKeyVerifier(settings, public_key)
    monkeypatch.setattr(ebay_notifications, "get_settings", lambda: settings)
    app.dependency_overrides[ebay_notifications.get_ebay_notification_verifier] = lambda: verifier
    event = _event("account-deletion-notification-invalid", "signature-fixture")

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/webhooks/ebay/account-deletion",
                headers={"X-EBAY-SIGNATURE": _signature_header(event, attacker_key)},
                json=event,
            )
        assert response.status_code == 412
    finally:
        app.dependency_overrides.pop(ebay_notifications.get_ebay_notification_verifier, None)


async def _add_image(listing_id: UUID, workspace_id: UUID, storage_path: str) -> None:
    async with session_factory() as session:
        session.add(
            ListingImageRow(
                workspace_id=workspace_id,
                listing_id=listing_id,
                source_url="https://i.ebayimg.com/images/g/fixture/s-l1600.jpg",
                storage_path=storage_path,
                sha256_hash="a" * 64,
                perceptual_hash=None,
                width=1,
                height=1,
                mime_type="image/jpeg",
                analysis_status="COMPLETED",
            )
        )
        await session.commit()


async def _account_rows(
    listing_external_id: str,
    seller_external_id: str,
    notification_id: str,
) -> tuple[bool, bool, bool]:
    async with session_factory() as session:
        listing = await session.scalar(select(ListingRow.id).where(ListingRow.external_id == listing_external_id))
        seller = await session.scalar(select(SellerRow.id).where(SellerRow.external_id == seller_external_id))
        event = await session.get(EbayAccountDeletionEventRow, notification_id)
        return listing is not None, seller is not None, event is not None
