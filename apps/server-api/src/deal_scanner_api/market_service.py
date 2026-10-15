from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from deal_scanner_core.ports import NotificationAdapter
from deal_scanner_scoring import (
    DealScoreEngine,
    DealScoreInput,
    MarketEstimate,
    MarketValueEngine,
    PriceObservation,
)
from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .comparison_service import COMPARISON_VERSION, select_comparisons
from .db_models import (
    DealEvaluationRow,
    ListingProductRow,
    ListingRow,
    ListingSnapshotRow,
    MarketValueEstimateRow,
    NotificationRow,
    ProductAttributeRow,
    SearchProfileRow,
)
from .notification_service import DesktopNotificationAdapter, NtfyNotificationAdapter


@dataclass(frozen=True)
class EvaluationOutcome:
    listing: ListingRow
    market: MarketEstimate
    deal_score: int | None
    risk_score: int
    notification_created: bool


async def _deal_component_scores(
    session: AsyncSession,
    workspace_id: UUID,
    listing: ListingRow,
) -> tuple[int, int, int, int]:
    text = f"{listing.title}\n{listing.description}".lower()
    positive_condition = bool(re.search(r"\b(?:neuwertig|sehr gut|gepflegt|funktioniert|funktionstest)\b", text))
    negative_condition = bool(re.search(r"\b(?:defekt|beschädigt|reparatur|ersatzteil|ungetestet)\b", text))
    condition = 75 if positive_condition and not negative_condition else 25 if negative_condition else 50

    product_rows = list(
        (
            await session.execute(
                select(ListingProductRow).where(
                    ListingProductRow.workspace_id == workspace_id,
                    ListingProductRow.listing_id == listing.id,
                )
            )
        ).scalars()
    )
    attribute_count = 0
    if product_rows:
        attribute_count = len(
            list(
                (
                    await session.execute(
                        select(ProductAttributeRow.id).where(
                            ProductAttributeRow.workspace_id == workspace_id,
                            ProductAttributeRow.listing_product_id.in_([row.id for row in product_rows]),
                        )
                    )
                ).scalars()
            )
        )
    completeness = min(100, 30 + len({row.model for row in product_rows}) * 15 + attribute_count * 5)
    canonical_count = len({row.canonical_product_id for row in product_rows if row.canonical_product_id is not None})
    resale = min(90, 40 + canonical_count * 20 + (10 if listing.platform == "ebay" else 0))

    relevance = 50
    if listing.search_profile_id is not None:
        profile = await session.get(SearchProfileRow, listing.search_profile_id)
        if profile is not None and profile.workspace_id == workspace_id:
            searchable = text.casefold()
            query_tokens = [token for token in re.split(r"\W+", profile.query.casefold()) if len(token) >= 3]
            matched = sum(1 for token in query_tokens if token in searchable)
            query_ratio = matched / len(query_tokens) if query_tokens else 0
            required = [*profile.required_terms, *profile.required_products]
            required_ratio = (
                sum(1 for term in required if term.casefold() in searchable) / len(required) if required else 1
            )
            relevance = round(min(100, 40 + query_ratio * 35 + required_ratio * 25))
    return condition, completeness, resale, relevance


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

    selection = await select_comparisons(session, workspace_id, listing)
    observations = [
        PriceObservation(
            price=row.observed_price,
            shipping_cost=row.shipping_cost,
            observed_at=row.observed_at.replace(tzinfo=UTC) if row.observed_at.tzinfo is None else row.observed_at,
            kind=row.observation_kind,
            source_quality=float(row.source_quality),
        )
        for row in selection.rows
    ]
    estimate = MarketValueEngine().estimate(observations)
    estimate.calculation_version += f"+{COMPARISON_VERSION}"
    estimate.explanation.extend(selection.explanations())
    return listing, estimate


