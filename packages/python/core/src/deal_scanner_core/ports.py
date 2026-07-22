from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol
from uuid import UUID

from .models import (
    ModelProviderStatus,
    NormalizedListing,
    RawListingSnapshot,
    SearchProfile,
    TextAnalysisRequest,
    TextAnalysisResult,
)


class ListingProvider(Protocol):
    platform: str

    def discover(self, profile: SearchProfile, cursor: str | None = None) -> AsyncIterator[RawListingSnapshot]: ...

    async def fetch_details(self, external_id: str) -> RawListingSnapshot | None: ...

    async def normalize(self, snapshot: RawListingSnapshot) -> NormalizedListing: ...

    async def health_check(self) -> dict[str, Any]: ...


class AiModelProvider(Protocol):
    async def analyze_text(self, request: TextAnalysisRequest) -> TextAnalysisResult: ...

    async def analyze_images(self, request: dict[str, Any]) -> dict[str, Any]: ...

    async def health_check(self) -> ModelProviderStatus: ...


class ErpIntegrationAdapter(Protocol):
    async def export_listing_as_purchase(self, listing_id: UUID) -> dict[str, Any]: ...


class NotificationAdapter(Protocol):
    channel: str

    async def deliver(self, notification_id: UUID, title: str, body: str) -> bool: ...
