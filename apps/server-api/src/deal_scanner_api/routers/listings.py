from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from deal_scanner_core.models import ProductDetection
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, desc, or_, select

from ..comparison_service import COMPARISON_VERSION
from ..context import Context
from ..db_models import (
    AnalysisJobRow,
    AnalysisResultRow,
    AuditEventRow,
    DealEvaluationRow,
    ListingRow,
    ListingSnapshotRow,
    UserFeedbackRow,
)
from ..product_service import persist_listing_products
from ..schemas import FeedbackCreate, JobResponse, ListingDetail, ListingPage
from ..services import listing_detail, listing_summary
from ..tracking_service import archive_expired_listings

router = APIRouter(prefix="/listings", tags=["listings"])


@router.post("/maintenance/archive")
async def archive_old_offers(context: Context) -> dict[str, int]:
    return {"archived": await archive_expired_listings(context.session, context.workspace_id)}


def _encode_cursor(listing: ListingRow) -> str:
    payload = json.dumps({"time": listing.last_seen_at.isoformat(), "id": str(listing.id)})
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        return datetime.fromisoformat(payload["time"]), UUID(payload["id"])
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="invalid cursor") from exc


@router.get("", response_model=ListingPage)
async def list_listings(
    context: Context,
    limit: int = Query(default=30, ge=1, le=100),
    cursor: str | None = None,
    view: Literal["all", "new", "favorites", "hidden"] = "all",
    assessment: Literal["all", "interesting", "suspicious", "unknown"] = "all",
    q: str | None = Query(default=None, max_length=100),
    platforms: list[str] | None = Query(default=None),
    search_profile_id: UUID | None = Query(default=None, alias="searchProfileId"),
    minimum_deal_score: int | None = Query(default=None, ge=0, le=100, alias="minimumDealScore"),
    maximum_risk_score: int | None = Query(default=None, ge=0, le=100, alias="maximumRiskScore"),
    minimum_data_quality: int | None = Query(default=None, ge=0, le=100, alias="minimumDataQuality"),
) -> ListingPage:
    query = select(ListingRow).where(ListingRow.workspace_id == context.workspace_id)
    if view == "hidden":
        query = query.where(ListingRow.is_hidden.is_(True))
    else:
        query = query.where(ListingRow.is_hidden.is_(False))
    if view == "favorites":
        query = query.where(ListingRow.is_favorite.is_(True))
    elif view == "new":
        query = query.where(ListingRow.first_seen_at >= datetime.now(UTC) - timedelta(hours=24))
    if platforms:
        query = query.where(ListingRow.platform.in_(platforms))
    if search_profile_id is not None:
        query = query.where(ListingRow.search_profile_id == search_profile_id)
    if q and q.strip():
        term = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            or_(
                ListingRow.title.ilike(f"%{term}%", escape="\\"), ListingRow.description.ilike(f"%{term}%", escape="\\")
            )
        )
    if assessment != "all" or any(
        value is not None for value in (minimum_deal_score, maximum_risk_score, minimum_data_quality)
    ):
        latest = (
            select(DealEvaluationRow.id)
            .where(
                DealEvaluationRow.workspace_id == context.workspace_id,
                DealEvaluationRow.listing_id == ListingRow.id,
            )
            .order_by(DealEvaluationRow.created_at.desc(), DealEvaluationRow.id.desc())
            .limit(1)
            .correlate(ListingRow)
            .scalar_subquery()
        )
        query = query.outerjoin(DealEvaluationRow, DealEvaluationRow.id == latest)
        market_current = DealEvaluationRow.calculation_version.endswith(f"+{COMPARISON_VERSION}")
        quality = minimum_data_quality if minimum_data_quality is not None else 40
        risk = maximum_risk_score if maximum_risk_score is not None else 45
        if assessment == "interesting":
            query = query.where(
                market_current,
                DealEvaluationRow.deal_score >= (minimum_deal_score if minimum_deal_score is not None else 75),
                DealEvaluationRow.risk_score <= risk,
                DealEvaluationRow.data_quality_score >= quality,
            )
        elif assessment == "suspicious":
            query = query.where(DealEvaluationRow.risk_score > risk)
        elif assessment == "unknown":
            query = query.where(
                or_(
                    DealEvaluationRow.id.is_(None),
                    DealEvaluationRow.deal_score.is_(None),
                    DealEvaluationRow.data_quality_score < quality,
                    ~market_current,
                )
            )
        else:
            if minimum_deal_score is not None:
                query = query.where(market_current, DealEvaluationRow.deal_score >= minimum_deal_score)
            if maximum_risk_score is not None:
                query = query.where(DealEvaluationRow.risk_score <= maximum_risk_score)
            if minimum_data_quality is not None:
                query = query.where(market_current, DealEvaluationRow.data_quality_score >= minimum_data_quality)
    if cursor:
        cursor_time, cursor_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                ListingRow.last_seen_at < cursor_time,
                and_(ListingRow.last_seen_at == cursor_time, ListingRow.id < cursor_id),
            )
        )
    result = await context.session.execute(
        query.order_by(desc(ListingRow.last_seen_at), desc(ListingRow.id)).limit(limit + 1)
    )
    rows = list(result.scalars())
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    items = [await listing_summary(context.session, row) for row in page_rows]
    return ListingPage(
        items=items,
        next_cursor=_encode_cursor(page_rows[-1]) if has_more and page_rows else None,
    )


