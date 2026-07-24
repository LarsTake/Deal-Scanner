from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import textwrap
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Literal
from urllib.parse import quote

import httpx
import structlog
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import (
    AuditEventRow,
    EbayAccountDeletionEventRow,
    ListingImageRow,
    ListingRow,
    ListingSnapshotRow,
    PriceObservationRow,
    SellerRow,
)
from .image_service import delete_private_images, system_ssl_context
from .settings import Settings

logger = structlog.get_logger("deal_scanner_api.ebay_account_deletion")
EBAY_DELETION_TOPIC = "MARKETPLACE_ACCOUNT_DELETION"
EBAY_NOTIFICATION_SCOPE = "https://api.ebay.com/oauth/api_scope"
SIGNATURE_HEADER_MAX_BYTES = 4096


class EbayNotificationConfigurationError(RuntimeError):
    pass


class EbayNotificationUpstreamError(RuntimeError):
    pass


class EbayDeletionData(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    username: str | None = Field(default=None, max_length=255)
    user_id: str | None = Field(default=None, alias="userId", max_length=255)
    eias_token: str | None = Field(default=None, alias="eiasToken", max_length=2048)

    @model_validator(mode="after")
    def require_identifier(self) -> EbayDeletionData:
        if not any((self.username, self.user_id, self.eias_token)):
            raise ValueError("the notification does not contain an account identifier")
        return self

    @property
    def identifiers(self) -> tuple[str, ...]:
        return tuple(value for value in (self.username, self.user_id, self.eias_token) if value)


class EbayDeletionMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic: Literal["MARKETPLACE_ACCOUNT_DELETION"]


class EbayDeletionNotificationBody(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    notification_id: str = Field(alias="notificationId", min_length=1, max_length=128)
    data: EbayDeletionData


class EbayDeletionEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    metadata: EbayDeletionMetadata
    notification: EbayDeletionNotificationBody


@dataclass(frozen=True)
class DeletionResult:
    already_processed: bool
    deleted_seller_count: int
    deleted_listing_count: int


class EbayNotificationVerifier:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0
        self._public_keys: dict[str, tuple[float, bytes]] = {}

    async def verify(self, payload: dict[str, Any], signature_header: str | None) -> bool:
        parsed_header = self._parse_signature_header(signature_header)
        if parsed_header is None:
            return False
        key_id, signature = parsed_header
        try:
            public_key_pem = await self._get_public_key(key_id)
            public_key = serialization.load_pem_public_key(public_key_pem)
        except (EbayNotificationConfigurationError, EbayNotificationUpstreamError):
            raise
        except (TypeError, ValueError):
            return False
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            return False

        signed_message = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        try:
            # eBay's official event SDK requires ECDSA with SHA-1 for this header format.
            public_key.verify(signature, signed_message, ec.ECDSA(hashes.SHA1()))  # noqa: S303
        except InvalidSignature:
            return False
        return True

    @staticmethod
    def _parse_signature_header(signature_header: str | None) -> tuple[str, bytes] | None:
        if not signature_header or len(signature_header.encode()) > SIGNATURE_HEADER_MAX_BYTES:
            return None
        try:
            decoded = base64.b64decode(signature_header, validate=True)
            envelope = json.loads(decoded.decode("utf-8"))
            key_id = envelope["kid"]
            encoded_signature = envelope["signature"]
            if (
                not isinstance(key_id, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", key_id)
                or not isinstance(encoded_signature, str)
            ):
                return None
            signature = base64.b64decode(encoded_signature, validate=True)
        except (KeyError, TypeError, UnicodeDecodeError, ValueError, binascii.Error, json.JSONDecodeError):
            return None
        return key_id, signature

    async def _get_public_key(self, key_id: str) -> bytes:
        cached = self._public_keys.get(key_id)
        now = monotonic()
        if cached and cached[0] > now:
            return cached[1]
        token = await self._get_access_token()
        api_base = (
            "https://api.ebay.com"
            if self._settings.ebay_environment == "production"
            else "https://api.sandbox.ebay.com"
        )
        target = f"{api_base}/commerce/notification/v1/public_key/{quote(key_id, safe='')}"
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(20, connect=5),
                follow_redirects=False,
                trust_env=False,
                verify=system_ssl_context(),
            ) as client:
                response = await client.get(
                    target,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EbayNotificationUpstreamError("eBay's notification public key could not be retrieved") from exc
        encoded_key = body.get("key") if isinstance(body, dict) else None
        if not isinstance(encoded_key, str) or not encoded_key.strip():
            raise EbayNotificationUpstreamError("eBay returned an invalid notification public key")
        public_key = _normalize_public_key(encoded_key)
        self._public_keys[key_id] = (
            now + self._settings.ebay_notification_public_key_cache_seconds,
            public_key,
        )
        return public_key

    async def _get_access_token(self) -> str:
        now = monotonic()
        if self._access_token and self._access_token_expires_at > now:
            return self._access_token
        if not self._settings.ebay_client_id or not self._settings.ebay_client_secret:
            raise EbayNotificationConfigurationError("eBay application credentials are not configured")
        token_url = (
            "https://api.ebay.com/identity/v1/oauth2/token"
            if self._settings.ebay_environment == "production"
            else "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
        )
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(20, connect=5),
                follow_redirects=False,
                trust_env=False,
                verify=system_ssl_context(),
            ) as client:
                response = await client.post(
                    token_url,
                    auth=httpx.BasicAuth(
                        self._settings.ebay_client_id,
                        self._settings.ebay_client_secret,
                    ),
                    data={
                        "grant_type": "client_credentials",
                        "scope": EBAY_NOTIFICATION_SCOPE,
                    },
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EbayNotificationUpstreamError("an eBay application token could not be retrieved") from exc
        access_token = body.get("access_token") if isinstance(body, dict) else None
        expires_in = body.get("expires_in", 7200) if isinstance(body, dict) else 7200
        if not isinstance(access_token, str) or not access_token:
            raise EbayNotificationUpstreamError("eBay returned an invalid application token")
        self._access_token = access_token
        self._access_token_expires_at = now + max(int(expires_in) - 120, 60)
        return access_token


def challenge_response(challenge_code: str, verification_token: str, endpoint_url: str) -> str:
    challenge = f"{challenge_code}{verification_token}{endpoint_url}".encode()
    return hashlib.sha256(challenge).hexdigest()


async def process_account_deletion(
    session: AsyncSession,
    event: EbayDeletionEvent,
    settings: Settings,
) -> DeletionResult:
    notification_id = event.notification.notification_id
    existing = await session.get(EbayAccountDeletionEventRow, notification_id)
    if existing is not None:
        return DeletionResult(
            already_processed=True,
            deleted_seller_count=existing.deleted_seller_count,
            deleted_listing_count=existing.deleted_listing_count,
        )

    identifiers = event.notification.data.identifiers
    sellers = list((await session.scalars(select(SellerRow).where(SellerRow.platform == "ebay"))).all())
    listings = list((await session.scalars(select(ListingRow).where(ListingRow.platform == "ebay"))).all())
    snapshots = list(
        (
            await session.scalars(
                select(ListingSnapshotRow)
                .join(ListingRow, ListingRow.id == ListingSnapshotRow.listing_id)
                .where(ListingRow.platform == "ebay")
            )
        ).all()
    )

    seller_ids = {
        seller.id
        for seller in sellers
        if _contains_identifier(
            {
                "externalId": seller.external_id,
                "displayName": seller.display_name,
                "rawData": seller.raw_data,
            },
            identifiers,
        )
    }
    listing_ids = {
        listing.id
        for listing in listings
        if listing.seller_id in seller_ids
        or _contains_identifier(
            {
                "externalId": listing.external_id,
                "url": listing.url,
                "title": listing.title,
                "description": listing.description,
                "location": listing.location,
            },
            identifiers,
        )
    }
    listing_ids.update(
        snapshot.listing_id for snapshot in snapshots if _contains_identifier(snapshot.raw_data, identifiers)
    )
    seller_ids.update(
        listing.seller_id for listing in listings if listing.id in listing_ids and listing.seller_id is not None
    )
    listing_ids.update(listing.id for listing in listings if listing.seller_id in seller_ids)

    observation_ids = set(
        (
            await session.scalars(select(PriceObservationRow.id).where(PriceObservationRow.listing_id.in_(listing_ids)))
        ).all()
        if listing_ids
        else ()
    )
    ebay_observations = list(
        (await session.scalars(select(PriceObservationRow).where(PriceObservationRow.platform == "ebay"))).all()
    )
    observation_ids.update(
        observation.id
        for observation in ebay_observations
        if _contains_identifier(observation.metadata_json, identifiers)
    )

    storage_paths = (
        list(
            (
                await session.scalars(
                    select(ListingImageRow.storage_path).where(
                        ListingImageRow.listing_id.in_(listing_ids),
                        ListingImageRow.storage_path.is_not(None),
                    )
                )
            ).all()
        )
        if listing_ids
        else []
    )
    await delete_private_images([path for path in storage_paths if path], settings)

    aggregate_ids = {*seller_ids, *listing_ids}
    if aggregate_ids:
        await session.execute(delete(AuditEventRow).where(AuditEventRow.aggregate_id.in_(aggregate_ids)))
    if observation_ids:
        await session.execute(delete(PriceObservationRow).where(PriceObservationRow.id.in_(observation_ids)))
    if listing_ids:
        await session.execute(delete(ListingRow).where(ListingRow.id.in_(listing_ids)))
    if seller_ids:
        await session.execute(delete(SellerRow).where(SellerRow.id.in_(seller_ids)))

    processed_at = datetime.now(UTC)
    session.add(
        EbayAccountDeletionEventRow(
            notification_id=notification_id,
            received_at=processed_at,
            processed_at=processed_at,
            deleted_seller_count=len(seller_ids),
            deleted_listing_count=len(listing_ids),
        )
    )
    await session.commit()
    logger.info(
        "ebay_account_deletion_processed",
        notification_id=notification_id,
        deleted_seller_count=len(seller_ids),
        deleted_listing_count=len(listing_ids),
    )
    return DeletionResult(
        already_processed=False,
        deleted_seller_count=len(seller_ids),
        deleted_listing_count=len(listing_ids),
    )


def _contains_identifier(value: Any, identifiers: tuple[str, ...]) -> bool:
    exact = set(identifiers)
    folded = {identifier.casefold() for identifier in identifiers}
    if isinstance(value, str):
        return value in exact or value.casefold() in folded
    if isinstance(value, dict):
        return any(_contains_identifier(item, identifiers) for item in value.values())
    if isinstance(value, list | tuple):
        return any(_contains_identifier(item, identifiers) for item in value)
    return False


def _normalize_public_key(value: str) -> bytes:
    stripped = value.strip()
    begin = "-----BEGIN PUBLIC KEY-----"
    end = "-----END PUBLIC KEY-----"
    if stripped.startswith(begin) and stripped.endswith(end):
        body = stripped.removeprefix(begin).removesuffix(end)
        body = "".join(body.split())
        wrapped = "\n".join(textwrap.wrap(body, 64))
        return f"{begin}\n{wrapped}\n{end}\n".encode()
    return stripped.encode()
