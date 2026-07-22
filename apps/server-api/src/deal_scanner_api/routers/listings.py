from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, desc, or_, select

from ..context import Context
from ..db_models import (
    AnalysisJobRow,
    AnalysisResultRow,
    AuditEventRow,
    ListingRow,
    ListingSnapshotRow,
    UserFeedbackRow,
)
from ..schemas import FeedbackCreate, JobResponse, ListingDetail, ListingPage
from ..services import listing_detail, listing_summary

router = APIRouter(prefix="/listings", tags=["listings"])


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
        select(ListingRow).where(ListingRow.id == listing_id, ListingRow.workspace_id == context.workspace_id)
    )
    listing = result.scalar_one_or_none()
    if listing is None or listing.current_snapshot_id is None:
        raise HTTPException(status_code=404, detail="listing snapshot not found")
    snapshot = await context.session.get(ListingSnapshotRow, listing.current_snapshot_id)
    assert snapshot is not None
    digest = hashlib.sha256(f"{snapshot.content_hash}:manual:{uuid4()}".encode()).hexdigest()
    job = AnalysisJobRow(
        workspace_id=context.workspace_id,
        listing_id=listing.id,
        snapshot_id=snapshot.id,
        job_type="text_analysis",
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
    base_version = listing.version
    state_updates = {
        "favorite": ("is_favorite", True),
        "unfavorite": ("is_favorite", False),
        "hide": ("is_hidden", True),
        "unhide": ("is_hidden", False),
    }
    state_update = state_updates.get(payload.feedback_type)
    if state_update is not None:
        field, value = state_update
        if getattr(listing, field) != value:
            setattr(listing, field, value)
            listing.version += 1
    corrections = {
        "products": payload.corrected_products,
        "attributes": payload.corrected_attributes,
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
