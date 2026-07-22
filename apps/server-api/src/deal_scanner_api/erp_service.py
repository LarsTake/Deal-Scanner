from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import ListingRow


class MockErpIntegrationAdapter:
    """Stable ERP boundary; replace this adapter without changing the REST contract."""

    def __init__(self, session: AsyncSession, workspace_id: UUID) -> None:
        self.session = session
        self.workspace_id = workspace_id

    async def export_listing_as_purchase(self, listing_id: UUID) -> dict[str, Any]:
        listing = (
            await self.session.execute(
                select(ListingRow).where(
                    ListingRow.id == listing_id,
                    ListingRow.workspace_id == self.workspace_id,
                )
            )
        ).scalar_one_or_none()
        if listing is None:
            raise LookupError("listing not found")
        return {
            "formatVersion": "erp-purchase-v1",
            "externalReference": f"deal-scanner:{listing.id}",
            "source": {
                "platform": listing.platform,
                "externalId": listing.external_id,
                "url": listing.url,
            },
            "purchase": {
                "title": listing.title,
                "purchasePrice": str(listing.price),
                "shippingCost": str(listing.shipping_cost),
                "currency": listing.currency,
            },
            "relationships": {
                "listingId": str(listing.id),
                "sellerId": str(listing.seller_id) if listing.seller_id is not None else None,
            },
        }