@router.get("/{listing_id}", response_model=ListingDetail)
async def get_listing(listing_id: UUID, context: Context) -> ListingDetail:
    result = await context.session.execute(
        select(ListingRow).where(ListingRow.id == listing_id, ListingRow.workspace_id == context.workspace_id)
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")
    return await listing_detail(context.session, listing)


@router.post("/{listing_id}/reanalyze", response_model=JobResponse, status_code=201)
async def reanalyze(listing_id: UUID, context: Context) -> JobResponse:
    result = await context.session.execute(
        select(ListingRow)
        .where(ListingRow.id == listing_id, ListingRow.workspace_id == context.workspace_id)
        .with_for_update()
    )
    listing = result.scalar_one_or_none()
    if listing is None or listing.current_snapshot_id is None:
        raise HTTPException(status_code=404, detail="listing snapshot not found")
    snapshot = await context.session.get(ListingSnapshotRow, listing.current_snapshot_id)
    assert snapshot is not None
    pending = (
        await context.session.execute(
            select(AnalysisJobRow)
            .where(
                AnalysisJobRow.workspace_id == context.workspace_id,
                AnalysisJobRow.listing_id == listing.id,
                AnalysisJobRow.snapshot_id == snapshot.id,
                AnalysisJobRow.job_type == "deep_text_analysis",
                AnalysisJobRow.status.in_(["PENDING", "RETRY", "LEASED"]),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if pending is not None:
        from .workers import _job_response

        return _job_response(pending)
    digest = hashlib.sha256(f"{snapshot.content_hash}:manual:{uuid4()}".encode()).hexdigest()
    job = AnalysisJobRow(
        workspace_id=context.workspace_id,
        listing_id=listing.id,
        snapshot_id=snapshot.id,
        job_type="deep_text_analysis",
        required_capability="text-small",
        input_hash=digest,
        priority=20,
        status="PENDING",
        available_at=datetime.now(UTC),
    )
    context.session.add(job)
    listing.analysis_status = "PENDING"
    await context.session.commit()
    return JobResponse(
        id=job.id,
        listing_id=job.listing_id,
        snapshot_id=job.snapshot_id,
        job_type=job.job_type,
        required_capability=job.required_capability,
        input_hash=job.input_hash,
        priority=job.priority,
        status=job.status,
        lease_expires_at=job.lease_expires_at,
        attempts=job.attempts,
    )


@router.post("/{listing_id}/feedback", status_code=status.HTTP_201_CREATED)
async def create_feedback(listing_id: UUID, payload: FeedbackCreate, context: Context) -> dict[str, str | int]:
    result = await context.session.execute(
        select(ListingRow).where(ListingRow.id == listing_id, ListingRow.workspace_id == context.workspace_id)
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")
    if listing.version != payload.base_listing_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "listing changed", "currentVersion": listing.version},
        )
    feedback = UserFeedbackRow(
        workspace_id=context.workspace_id,
        listing_id=listing.id,
        user_id=context.identity.user_id,
        **payload.model_dump(by_alias=False),
    )
    context.session.add(feedback)
    await context.session.flush()
    base_version = listing.version
    listing_changed = False
    state_updates = {
        "favorite": ("is_favorite", True),
        "unfavorite": ("is_favorite", False),
        "hide": ("is_hidden", True),
        "unhide": ("is_hidden", False),
    }
    state_update = state_updates.get(payload.feedback_type)
    if state_update is not None:
        if payload.feedback_type in {"hide", "unhide"}:
            listing.removed_at = None  # Manual choices must never be undone by the importer.
        field, value = state_update
        if getattr(listing, field) != value:
            setattr(listing, field, value)
            listing_changed = True
    corrections = {
        "products": [item.model_dump(mode="json", by_alias=True) for item in payload.corrected_products]
        if payload.corrected_products is not None
        else None,
        "attributes": [item.model_dump(mode="json", by_alias=True) for item in payload.corrected_attributes]
        if payload.corrected_attributes is not None
        else None,
        "value": payload.corrected_value,
        "note": payload.note,
        "feedbackType": payload.feedback_type,
    }
    if any(
        value is not None
        for value in (
            payload.corrected_products,
            payload.corrected_attributes,
            payload.corrected_value,
        )
    ):
        correction_hash = hashlib.sha256(
            json.dumps(corrections, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        if payload.corrected_products is not None:
            detections = [
                ProductDetection(
                    product_type=item.product_type,
                    manufacturer=item.manufacturer,
                    model=item.model,
                    variant=item.variant,
                    quantity=item.quantity,
                    confidence=1,
                    sources=["userFeedback"],
                    evidence=item.evidence,
                )
                for item in payload.corrected_products
            ]
            await persist_listing_products(
                context.session,
                context.workspace_id,
                listing.id,
                listing.category_profile,
                detections,
                source=f"user-correction:{feedback.id}",
                attributes=[item.model_dump(mode="json", by_alias=True) for item in payload.corrected_attributes]
                if payload.corrected_attributes is not None
                else None,
            )
        context.session.add(
            AnalysisResultRow(
                workspace_id=context.workspace_id,
                listing_id=listing.id,
                job_id=None,
                analysis_type="user_correction",
                model_name="human",
                model_version="1",
                prompt_version="none",
                result_schema_version="feedback-v1",
                input_hash=correction_hash,
                result_json=corrections,
                confidence=Decimal("1"),
            )
        )
        listing_changed = True
    if listing_changed:
        listing.version += 1
    context.session.add(
        AuditEventRow(
            workspace_id=context.workspace_id,
            actor_user_id=context.identity.user_id,
            event_type="listing.feedbackCreated",
            aggregate_type="listing",
            aggregate_id=listing.id,
            payload={"feedbackType": payload.feedback_type, "baseVersion": base_version},
        )
    )
    await context.session.commit()
    return {"id": str(feedback.id), "status": "accepted", "version": listing.version}
