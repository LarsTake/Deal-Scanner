from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import urlparse
from uuid import UUID

from deal_scanner_extraction import RuleExtractor
from deal_scanner_scoring import RiskScoreEngine
from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import (
    AnalysisJobRow,
    AnalysisResultRow,
    AuditEventRow,
    DealEvaluationRow,
    ListingProductRow,
    ListingRow,
    ListingSnapshotRow,
    PriceObservationRow,
    ProductAttributeRow,
    RiskSignalRow,
    SearchProfileRow,
    SellerRow,
    UserFeedbackRow,
)
from .product_service import persist_listing_products
from .schemas import (
    AnalysisResultResponse,
    DealEvaluationHistoryResponse,
    FeedbackResponse,
    ImportResponse,
    ListingDetail,
    ListingProductResponse,
    ListingSnapshotResponse,
    ListingSummary,
    ManualImportRequest,
    ProductAttributeResponse,
    RiskSignalResponse,
    SellerInput,
    SellerResponse,
)

ALLOWED_IMPORT_HOSTS = {
    "ebay.de",
    "www.ebay.de",
    "ebay.com",
    "www.ebay.com",
    "kleinanzeigen.de",
    "www.kleinanzeigen.de",
}


def validate_import_url(url: str, platform: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise HTTPException(status_code=422, detail="only HTTPS provider URLs are accepted")
    host = parsed.hostname.lower().rstrip(".")
    if platform != "manual" and host not in ALLOWED_IMPORT_HOSTS:
        raise HTTPException(status_code=422, detail="URL host does not match an allowed provider")
    if platform == "manual" and host not in ALLOWED_IMPORT_HOSTS:
        raise HTTPException(
            status_code=422,
            detail="manual imports require explicit fields and a supported public listing URL",
        )


def request_content_hash(payload: ManualImportRequest) -> str:
    encoded = json.dumps(payload.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


async def latest_evaluation(session: AsyncSession, listing_id: UUID) -> DealEvaluationRow | None:
    result = await session.execute(
        select(DealEvaluationRow)
        .where(DealEvaluationRow.listing_id == listing_id)
        .order_by(desc(DealEvaluationRow.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def listing_summary(session: AsyncSession, listing: ListingRow) -> ListingSummary:
    evaluation = await latest_evaluation(session, listing.id)
    return ListingSummary(
        id=listing.id,
        workspace_id=listing.workspace_id,
        platform=listing.platform,
        external_id=listing.external_id,
        url=listing.url,
        title=listing.title,
        price=listing.price,
        shipping_cost=listing.shipping_cost,
        currency=listing.currency,
        status=listing.status,
        analysis_status=listing.analysis_status,
        is_favorite=listing.is_favorite,
        is_hidden=listing.is_hidden,
        version=listing.version,
        last_seen_at=listing.last_seen_at,
        deal_score=evaluation.deal_score if evaluation else None,
        risk_score=evaluation.risk_score if evaluation else None,
    )


async def listing_detail(session: AsyncSession, listing: ListingRow) -> ListingDetail:
    summary = await listing_summary(session, listing)
    signals_result = await session.execute(
        select(RiskSignalRow).where(RiskSignalRow.listing_id == listing.id).order_by(RiskSignalRow.created_at)
    )
    signals = [
        RiskSignalResponse(
            type=signal.type,
            severity=signal.severity,
            confidence=float(signal.confidence),
            positive=signal.positive,
            source=signal.source,
            evidence=signal.evidence,
        )
        for signal in signals_result.scalars()
    ]
    product_rows = list(
        (
            await session.execute(
                select(ListingProductRow)
                .where(ListingProductRow.listing_id == listing.id)
                .order_by(desc(ListingProductRow.created_at), ListingProductRow.id)
            )
        ).scalars()
    )
    attributes_by_product: dict[UUID, list[ProductAttributeResponse]] = {row.id: [] for row in product_rows}
    if product_rows:
        attribute_rows = (
            await session.execute(
                select(ProductAttributeRow)
                .where(ProductAttributeRow.listing_product_id.in_([row.id for row in product_rows]))
                .order_by(ProductAttributeRow.created_at, ProductAttributeRow.id)
            )
        ).scalars()
        for attribute in attribute_rows:
            value: str | Decimal | bool
            if attribute.value_boolean is not None:
                value = attribute.value_boolean
            elif attribute.value_number is not None:
                value = attribute.value_number
            else:
                value = attribute.value_text or ""
            attributes_by_product[attribute.listing_product_id].append(
                ProductAttributeResponse(
                    id=attribute.id,
                    attribute_key=attribute.attribute_key,
                    value=value,
                    unit=attribute.unit,
                    confidence=float(attribute.confidence),
                    source=attribute.source,
                )
            )
    products = [
        ListingProductResponse(
            id=row.id,
            canonical_product_id=row.canonical_product_id,
            product_type=row.product_type,
            manufacturer=row.manufacturer,
            model=row.model,
            variant=row.variant,
            quantity=row.quantity,
            confidence=float(row.confidence),
            detection_source=row.detection_source,
            evidence=row.raw_match,
            created_at=row.created_at,
            attributes=attributes_by_product[row.id],
        )
        for row in product_rows
    ]
    snapshot_rows = (
        await session.execute(
            select(ListingSnapshotRow)
            .where(ListingSnapshotRow.listing_id == listing.id)
            .order_by(desc(ListingSnapshotRow.fetched_at))
        )
    ).scalars()
    snapshots = [
        ListingSnapshotResponse(
            id=row.id,
            content_hash=row.content_hash,
            raw_data=row.raw_data,
            provider_version=row.provider_version,
            fetched_at=row.fetched_at,
            created_at=row.created_at,
        )
        for row in snapshot_rows
    ]
    analysis_rows = (
        await session.execute(
            select(AnalysisResultRow)
            .where(AnalysisResultRow.listing_id == listing.id)
            .order_by(desc(AnalysisResultRow.created_at))
        )
    ).scalars()
    analysis_results = [
        AnalysisResultResponse(
            id=row.id,
            analysis_type=row.analysis_type,
            model_name=row.model_name,
            model_version=row.model_version,
            prompt_version=row.prompt_version,
            result_schema_version=row.result_schema_version,
            result=row.result_json,
            confidence=float(row.confidence),
            created_at=row.created_at,
        )
        for row in analysis_rows
    ]
    evaluation_rows = (
        await session.execute(
            select(DealEvaluationRow)
            .where(DealEvaluationRow.listing_id == listing.id)
            .order_by(desc(DealEvaluationRow.created_at))
        )
    ).scalars()
    evaluations = [
        DealEvaluationHistoryResponse(
            id=row.id,
            market_value_minimum=row.estimated_market_value_min,
            market_value_median=row.estimated_market_value_median,
            market_value_maximum=row.estimated_market_value_max,
            expected_resale_value=row.expected_resale_value,
            estimated_margin=row.estimated_margin,
            deal_score=row.deal_score,
            risk_score=row.risk_score,
            data_quality_score=row.data_quality_score,
            relevance_score=row.relevance_score,
            explanation=row.explanation,
            calculation_version=row.calculation_version,
            created_at=row.created_at,
        )
        for row in evaluation_rows
    ]
    feedback_rows = (
        await session.execute(
            select(UserFeedbackRow)
            .where(UserFeedbackRow.listing_id == listing.id)
            .order_by(desc(UserFeedbackRow.created_at))
        )
    ).scalars()
    feedback = [
        FeedbackResponse(
            id=row.id,
            feedback_type=row.feedback_type,
            corrected_products=row.corrected_products,
            corrected_attributes=row.corrected_attributes,
            corrected_value=row.corrected_value,
            note=row.note,
            base_listing_version=row.base_listing_version,
            created_at=row.created_at,
        )
        for row in feedback_rows
    ]
    seller_row = await session.get(SellerRow, listing.seller_id) if listing.seller_id is not None else None
    seller = (
        SellerResponse(
            id=seller_row.id,
            platform=seller_row.platform,
            external_id=seller_row.external_id,
            display_name=seller_row.display_name,
            account_age_text=seller_row.account_age_text,
            account_created_at=seller_row.account_created_at,
            rating_text=seller_row.rating_text,
            rating_score=seller_row.rating_score,
            review_count=seller_row.review_count,
            location=seller_row.location,
            raw_data=seller_row.raw_data,
            first_seen_at=seller_row.first_seen_at,
            last_seen_at=seller_row.last_seen_at,
        )
        if seller_row is not None
        else None
    )
    return ListingDetail(
        **summary.model_dump(),
        description=listing.description,
        location=listing.location,
        category_profile=listing.category_profile,
        current_snapshot_id=listing.current_snapshot_id,
        risk_signals=signals,
        products=products,
        snapshots=snapshots,
        analysis_results=analysis_results,
        evaluations=evaluations,
        feedback=feedback,
        seller=seller,
    )


async def upsert_seller(
    session: AsyncSession,
    workspace_id: UUID,
    platform: str,
    payload: SellerInput | None,
    observed_at: datetime,
) -> SellerRow | None:
    if payload is None:
        return None
    seller = (
        await session.execute(
            select(SellerRow).where(
                SellerRow.workspace_id == workspace_id,
                SellerRow.platform == platform,
                SellerRow.external_id == payload.external_id,
            )
        )
    ).scalar_one_or_none()
    if seller is None:
        seller = SellerRow(
            workspace_id=workspace_id,
            platform=platform,
            external_id=payload.external_id,
            display_name=payload.display_name,
            account_age_text=payload.account_age_text,
            account_created_at=payload.account_created_at,
            rating_text=payload.rating_text,
            rating_score=payload.rating_score,
            review_count=payload.review_count,
            location=payload.location,
            raw_data=payload.raw_data,
            first_seen_at=observed_at,
            last_seen_at=observed_at,
        )
        session.add(seller)
        await session.flush()
        return seller
    for field in (
        "display_name",
        "account_age_text",
        "account_created_at",
        "rating_text",
        "rating_score",
        "review_count",
        "location",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(seller, field, value)
    if payload.raw_data:
        seller.raw_data = payload.raw_data
    seller.last_seen_at = observed_at
    return seller


async def import_listing(
    session: AsyncSession,
    workspace_id: UUID,
    payload: ManualImportRequest,
) -> ImportResponse:
    validate_import_url(str(payload.url), payload.platform)
    digest = request_content_hash(payload)
    now = datetime.now(UTC)
    seller = await upsert_seller(session, workspace_id, payload.platform, payload.seller, now)
    if payload.search_profile_id is not None:
        profile = (
            await session.execute(
                select(SearchProfileRow).where(
                    SearchProfileRow.id == payload.search_profile_id,
                    SearchProfileRow.workspace_id == workspace_id,
                )
            )
        ).scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=404, detail="search profile not found")
    existing_result = await session.execute(
        select(ListingRow).where(
            ListingRow.workspace_id == workspace_id,
            ListingRow.platform == payload.platform,
            ListingRow.external_id == payload.external_id,
        )
    )
    listing = existing_result.scalar_one_or_none()
    if listing is None:
        listing = ListingRow(
            workspace_id=workspace_id,
            search_profile_id=payload.search_profile_id,
            seller_id=seller.id if seller is not None else None,
            platform=payload.platform,
            external_id=payload.external_id,
            url=str(payload.url),
            title=payload.title,
            description=payload.description,
            price=payload.price,
            shipping_cost=payload.shipping_cost,
            currency=payload.currency,
            location=payload.location,
            category_profile=payload.category_profile,
            published_at=payload.published_at,
            first_seen_at=now,
            last_seen_at=now,
            status="DISCOVERED",
            analysis_status="PENDING",
        )
        session.add(listing)
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            listing = (
                await session.execute(
                    select(ListingRow).where(
                        ListingRow.workspace_id == workspace_id,
                        ListingRow.platform == payload.platform,
                        ListingRow.external_id == payload.external_id,
                    )
                )
            ).scalar_one()
            listing.last_seen_at = now
    else:
        listing.last_seen_at = now
        if seller is not None:
            listing.seller_id = seller.id
        if payload.search_profile_id is not None:
            listing.search_profile_id = payload.search_profile_id

    snapshot_result = await session.execute(
        select(ListingSnapshotRow).where(
            ListingSnapshotRow.listing_id == listing.id,
            ListingSnapshotRow.content_hash == digest,
        )
    )
    snapshot = snapshot_result.scalar_one_or_none()
    if snapshot is not None:
        await session.commit()
        return ImportResponse(
            listing=await listing_detail(session, listing),
            snapshot_created=False,
            analysis_job_id=None,
        )

    snapshot = ListingSnapshotRow(
        workspace_id=workspace_id,
        listing_id=listing.id,
        content_hash=digest,
        raw_data={**payload.raw_data, "normalizedInput": payload.model_dump(mode="json")},
        provider_version=payload.provider_version,
        fetched_at=now,
    )
    session.add(snapshot)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        listing = (
            await session.execute(
                select(ListingRow).where(
                    ListingRow.workspace_id == workspace_id,
                    ListingRow.platform == payload.platform,
                    ListingRow.external_id == payload.external_id,
                )
            )
        ).scalar_one()
        return ImportResponse(
            listing=await listing_detail(session, listing),
            snapshot_created=False,
            analysis_job_id=None,
        )

    if listing.current_snapshot_id is not None:
        listing.version += 1
    listing.current_snapshot_id = snapshot.id
    listing.url = str(payload.url)
    listing.title = payload.title
    listing.description = payload.description
    listing.price = payload.price
    listing.shipping_cost = payload.shipping_cost
    listing.status = "RULE_ANALYZED"
    listing.analysis_status = "PENDING"

    rule_analysis = RuleExtractor().analyze(payload.title, payload.description)
    risk_result = RiskScoreEngine().score(rule_analysis.risk_signals)
    for signal in rule_analysis.risk_signals:
        session.add(
            RiskSignalRow(
                workspace_id=workspace_id,
                listing_id=listing.id,
                type=signal.type,
                severity=signal.weight,
                confidence=Decimal(str(signal.confidence)),
                positive=signal.positive,
                source=signal.source,
                evidence=signal.evidence,
            )
        )
    session.add(
        DealEvaluationRow(
            workspace_id=workspace_id,
            listing_id=listing.id,
            deal_score=None,
            risk_score=risk_result.score,
            data_quality_score=0,
            relevance_score=50,
            explanation={
                "risk": risk_result.model_dump(mode="json"),
                "products": [product.model_dump(mode="json") for product in rule_analysis.products],
                "contradictions": rule_analysis.contradictions,
                "deal": ["Noch keine ausreichenden Marktbeobachtungen."],
            },
            calculation_version="deal-v1+risk-v1",
            created_at=now,
        )
    )
    session.add(
        PriceObservationRow(
            workspace_id=workspace_id,
            canonical_product_id=None,
            listing_id=listing.id,
            platform=listing.platform,
            observed_price=listing.price,
            shipping_cost=listing.shipping_cost,
            currency=listing.currency,
            condition=None,
            observation_kind="active",
            region=listing.location,
            observed_at=now,
            source_quality=Decimal("1"),
            metadata_json={"snapshotId": str(snapshot.id), "providerVersion": payload.provider_version},
        )
    )
    await session.flush()
    await persist_listing_products(
        session,
        workspace_id,
        listing.id,
        listing.category_profile,
        rule_analysis.products,
        source="rules-v1",
    )
    job = AnalysisJobRow(
        workspace_id=workspace_id,
        listing_id=listing.id,
        snapshot_id=snapshot.id,
        job_type="text_analysis",
        required_capability="text-small",
        input_hash=digest,
        priority=10,
        status="PENDING",
        available_at=now,
    )
    session.add(job)
    session.add(
        AuditEventRow(
            workspace_id=workspace_id,
            actor_user_id=None,
            event_type="listing.snapshotImported",
            aggregate_type="listing",
            aggregate_id=listing.id,
            payload={
                "snapshotId": str(snapshot.id),
                "contentHash": digest,
                "providerVersion": payload.provider_version,
            },
        )
    )
    await session.commit()
    await session.refresh(listing)
    return ImportResponse(
        listing=await listing_detail(session, listing),
        snapshot_created=True,
        analysis_job_id=job.id,
    )
