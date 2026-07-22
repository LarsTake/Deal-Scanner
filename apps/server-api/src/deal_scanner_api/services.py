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
    AuditEventRow,
    DealEvaluationRow,
    ListingRow,
    ListingSnapshotRow,
    PriceObservationRow,
    RiskSignalRow,
    SearchProfileRow,
)
from .product_service import persist_listing_products
from .schemas import (
    ImportResponse,
    ListingDetail,
    ListingSummary,
    ManualImportRequest,
    RiskSignalResponse,
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
    return ListingDetail(
        **summary.model_dump(),
        description=listing.description,
        location=listing.location,
        category_profile=listing.category_profile,
        current_snapshot_id=listing.current_snapshot_id,
        risk_signals=signals,
    )


async def import_listing(
    session: AsyncSession,
    workspace_id: UUID,
    payload: ManualImportRequest,
) -> ImportResponse:
    validate_import_url(str(payload.url), payload.platform)
    digest = request_content_hash(payload)
    now = datetime.now(UTC)
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
