from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import (
    DealEvaluationRow,
    ListingImageRow,
    ListingProductRow,
    ListingRow,
    SellerRow,
)


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
        seller = (
            (
                await self.session.execute(
                    select(SellerRow).where(
                        SellerRow.id == listing.seller_id,
                        SellerRow.workspace_id == self.workspace_id,
                    )
                )
            ).scalar_one_or_none()
            if listing.seller_id is not None
            else None
        )
        images = list(
            (
                await self.session.execute(
                    select(ListingImageRow)
                    .where(
                        ListingImageRow.workspace_id == self.workspace_id,
                        ListingImageRow.listing_id == listing.id,
                    )
                    .order_by(ListingImageRow.created_at, ListingImageRow.id)
                )
            ).scalars()
        )
        components = list(
            (
                await self.session.execute(
                    select(ListingProductRow)
                    .where(
                        ListingProductRow.workspace_id == self.workspace_id,
                        ListingProductRow.listing_id == listing.id,
                    )
                    .order_by(ListingProductRow.created_at, ListingProductRow.id)
                )
            ).scalars()
        )
        evaluation = (
            await self.session.execute(
                select(DealEvaluationRow)
                .where(
                    DealEvaluationRow.workspace_id == self.workspace_id,
                    DealEvaluationRow.listing_id == listing.id,
                )
                .order_by(desc(DealEvaluationRow.created_at), desc(DealEvaluationRow.id))
                .limit(1)
            )
        ).scalar_one_or_none()
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
            "seller": (
                {
                    "externalId": seller.external_id,
                    "displayName": seller.display_name,
                    "location": seller.location,
                    "ratingScore": str(seller.rating_score) if seller.rating_score is not None else None,
                    "reviewCount": seller.review_count,
                }
                if seller is not None
                else None
            ),
            "components": [
                {
                    "listingProductId": str(component.id),
                    "canonicalProductId": str(component.canonical_product_id)
                    if component.canonical_product_id is not None
                    else None,
                    "productType": component.product_type,
                    "manufacturer": component.manufacturer,
                    "model": component.model,
                    "variant": component.variant,
                    "quantity": component.quantity,
                    "confidence": str(component.confidence),
                }
                for component in components
            ],
            "images": [
                {
                    "listingImageId": str(image.id),
                    "sourceUrl": image.source_url,
                    "sha256Hash": image.sha256_hash,
                    "mimeType": image.mime_type,
                    "width": image.width,
                    "height": image.height,
                }
                for image in images
            ],
            "marketValue": (
                {
                    "minimum": str(evaluation.estimated_market_value_min)
                    if evaluation.estimated_market_value_min is not None
                    else None,
                    "median": str(evaluation.estimated_market_value_median)
                    if evaluation.estimated_market_value_median is not None
                    else None,
                    "maximum": str(evaluation.estimated_market_value_max)
                    if evaluation.estimated_market_value_max is not None
                    else None,
                    "expectedResaleValue": str(evaluation.expected_resale_value)
                    if evaluation.expected_resale_value is not None
                    else None,
                    "estimatedMargin": str(evaluation.estimated_margin)
                    if evaluation.estimated_margin is not None
                    else None,
                    "dealScore": evaluation.deal_score,
                    "riskScore": evaluation.risk_score,
                    "dataQualityScore": evaluation.data_quality_score,
                    "calculationVersion": evaluation.calculation_version,
                }
                if evaluation is not None
                else None
            ),
        }
