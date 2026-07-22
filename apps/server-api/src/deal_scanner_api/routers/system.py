from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func, select

from ..context import Context
from ..db_models import (
    AnalysisJobRow,
    CanonicalProductRow,
    ExtensionPairingRow,
    ListingRow,
    MailImportRow,
    ProductAliasRow,
    ProviderSyncRunRow,
    SearchProfileRow,
    WorkerRow,
)
from ..schemas import (
    ErpExportResponse,
    MailImportCreate,
    MailImportResponse,
    PairingResponse,
    ProductPage,
    ProductResponse,
    ProviderSyncRunCreate,
    ProviderSyncRunPage,
    ProviderSyncRunResponse,
    ProviderSyncRunUpdate,
)

router = APIRouter(tags=["system"])


@router.get("/system/status")
async def system_status(context: Context) -> dict[str, int | str]:
    listing_count = await context.session.scalar(
        select(func.count()).select_from(ListingRow).where(ListingRow.workspace_id == context.workspace_id)
    )
    open_jobs = await context.session.scalar(
        select(func.count())
        .select_from(AnalysisJobRow)
        .where(
            AnalysisJobRow.workspace_id == context.workspace_id,
            AnalysisJobRow.status.in_(["PENDING", "RETRY", "LEASED"]),
        )
    )
    workers = await context.session.scalar(
        select(func.count()).select_from(WorkerRow).where(WorkerRow.workspace_id == context.workspace_id)
    )
    return {
        "status": "ok",
        "listings": listing_count or 0,
        "openJobs": open_jobs or 0,
        "workers": workers or 0,
    }


@router.post("/extension/pairings", response_model=PairingResponse, status_code=201)
async def create_pairing(context: Context) -> PairingResponse:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    row = ExtensionPairingRow(
        workspace_id=context.workspace_id,
        created_by_user_id=context.identity.user_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=expires_at,
    )
    context.session.add(row)
    await context.session.commit()
    return PairingResponse(id=row.id, token=token, expires_at=expires_at)


@router.delete("/extension/pairings/{pairing_id}", status_code=204)
async def revoke_pairing(pairing_id: UUID, context: Context) -> None:
    pairing = (
        await context.session.execute(
            select(ExtensionPairingRow).where(
                ExtensionPairingRow.id == pairing_id,
                ExtensionPairingRow.workspace_id == context.workspace_id,
            )
        )
    ).scalar_one_or_none()
    if pairing is None:
        raise HTTPException(status_code=404, detail="pairing not found")
    pairing.revoked_at = datetime.now(UTC)
    await context.session.commit()


@router.post("/erp/exports/{listing_id}", response_model=ErpExportResponse)
async def mock_erp_export(listing_id: UUID, context: Context) -> ErpExportResponse:
    result = await context.session.execute(
        select(ListingRow).where(ListingRow.id == listing_id, ListingRow.workspace_id == context.workspace_id)
    )
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="listing not found")
    return ErpExportResponse(
        listing_id=listing.id,
        purchase_payload={
            "externalReference": f"deal-scanner:{listing.id}",
            "title": listing.title,
            "purchasePrice": str(listing.price),
            "currency": listing.currency,
            "sourceUrl": listing.url,
        },
    )


