import csv
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import desc, select

from ..context import Context
from ..db_models import (
    CanonicalProductRow,
    ListingRow,
    NotificationDeliveryRow,
    NotificationRow,
    PriceObservationRow,
)
from ..market_service import estimate_listing_market, evaluate_listing_record
from ..notification_service import dispatch_ntfy_notifications
from ..schemas import (
    CsvImportResponse,
    ListingEvaluationResponse,
    MarketEstimateResponse,
    NotificationResponse,
    PriceObservationCreate,
    PriceObservationResponse,
)

router = APIRouter(tags=["market-data"])


@router.post("/notifications/dispatch")
async def dispatch_notifications(context: Context) -> dict[str, int]:
    return {"delivered": await dispatch_ntfy_notifications(context.session, context.workspace_id)}


@router.post("/price-observations", response_model=PriceObservationResponse, status_code=201)
async def create_observation(payload: PriceObservationCreate, context: Context) -> PriceObservationResponse:
    if payload.listing_id is not None:
        result = await context.session.execute(
            select(ListingRow.id).where(
                ListingRow.id == payload.listing_id,
                ListingRow.workspace_id == context.workspace_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="listing not found")
    if payload.canonical_product_id is not None:
        result = await context.session.execute(
            select(CanonicalProductRow.id).where(
                CanonicalProductRow.id == payload.canonical_product_id,
                CanonicalProductRow.workspace_id == context.workspace_id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="canonical product not found")
    row = PriceObservationRow(
        workspace_id=context.workspace_id,
        canonical_product_id=payload.canonical_product_id,
        listing_id=payload.listing_id,
        platform=payload.platform,
        observed_price=payload.observed_price,
        shipping_cost=payload.shipping_cost,
        currency=payload.currency,
        condition=payload.condition,
        observation_kind=payload.observation_kind,
        region=payload.region,
        observed_at=payload.observed_at,
        source_quality=Decimal(str(payload.source_quality)),
        metadata_json=payload.metadata,
    )
    context.session.add(row)
    await context.session.commit()
    return PriceObservationResponse(id=row.id, **payload.model_dump(by_alias=False))


@router.get("/price-observations", response_model=list[PriceObservationResponse])
async def price_observations(
    context: Context,
    canonical_product_id: UUID | None = Query(default=None, alias="canonicalProductId"),
    listing_id: UUID | None = Query(default=None, alias="listingId"),
) -> list[PriceObservationResponse]:
    query = select(PriceObservationRow).where(PriceObservationRow.workspace_id == context.workspace_id)
    if canonical_product_id is not None:
        query = query.where(PriceObservationRow.canonical_product_id == canonical_product_id)
    if listing_id is not None:
        query = query.where(PriceObservationRow.listing_id == listing_id)
    rows = (await context.session.execute(query.order_by(desc(PriceObservationRow.observed_at)).limit(500))).scalars()
    return [
        PriceObservationResponse(
            id=row.id,
            canonical_product_id=row.canonical_product_id,
            listing_id=row.listing_id,
            platform=row.platform,
            observed_price=row.observed_price,
            shipping_cost=row.shipping_cost,
            currency=row.currency,
            condition=row.condition,
            observation_kind=row.observation_kind,
            region=row.region,
            observed_at=row.observed_at,
            source_quality=float(row.source_quality),
            metadata=row.metadata_json,
        )
        for row in rows
    ]


@router.get("/listings/{listing_id}/market-value", response_model=MarketEstimateResponse)
async def market_value(listing_id: UUID, context: Context) -> MarketEstimateResponse:
    _, estimate = await estimate_listing_market(context.session, context.workspace_id, listing_id)
    return MarketEstimateResponse(**estimate.model_dump())


@router.post("/listings/{listing_id}/evaluate", response_model=ListingEvaluationResponse)
async def evaluate_listing(listing_id: UUID, context: Context) -> ListingEvaluationResponse:
    outcome = await evaluate_listing_record(context.session, context.workspace_id, listing_id)
    await context.session.commit()
    return ListingEvaluationResponse(
        listing_id=outcome.listing.id,
        market=MarketEstimateResponse(**outcome.market.model_dump()),
        deal_score=outcome.deal_score,
        risk_score=outcome.risk_score,
        notification_created=outcome.notification_created,
    )


@router.get("/notifications", response_model=list[NotificationResponse])
async def notifications(context: Context, pending_only: bool = False) -> list[NotificationResponse]:
    query = select(NotificationRow).where(NotificationRow.workspace_id == context.workspace_id)
    if pending_only:
        query = query.join(
            NotificationDeliveryRow, NotificationDeliveryRow.notification_id == NotificationRow.id
        ).where(
            NotificationDeliveryRow.workspace_id == context.workspace_id,
            NotificationDeliveryRow.channel == "desktop",
            NotificationDeliveryRow.status == "PENDING",
        )
    rows = (await context.session.execute(query.order_by(desc(NotificationRow.created_at)).limit(100))).scalars()
    return [
        NotificationResponse(
            id=row.id,
            listing_id=row.listing_id,
            reason=row.reason,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/notifications/{notification_id}/delivered", status_code=204)
async def mark_desktop_notification_delivered(notification_id: UUID, context: Context) -> Response:
    delivery = (
        await context.session.execute(
            select(NotificationDeliveryRow).where(
                NotificationDeliveryRow.notification_id == notification_id,
                NotificationDeliveryRow.workspace_id == context.workspace_id,
                NotificationDeliveryRow.channel == "desktop",
            )
        )
    ).scalar_one_or_none()
    if delivery is None:
        raise HTTPException(status_code=404, detail="desktop notification delivery not found")
    delivery.status = "DELIVERED"
    delivery.delivered_at = datetime.now(UTC)
    await context.session.commit()
    return Response(status_code=204)


@router.post("/market-data/imports/csv", response_model=CsvImportResponse, status_code=201)
async def import_csv(
    context: Context,
    file: UploadFile = File(...),
) -> CsvImportResponse:
    allowed_types = {
        "text/csv",
        "text/plain",
        "application/csv",
        "application/vnd.ms-excel",
        "application/octet-stream",
    }
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=415, detail="only CSV uploads are accepted")
    content = await file.read(2_000_001)
    if len(content) > 2_000_000:
        raise HTTPException(status_code=413, detail="CSV exceeds the 2 MB limit")
    try:
        decoded = content.decode("utf-8-sig")
        dialect = csv.Sniffer().sniff(decoded[:4096], delimiters=",;")
        rows = list(csv.DictReader(StringIO(decoded), dialect=dialect))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise HTTPException(status_code=422, detail="CSV is not valid UTF-8 tabular data") from exc
    if not rows or len(rows) > 10_000:
        raise HTTPException(status_code=422, detail="CSV must contain between 1 and 10000 rows")

    validated: list[PriceObservationCreate] = []
    errors: list[str] = []
    for number, row in enumerate(rows, start=2):
        cleaned = {key: value for key, value in row.items() if key and value not in (None, "")}
        try:
            validated.append(PriceObservationCreate.model_validate(cleaned))
        except ValidationError as exc:
            errors.append(f"row {number}: {exc.errors()[0]['msg']}")
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors[:20]))

    for payload in validated:
        context.session.add(
            PriceObservationRow(
                workspace_id=context.workspace_id,
                canonical_product_id=payload.canonical_product_id,
                listing_id=payload.listing_id,
                platform=payload.platform,
                observed_price=payload.observed_price,
                shipping_cost=payload.shipping_cost,
                currency=payload.currency,
                condition=payload.condition,
                observation_kind=payload.observation_kind,
                region=payload.region,
                observed_at=payload.observed_at,
                source_quality=Decimal(str(payload.source_quality)),
                metadata_json=payload.metadata,
            )
        )
    await context.session.commit()
    return CsvImportResponse(rows_imported=len(validated), filename=file.filename or "market-data.csv")