async def evaluate_listing_record(
    session: AsyncSession,
    workspace_id: UUID,
    listing_id: UUID,
    *,
    allow_notification: bool = True,
    risk_score_override: int | None = None,
) -> EvaluationOutcome:
    listing, estimate = await estimate_listing_market(session, workspace_id, listing_id)
    evaluated_at = datetime.now(UTC)
    condition_score, completeness_score, resale_score, relevance_score = await _deal_component_scores(
        session, workspace_id, listing
    )
    deal = DealScoreEngine().score(
        DealScoreInput(
            total_cost=listing.price + listing.shipping_cost,
            market=estimate,
            condition_score=condition_score,
            completeness_score=completeness_score,
            resale_score=resale_score,
            relevance_score=relevance_score,
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
    risk_score = risk_score_override if risk_score_override is not None else previous.risk_score if previous else 0

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
        relevance_score=relevance_score,
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
    minimum_advantage = Decimal("0")
    maximum_age_hours: int | None = None
    desktop_enabled = True
    minimum_quality = 40
    ntfy_enabled = False
    if listing.search_profile_id is not None:
        profile = await session.get(SearchProfileRow, listing.search_profile_id)
        if profile is not None and profile.workspace_id == workspace_id:
            minimum_deal, maximum_risk = profile.minimum_deal_score, profile.maximum_risk_score
            settings = profile.notification_settings or {}
            try:
                minimum_advantage = max(
                    Decimal("0"),
                    Decimal(str(settings.get("minimum_market_advantage_percent", 0))),
                )
            except InvalidOperation:
                minimum_advantage = Decimal("0")
            raw_maximum_age = settings.get("maximum_listing_age_hours")
            if isinstance(raw_maximum_age, int) and not isinstance(raw_maximum_age, bool) and raw_maximum_age > 0:
                maximum_age_hours = raw_maximum_age
            desktop_enabled = settings.get("desktop_enabled", True) is True
            minimum_quality = settings.get("minimum_data_quality", 40)
            ntfy_enabled = settings.get("ntfy_enabled", False) is True
    total_cost = listing.price + listing.shipping_cost
    advantage_percent = (
        ((estimate.median - total_cost) / estimate.median * Decimal("100"))
        if estimate.median is not None and estimate.median > 0
        else None
    )
    published_at = listing.published_at
    if published_at is not None and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    age_hours = (
        Decimal(str((evaluated_at - published_at).total_seconds())) / Decimal("3600")
        if published_at is not None
        else None
    )
    advantage_qualifies = advantage_percent is not None and advantage_percent >= minimum_advantage
    age_qualifies = maximum_age_hours is None or (age_hours is not None and age_hours <= maximum_age_hours)
    snapshot = (
        await session.get(ListingSnapshotRow, listing.current_snapshot_id) if listing.current_snapshot_id else None
    )
    silent_baseline = bool(snapshot and snapshot.raw_data.get("_tracking", {}).get("silentBaseline"))
    qualifies = (
        allow_notification
        and not silent_baseline
        and not listing.is_hidden
        and deal.score is not None
        and deal.score >= minimum_deal
        and risk_score <= maximum_risk
        and advantage_qualifies
        and age_qualifies
        and estimate.data_quality_score >= minimum_quality
        and (desktop_enabled or ntfy_enabled)
    )
    notification_created = False
    signature = {
        "listingVersion": listing.version,
        "dealScore": deal.score,
        "riskScore": risk_score,
        "marketMedian": str(estimate.median) if estimate.median is not None else None,
        "observationCount": estimate.observation_count,
        "marketAdvantagePercent": str(advantage_percent.quantize(Decimal("0.1")))
        if advantage_percent is not None
        else None,
        "listingAgeHours": str(age_hours.quantize(Decimal("0.1"))) if age_hours is not None else None,
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
            "minimumMarketAdvantagePercent": str(minimum_advantage),
            "minimumDataQuality": minimum_quality,
            "maximumListingAgeHours": maximum_age_hours,
            "title": listing.title,
            "url": listing.url,
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
        body = f"{listing.title}: Deal {deal.score}, Risiko {risk_score}"
        adapters: list[NotificationAdapter] = []
        if desktop_enabled:
            adapters.append(DesktopNotificationAdapter(session, workspace_id))
        if ntfy_enabled:
            adapters.append(NtfyNotificationAdapter(session, workspace_id))
        for adapter in adapters:
            await adapter.deliver(notification.id, "Deal Scanner", body)
        notification_created = True

    listing.status = "READY" if estimate.status == "ready" else "PRICE_EVALUATED"
    return EvaluationOutcome(
        listing=listing,
        market=estimate,
        deal_score=deal.score,
        risk_score=risk_score,
        notification_created=notification_created,
    )