@router.get("/products", response_model=ProductPage)
async def products(context: Context) -> ProductPage:
    rows = list(
        (
            await context.session.execute(
                select(CanonicalProductRow)
                .where(CanonicalProductRow.workspace_id == context.workspace_id)
                .order_by(CanonicalProductRow.product_type, CanonicalProductRow.model)
            )
        ).scalars()
    )
    aliases_by_product: dict[UUID, list[str]] = {row.id: [] for row in rows}
    if rows:
        aliases = await context.session.execute(
            select(ProductAliasRow).where(
                ProductAliasRow.workspace_id == context.workspace_id,
                ProductAliasRow.canonical_product_id.in_([row.id for row in rows]),
            )
        )
        for alias in aliases.scalars():
            aliases_by_product[alias.canonical_product_id].append(alias.alias)
    return ProductPage(
        items=[
            ProductResponse(
                id=row.id,
                category_profile=row.category_profile,
                product_type=row.product_type,
                manufacturer=row.manufacturer,
                model=row.model,
                variant=row.variant,
                aliases=sorted(aliases_by_product[row.id]),
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
    )


def _sync_response(row: ProviderSyncRunRow) -> ProviderSyncRunResponse:
    return ProviderSyncRunResponse(
        id=row.id,
        search_profile_id=row.search_profile_id,
        provider=row.provider,
        status=row.status,
        cursor=row.cursor,
        discovered_count=row.discovered_count,
        imported_count=row.imported_count,
        error_summary=row.error_summary,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


@router.get("/provider-sync-runs", response_model=ProviderSyncRunPage)
async def provider_sync_runs(
    context: Context,
    provider: str | None = None,
    search_profile_id: UUID | None = Query(default=None, alias="searchProfileId"),
    limit: int = Query(default=100, ge=1, le=500),
) -> ProviderSyncRunPage:
    query = select(ProviderSyncRunRow).where(ProviderSyncRunRow.workspace_id == context.workspace_id)
    if provider is not None:
        query = query.where(ProviderSyncRunRow.provider == provider)
    if search_profile_id is not None:
        query = query.where(ProviderSyncRunRow.search_profile_id == search_profile_id)
    rows = (await context.session.execute(query.order_by(desc(ProviderSyncRunRow.started_at)).limit(limit))).scalars()
    return ProviderSyncRunPage(items=[_sync_response(row) for row in rows])


@router.post("/provider-sync-runs", response_model=ProviderSyncRunResponse, status_code=201)
async def create_provider_sync_run(
    payload: ProviderSyncRunCreate,
    context: Context,
) -> ProviderSyncRunResponse:
    profile = (
        await context.session.execute(
            select(SearchProfileRow.id).where(
                SearchProfileRow.id == payload.search_profile_id,
                SearchProfileRow.workspace_id == context.workspace_id,
            )
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="search profile not found")
    row = ProviderSyncRunRow(
        workspace_id=context.workspace_id,
        search_profile_id=payload.search_profile_id,
        provider=payload.provider,
        status="RUNNING",
        cursor=payload.cursor,
        started_at=datetime.now(UTC),
    )
    context.session.add(row)
    await context.session.commit()
    return _sync_response(row)


@router.patch("/provider-sync-runs/{run_id}", response_model=ProviderSyncRunResponse)
async def complete_provider_sync_run(
    run_id: UUID,
    payload: ProviderSyncRunUpdate,
    context: Context,
) -> ProviderSyncRunResponse:
    row = (
        await context.session.execute(
            select(ProviderSyncRunRow).where(
                ProviderSyncRunRow.id == run_id,
                ProviderSyncRunRow.workspace_id == context.workspace_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="provider sync run not found")
    if row.status != "RUNNING":
        raise HTTPException(status_code=409, detail="provider sync run is already finalized")
    row.status = payload.status
    row.cursor = payload.cursor
    row.discovered_count = payload.discovered_count
    row.imported_count = payload.imported_count
    row.error_summary = payload.error_summary
    row.completed_at = datetime.now(UTC)
    await context.session.commit()
    return _sync_response(row)


def _mail_response(row: MailImportRow) -> MailImportResponse:
    return MailImportResponse(
        id=row.id,
        message_id=row.message_id,
        sender=row.sender,
        subject=row.subject,
        received_at=row.received_at,
        raw_storage_path=row.raw_storage_path,
        raw_sha256=row.raw_sha256,
        parser_version=row.parser_version,
        status=row.status,
        parsed_data=row.parsed_data,
        error_summary=row.error_summary,
        created_at=row.created_at,
    )


@router.get("/mail-imports", response_model=list[MailImportResponse])
async def mail_imports(context: Context) -> list[MailImportResponse]:
    rows = (
        await context.session.execute(
            select(MailImportRow)
            .where(MailImportRow.workspace_id == context.workspace_id)
            .order_by(desc(MailImportRow.received_at))
            .limit(200)
        )
    ).scalars()
    return [_mail_response(row) for row in rows]


@router.post("/mail-imports", response_model=MailImportResponse, status_code=201)
async def record_mail_import(payload: MailImportCreate, context: Context) -> MailImportResponse:
    row = (
        await context.session.execute(
            select(MailImportRow).where(
                MailImportRow.workspace_id == context.workspace_id,
                MailImportRow.message_id == payload.message_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = MailImportRow(workspace_id=context.workspace_id, **payload.model_dump(by_alias=False))
        context.session.add(row)
        await context.session.commit()
    return _mail_response(row)
