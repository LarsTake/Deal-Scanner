from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from deal_scanner_core.models import NormalizedListing, RawListingSnapshot, SearchProfile

EBAY_ID_PATTERN = re.compile(r"(?:/itm/(?:[^/]+/)?|[?&]item=)(\d{9,15})(?:[/?&#]|$)")


def extract_ebay_legacy_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "ebay.de",
        "www.ebay.de",
        "ebay.com",
        "www.ebay.com",
    }:
        return None
    match = EBAY_ID_PATTERN.search(url)
    return match.group(1) if match else None


class ManualImportProvider:
    platform = "manual"

    async def discover(self, profile: SearchProfile, cursor: str | None = None) -> AsyncIterator[RawListingSnapshot]:
        del profile, cursor
        if False:
            yield

    async def fetch_details(self, external_id: str) -> RawListingSnapshot | None:
        del external_id
        return None

    async def normalize(self, snapshot: RawListingSnapshot) -> NormalizedListing:
        return NormalizedListing.model_validate(snapshot.payload)

    async def health_check(self) -> dict[str, Any]:
        return {"available": True, "mode": "explicit-user-input"}

    def snapshot(self, external_id: str, url: str, payload: dict[str, Any]) -> RawListingSnapshot:
        return RawListingSnapshot(
            platform=self.platform,
            external_id=external_id,
            source_url=url,
            fetched_at=datetime.now(UTC),
            payload=payload,
            provider_version="manual-v1",
        )
