from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from deal_scanner_ebay import EbayProvider, EbaySettings
from deal_scanner_manual import extract_ebay_legacy_id
from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..context import BrowserContext, Context
from ..db_models import IdempotencyKeyRow, ListingRow
from ..schemas import ImportResponse, ManualImportRequest, SellerInput
from ..services import import_listing, listing_detail, request_content_hash
from ..settings import get_settings

router = APIRouter(prefix="/imports", tags=["imports"])


async def _resolve_manual_ebay(payload: ManualImportRequest) -> ManualImportRequest:
    if (
        payload.platform != "ebay"
        or payload.provider_version.startswith("browse-")
        or payload.provider_version.startswith("cloud-migration-")
    ):
        return payload
    legacy_id = extract_ebay_legacy_id(str(payload.url))
    if legacy_id is None:
        raise HTTPException(status_code=422, detail="eBay URL contains no supported legacy item id")
    settings = get_settings()
    if not settings.ebay_client_id or not settings.ebay_client_secret:
        raise HTTPException(status_code=503, detail="eBay credentials are required to resolve manual URLs")
    provider = EbayProvider(
        EbaySettings(
            client_id=settings.ebay_client_id,
            client_secret=settings.ebay_client_secret,
            environment=settings.ebay_environment,
        )
    )
    try:
        snapshot = await provider.fetch_details(legacy_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="eBay listing was not found by the official API")
        normalized = await provider.normalize(snapshot)
    finally:
        await provider.close()
    seller_data = snapshot.payload.get("seller")
    seller = (
        SellerInput(
            external_id=normalized.seller_external_id,
            display_name=seller_data.get("username"),
            rating_score=seller_data.get("feedbackPercentage"),
            review_count=seller_data.get("feedbackScore"),
            raw_data=seller_data,
        )
        if normalized.seller_external_id and isinstance(seller_data, dict)
        else None
    )
    return payload.model_copy(
        update={
            "external_id": legacy_id,
            "url": normalized.url,
            "title": normalized.title,
            "description": normalized.description,
            "price": normalized.price.amount,
            "shipping_cost": (normalized.shipping_cost.amount if normalized.shipping_cost else Decimal("0")),
            "currency": normalized.price.currency,
            "location": normalized.location,
            "raw_data": snapshot.payload,
            "provider_version": snapshot.provider_version,
            "seller": seller,
        }
    )


async def _idempotent_import(
    payload: ManualImportRequest,
    context: Context,
    idempotency_key: str | None,
    operation: str,
) -> ImportResponse:
    if not idempotency_key:
        return await import_listing(context.session, context.workspace_id, payload)
    if len(idempotency_key) > 255:
        raise HTTPException(status_code=422, detail="Idempotency-Key is too long")

    digest = request_content_hash(payload)
    existing = (
        await context.session.execute(
            select(IdempotencyKeyRow).where(
                IdempotencyKeyRow.workspace_id == context.workspace_id,
                IdempotencyKeyRow.operation == operation,
                IdempotencyKeyRow.key == idempotency_key,
                IdempotencyKeyRow.expires_at > datetime.now(UTC),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_hash != digest:
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key was already used for a different request",
            )
        if existing.resource_id is None:
            raise HTTPException(status_code=409, detail="idempotent request is still in progress")
        listing = await context.session.get(ListingRow, existing.resource_id)
        if listing is None or listing.workspace_id != context.workspace_id:
            raise HTTPException(status_code=409, detail="idempotent resource is unavailable")
        return ImportResponse(
            listing=await listing_detail(context.session, listing),
            snapshot_created=False,
            analysis_job_id=None,
        )

    reservation = IdempotencyKeyRow(
        workspace_id=context.workspace_id,
        key=idempotency_key,
        operation=operation,
        request_hash=digest,
        resource_id=None,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    context.session.add(reservation)
    try:
        await context.session.commit()
    except IntegrityError:
        await context.session.rollback()
        return await _idempotent_import(payload, context, idempotency_key, operation)
    reservation_id = reservation.id

    try:
        response = await import_listing(context.session, context.workspace_id, payload)
    except Exception:
        await context.session.rollback()
        stored_reservation = await context.session.get(IdempotencyKeyRow, reservation_id)
        if stored_reservation is not None:
            await context.session.delete(stored_reservation)
            await context.session.commit()
        raise
    stored_reservation = await context.session.get(IdempotencyKeyRow, reservation_id)
    if stored_reservation is None:
        raise HTTPException(status_code=409, detail="idempotency reservation was lost")
    stored_reservation.resource_id = response.listing.id
    await context.session.commit()
    return response


@router.post("/manual", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
async def manual_import(
    payload: ManualImportRequest,
    context: Context,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ImportResponse:
    resolved = await _resolve_manual_ebay(payload)
    return await _idempotent_import(resolved, context, idempotency_key, "manual-import")


@router.post("/browser", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
async def browser_import(
    payload: ManualImportRequest,
    context: BrowserContext,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ImportResponse:
    return await _idempotent_import(payload, context, idempotency_key, "browser-import")


@router.post("/email", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
async def email_import(
    payload: ManualImportRequest,
    context: Context,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ImportResponse:
    return await _idempotent_import(payload, context, idempotency_key, "email-import")
