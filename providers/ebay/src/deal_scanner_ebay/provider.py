from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from deal_scanner_core.errors import ProviderError, ProviderRateLimited
from deal_scanner_core.models import Money, NormalizedListing, RawListingSnapshot, SearchProfile
from deal_scanner_provider_sdk import content_hash


@dataclass(frozen=True)
class EbaySettings:
    client_id: str
    client_secret: str
    environment: str = "sandbox"
    marketplace_id: str = "EBAY_DE"
    request_timeout_seconds: float = 20.0

    @property
    def api_base(self) -> str:
        return "https://api.ebay.com" if self.environment == "production" else "https://api.sandbox.ebay.com"


class EbayProvider:
    platform = "ebay"
    provider_version = "browse-v1.20"

    def __init__(self, settings: EbaySettings, client: httpx.AsyncClient | None = None) -> None:
        if not settings.client_id or not settings.client_secret:
            raise ValueError("eBay client credentials are required")
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=settings.request_timeout_seconds)
        self._owns_client = client is None
        self._access_token: str | None = None
        self._token_expires_at = datetime.min.replace(tzinfo=UTC)
        self._token_lock = asyncio.Lock()

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _token(self) -> str:
        now = datetime.now(UTC)
        if self._access_token and now < self._token_expires_at - timedelta(seconds=60):
            return self._access_token
        async with self._token_lock:
            now = datetime.now(UTC)
            if self._access_token and now < self._token_expires_at - timedelta(seconds=60):
                return self._access_token
            credentials = base64.b64encode(f"{self.settings.client_id}:{self.settings.client_secret}".encode()).decode()
            response = await self.client.post(
                f"{self.settings.api_base}/identity/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "client_credentials",
                    "scope": "https://api.ebay.com/oauth/api_scope",
                },
            )
            if response.is_error:
                raise ProviderError(f"eBay OAuth failed with status {response.status_code}")
            payload = response.json()
            self._access_token = payload["access_token"]
            self._token_expires_at = now + timedelta(seconds=int(payload["expires_in"]))
            return self._access_token

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        for attempt in range(4):
            token = await self._token()
            response = await self.client.get(
                f"{self.settings.api_base}{path}",
                params=params,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": self.settings.marketplace_id,
                    "Accept-Language": "de-DE",
                },
            )
            if response.status_code == 401 and attempt == 0:
                self._access_token = None
                continue
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", "60"))
                raise ProviderRateLimited(retry_after)
            if 500 <= response.status_code < 600 and attempt < 3:
                await asyncio.sleep(2**attempt)
                continue
            if response.is_error:
                raise ProviderError(f"eBay Browse request failed with status {response.status_code}")
            payload: dict[str, Any] = response.json()
            return payload
        raise ProviderError("eBay Browse request exhausted retries")

    async def discover(self, profile: SearchProfile, cursor: str | None = None) -> AsyncIterator[RawListingSnapshot]:
        offset = int(cursor or "0")
        filters: list[str] = []
        if profile.minimum_price is not None or profile.maximum_price is not None:
            lower = str(profile.minimum_price or "")
            upper = str(profile.maximum_price or "")
            filters.extend([f"price:[{lower}..{upper}]", "priceCurrency:EUR"])
        payload = await self._get(
            "/buy/browse/v1/item_summary/search",
            {
                "q": profile.query,
                "limit": "50",
                "offset": str(offset),
                "fieldgroups": "EXTENDED",
                **({"filter": ",".join(filters)} if filters else {}),
            },
        )
        fetched_at = datetime.now(UTC)
        for item in payload.get("itemSummaries", []):
            external_id = item.get("legacyItemId") or item["itemId"]
            yield RawListingSnapshot(
                platform=self.platform,
                external_id=str(external_id),
                source_url=item["itemWebUrl"],
                fetched_at=fetched_at,
                payload=item,
                provider_version=self.provider_version,
            )

    async def fetch_details(self, external_id: str) -> RawListingSnapshot | None:
        try:
            payload = await self._get(
                "/buy/browse/v1/item/get_item_by_legacy_id",
                {"legacy_item_id": external_id},
            )
        except ProviderError as exc:
            if "404" in str(exc):
                return None
            raise
        return RawListingSnapshot(
            platform=self.platform,
            external_id=external_id,
            source_url=payload["itemWebUrl"],
            fetched_at=datetime.now(UTC),
            payload=payload,
            provider_version=self.provider_version,
        )

    async def normalize(self, snapshot: RawListingSnapshot) -> NormalizedListing:
        item = snapshot.payload
        price = item.get("price") or item.get("currentBidPrice")
        if not price:
            raise ProviderError("eBay item contains no price")
        shipping_options = item.get("shippingOptions") or []
        shipping = next(
            (option.get("shippingCost") for option in shipping_options if option.get("shippingCost")),
            None,
        )
        return NormalizedListing(
            platform=self.platform,
            external_id=snapshot.external_id,
            url=snapshot.source_url,
            title=item["title"],
            description=item.get("shortDescription", ""),
            price=Money(amount=Decimal(price["value"]), currency=price["currency"]),
            shipping_cost=(
                Money(amount=Decimal(shipping["value"]), currency=shipping["currency"]) if shipping else None
            ),
            location=(item.get("itemLocation") or {}).get("city"),
            seller_external_id=(item.get("seller") or {}).get("username"),
            published_at=None,
            raw_snapshot_hash=content_hash(snapshot.payload),
        )

    async def health_check(self) -> dict[str, Any]:
        try:
            await self._token()
            return {"available": True, "environment": self.settings.environment}
        except ProviderError as exc:
            return {"available": False, "detail": str(exc)}
