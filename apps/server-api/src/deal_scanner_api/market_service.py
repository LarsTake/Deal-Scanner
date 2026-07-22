from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx
from deal_scanner_scoring import (
    DealScoreEngine,
    DealScoreInput,
    MarketEstimate,
    MarketValueEngine,
    PriceObservation,
)
from fastapi import HTTPException
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import (
    DealEvaluationRow,
    ListingProductRow,
    ListingRow,
    MarketValueEstimateRow,
    NotificationDeliveryRow,
    NotificationRow,
    PriceObservationRow,
    SearchProfileRow,
)
from .settings import get_settings


@dataclass(frozen=True)
class EvaluationOutcome:
    listing: ListingRow
    market: MarketEstimate
    deal_score: int | None
    risk_score: int
    notification_created: bool


async def estimate_listing_market(
    session: AsyncSession,
    workspace_id: UUID,
    listing_id: UUID,
) -> tuple[ListingRow, MarketEstimate]:
    listing = (
        await session.execute(
            select(ListingRow).where(
                ListingRow.id == listing_id,
                ListingRow.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")

    canonical_ids = list(
        (
            await session.execute(
                select(ListingProductRow.canonical_product_id)
                .where(
                    ListingProductRow.workspace_id == workspace_id,
                    ListingProductRow.listing_id == listing_id,
                    ListingProductRow.canonical_product_id.is_not(None),
                )
                .distinct()
            )
        ).scalars()
    )
    scope = PriceObservationRow.listing_id == listing_id
    if canonical_ids:
        scope = or_(scope, PriceObservationRow.canonical_product_id.in_(canonical_ids))
    rows = (
        await session.execute(
            select(PriceObservationRow).where(
                PriceObservationRow.workspace_id == workspace_id,
                PriceObservationRow.currency == listing.currency,
                scope,
            )
        )
    ).scalars()
    observations = [
        PriceObservation(
            price=row.observed_price,
            shipping_cost=row.shipping_cost,
            observed_at=row.observed_at.replace(tzinfo=UTC) if row.observed_at.tzinfo is None else row.observed_at,
            kind=row.observation_kind,
            source_quality=float(row.source_quality),
        )
        for row in rows
    ]
    return listing, MarketValueEngine().estimate(observations)


async def evaluate_listing_record(
    session: AsyncSession,
    workspace_id: UUID,
    listing_id: UUID,
    *,
    allow_notification: bool = True,
) -> EvaluationOutcome:
    listing, estimate = await estimate_listing_market(session, workspace_id, listing_id)
    evaluated_at = datetime.now(UTC)
    deal = DealScoreEngine().score(
        DealScoreInput(
            total_cost=listing.price + listing.shipping_cost,
            market=estimate,
        )
    )
    previous = (
        await session.execute(
            select(DealEvaluationRow)
            .where(
                DealEvaluationRow.listing_id == listing.id,
                DealEvaluationRow.workspace_id == workspace_id,
            )
            .order_by(desc(DealEvaluationRow.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    risk_score = previous.risk_score if previous else 0

    session.add(
        MarketValueEstimateRow(
            workspace_id=workspace_id,
            listing_id=listing.id,
            status=estimate.status,
            minimum=estimate.minimum,
            median=estimate.median,
            maximum=estimate.maximum,
            observation_count=estimate.observation_count,
            data_quality_score=estimate.data_quality_score,
            calculation_version=estimate.calculation_version,
            explanation=estimate.explanation,
            created_at=evaluated_at,
        )
    )
    evaluation = DealEvaluationRow(
        workspace_id=workspace_id,
        listing_id=listing.id,
        estimated_market_value_min=estimate.minimum,
        estimated_market_value_median=estimate.median,
        estimated_market_value_max=estimate.maximum,
        expected_resale_value=estimate.median,
        estimated_margin=(
            estimate.median - listing.price - listing.shipping_cost if estimate.median is not None else None
        ),
        deal_score=deal.score,
        risk_score=risk_score,
        data_quality_score=estimate.data_quality_score,
        relevance_score=50,
        explanation={
            "deal": deal.model_dump(mode="json"),
            "market": estimate.model_dump(mode="json"),
            "risk": previous.explanation.get("risk", {}) if previous else {},
        },
        calculation_version=f"{deal.calculation_version}+risk-v1+{estimate.calculation_version}",
        created_at=evaluated_at,
    )
    session.add(evaluation)
    await session.flush()

    minimum_deal, maximum_risk = 75, 45
    if listing.search_profile_id is not None:
        profile = await session.get(SearchProfileRow, listing.search_profile_id)
        if profile is not None and profile.workspace_id == workspace_id:
            minimum_deal, maximum_risk = profile.minimum_deal_score, profile.maximum_risk_score
    qualifies = (
        allow_notification and deal.score is not None and deal.score >= minimum_deal and risk_score <= maximum_risk
    )
    notification_created = False
    signature = {
        "listingVersion": listing.version,
        "dealScore": deal.score,
        "riskScore": risk_score,
        "marketMedian": str(estimate.median) if estimate.median is not None else None,
        "observationCount": estimate.observation_count,
    }
    previous_notification = (
        await session.execute(
            select(NotificationRow)
            .where(
                NotificationRow.workspace_id == workspace_id,
                NotificationRow.listing_id == listing.id,
            )
            .order_by(desc(NotificationRow.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    duplicate = previous_notification is not None and all(
        previous_notification.reason.get(key) == value for key, value in signature.items()
    )
    if qualifies and not duplicate:
        assert deal.score is not None
        reason = {
            **signature,
            "minimumDealScore": minimum_deal,
            "maximumRiskScore": maximum_risk,
            "title": listing.title,
        }
        notification = NotificationRow(
            workspace_id=workspace_id,
            listing_id=listing.id,
            evaluation_id=evaluation.id,
            reason=reason,
            created_at=evaluated_at,
        )
        session.add(notification)
        await session.flush()
        session.add(
            NotificationDeliveryRow(
                workspace_id=workspace_id,
                notification_id=notification.id,
                channel="desktop",
                status="PENDING",
            )
        )
        await _send_ntfy(session, workspace_id, notification.id, listing.title, deal.score, risk_score)
        notification_created = True

    listing.status = "READY" if estimate.status == "ready" else "PRICE_EVALUATED"
    return EvaluationOutcome(
        listing=listing,
        market=estimate,
        deal_score=deal.score,
        risk_score=risk_score,
        notification_created=notification_created,
    )


async def _send_ntfy(
    session: AsyncSession,
    workspace_id: UUID,
    notification_id: UUID,
    title: str,
    deal_score: int,
    risk_score: int,
) -> None:
    ntfy_url = get_settings().ntfy_url
    if not ntfy_url:
        return
    delivery = NotificationDeliveryRow(
        workspace_id=workspace_id,
        notification_id=notification_id,
        channel="ntfy",
        status="PENDING",
        attempts=1,
    )
    session.add(delivery)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                ntfy_url,
                content=f"{title}: Deal {deal_score}, Risiko {risk_score}",
                headers={"Title": "Deal Scanner", "Tags": "moneybag"},
            )
            response.raise_for_status()
        delivery.status = "DELIVERED"
        delivery.delivered_at = datetime.now(UTC)
    except httpx.HTTPError as exc:
        delivery.status = "FAILED"
        delivery.last_error = str(exc)[:1000]
