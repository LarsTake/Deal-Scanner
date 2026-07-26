from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func, select

from ..audit import record_audit_event
from ..context import Context
from ..db_models import (
    AnalysisJobRow,
    CanonicalProductRow,
    ExtensionPairingRow,
    ListingRow,
    MailImportRow,
    ProductAliasRow,
    ProviderConfigurationRow,
    ProviderSyncRunRow,
    SearchProfileRow,
    WorkerRow,
)
from ..erp_service import MockErpIntegrationAdapter
from ..schemas import (
    ComponentHealth,
    ErpExportResponse,
    ExtensionConnectionCreate,
    ExtensionConnectionCreatedResponse,
    ExtensionConnectionResponse,
    MailImportCreate,
    MailImportResponse,
    PairingResponse,
    ProductPage,
    ProductResponse,
    ProviderConfigurationResponse,
    ProviderConfigurationUpsert,
    ProviderSyncRunCreate,
    ProviderSyncRunPage,
    ProviderSyncRunResponse,
    ProviderSyncRunUpdate,
    SystemStatusResponse,
)
from ..settings import get_settings

router = APIRouter(tags=["system"])
SUPPORTED_PROVIDERS = {"ebay", "kleinanzeigenEmail", "browser", "manual", "ollama"}


@router.get("/system/status", response_model=SystemStatusResponse)
async def system_status(context: Context) -> SystemStatusResponse:
    checked_at = datetime.now(UTC)
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
    configurations = list(
        (
            await context.session.execute(
                select(ProviderConfigurationRow).where(ProviderConfigurationRow.workspace_id == context.workspace_id)
            )
        ).scalars()
    )
    configuration_by_provider = {row.provider: row for row in configurations}
    latest_sync = (
        await context.session.execute(
            select(ProviderSyncRunRow)
            .where(
                ProviderSyncRunRow.workspace_id == context.workspace_id,
                ProviderSyncRunRow.provider == "ebay",
            )
            .order_by(desc(ProviderSyncRunRow.started_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    latest_mail = (
        await context.session.execute(
            select(MailImportRow)
            .where(MailImportRow.workspace_id == context.workspace_id)
            .order_by(desc(MailImportRow.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    recent_worker_rows = list(
        (
            await context.session.execute(
                select(WorkerRow).where(
                    WorkerRow.workspace_id == context.workspace_id,
                    WorkerRow.enabled.is_(True),
                    WorkerRow.last_heartbeat_at >= checked_at - timedelta(minutes=10),
                )
            )
        ).scalars()
    )
    active_workers = len(recent_worker_rows)
    ollama_workers = sum(1 for worker in recent_worker_rows if "text-small" in worker.capabilities)
    settings = get_settings()
    storage_path = Path(settings.image_storage_dir)

    def storage_is_writable() -> bool:
        storage_parent = storage_path if storage_path.exists() else storage_path.parent
        return storage_parent.exists() and os.access(storage_parent, os.W_OK)

    storage_ok = await asyncio.to_thread(storage_is_writable)

    def provider_health(provider: str, recent_status: str | None) -> ComponentHealth:
        configuration = configuration_by_provider.get(provider)
        if configuration is None or not configuration.enabled:
            return ComponentHealth(status="disabled", detail="Provider ist nicht aktiviert.", checked_at=checked_at)
        if recent_status == "FAILED":
            return ComponentHealth(
                status="degraded", detail="Der letzte Lauf ist fehlgeschlagen.", checked_at=checked_at
            )
        if recent_status:
            return ComponentHealth(status="ok", detail=f"Letzter Lauf: {recent_status}.", checked_at=checked_at)
        return ComponentHealth(
            status="unknown", detail="Aktiviert, aber noch kein Lauf vorhanden.", checked_at=checked_at
        )

    ebay_status = latest_sync.status if latest_sync is not None else None
    mail_status = latest_mail.status if latest_mail is not None else None
    components = {
        "api": ComponentHealth(status="ok", detail="FastAPI beantwortet Anfragen.", checked_at=checked_at),
        "database": ComponentHealth(status="ok", detail="Datenbankabfrage erfolgreich.", checked_at=checked_at),
        "supabase": ComponentHealth(
            status="ok" if settings.auth_mode == "supabase" else "disabled",
            detail="Supabase-Authentifizierung aktiv."
            if settings.auth_mode == "supabase"
            else "Lokaler Entwicklungsmodus.",
            checked_at=checked_at,
        ),
        "ebay": provider_health("ebay", ebay_status),
        "emailImporter": provider_health("kleinanzeigenEmail", mail_status),
        "worker": ComponentHealth(
            status="ok" if active_workers else "degraded",
            detail=f"{active_workers or 0} Worker mit aktuellem Heartbeat.",
            checked_at=checked_at,
        ),
        "ollama": ComponentHealth(
            status="ok" if ollama_workers else "disabled",
            detail=f"{ollama_workers or 0} aktiver Textmodell-Worker.",
            checked_at=checked_at,
        ),
        "storage": ComponentHealth(
            status="ok" if storage_ok else "degraded",
            detail="Privater Bildspeicher ist beschreibbar." if storage_ok else "Bildspeicher ist nicht beschreibbar.",
            checked_at=checked_at,
        ),
    }
    degraded = any(component.status == "degraded" for component in components.values())
    return SystemStatusResponse(
        status="degraded" if degraded else "ok",
        listings=listing_count or 0,
        open_jobs=open_jobs or 0,
        workers=workers or 0,
        components=components,
    )


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
    await context.session.flush()
    record_audit_event(context, "extensionPairing.created", "extensionPairing", row.id)
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
    record_audit_event(context, "extensionPairing.revoked", "extensionPairing", pairing.id)
    await context.session.commit()


def _extension_connection_response(row: ExtensionPairingRow) -> ExtensionConnectionResponse:
    return ExtensionConnectionResponse(
        id=row.id,
        display_name=row.display_name,
        created_at=row.created_at,
    )


@router.get("/extension/connections", response_model=list[ExtensionConnectionResponse])
async def extension_connections(context: Context) -> list[ExtensionConnectionResponse]:
    rows = (
        await context.session.execute(
            select(ExtensionPairingRow)
            .where(
                ExtensionPairingRow.workspace_id == context.workspace_id,
                ExtensionPairingRow.expires_at.is_(None),
                ExtensionPairingRow.revoked_at.is_(None),
            )
            .order_by(desc(ExtensionPairingRow.created_at))
        )
    ).scalars()
    return [_extension_connection_response(row) for row in rows]


@router.post("/extension/connections", response_model=ExtensionConnectionCreatedResponse, status_code=201)
async def create_extension_connection(
    payload: ExtensionConnectionCreate,
    context: Context,
) -> ExtensionConnectionCreatedResponse:
    token = secrets.token_urlsafe(48)
    row = ExtensionPairingRow(
        workspace_id=context.workspace_id,
        created_by_user_id=context.identity.user_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        display_name=payload.display_name,
        expires_at=None,
    )
    context.session.add(row)
    await context.session.flush()
    record_audit_event(
        context,
        "extensionConnection.created",
        "extensionConnection",
        row.id,
        {"displayName": row.display_name},
    )
    await context.session.commit()
    return ExtensionConnectionCreatedResponse(
        **_extension_connection_response(row).model_dump(),
        token=token,
    )


@router.delete("/extension/connections/{connection_id}", status_code=204)
async def revoke_extension_connection(connection_id: UUID, context: Context) -> None:
    connection = (
        await context.session.execute(
            select(ExtensionPairingRow).where(
                ExtensionPairingRow.id == connection_id,
                ExtensionPairingRow.workspace_id == context.workspace_id,
                ExtensionPairingRow.expires_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=404, detail="extension connection not found")
    connection.revoked_at = datetime.now(UTC)
    record_audit_event(
        context,
        "extensionConnection.revoked",
        "extensionConnection",
        connection.id,
        {"displayName": connection.display_name},
    )
    await context.session.commit()


@router.post("/erp/exports/{listing_id}", response_model=ErpExportResponse)
async def mock_erp_export(listing_id: UUID, context: Context) -> ErpExportResponse:
    try:
        purchase_payload = await MockErpIntegrationAdapter(
            context.session,
            context.workspace_id,
        ).export_listing_as_purchase(listing_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="listing not found") from exc
    record_audit_event(context, "erp.purchaseExported", "listing", listing_id, {"adapter": "mock"})
    await context.session.commit()
    return ErpExportResponse(
        listing_id=listing_id,
        purchase_payload=purchase_payload,
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


def _provider_configuration_response(row: ProviderConfigurationRow) -> ProviderConfigurationResponse:
    return ProviderConfigurationResponse(
        id=row.id,
        provider=row.provider,
        enabled=row.enabled,
        settings=row.settings_json,
        secret_reference=row.secret_reference,
        last_health_status=row.last_health_status,
        last_health_checked_at=row.last_health_checked_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/provider-configurations", response_model=list[ProviderConfigurationResponse])
async def provider_configurations(context: Context) -> list[ProviderConfigurationResponse]:
    rows = (
        await context.session.execute(
            select(ProviderConfigurationRow)
            .where(ProviderConfigurationRow.workspace_id == context.workspace_id)
            .order_by(ProviderConfigurationRow.provider)
        )
    ).scalars()
    return [_provider_configuration_response(row) for row in rows]


@router.put("/provider-configurations/{provider}", response_model=ProviderConfigurationResponse)
async def upsert_provider_configuration(
    provider: str,
    payload: ProviderConfigurationUpsert,
    context: Context,
) -> ProviderConfigurationResponse:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=422, detail="unsupported provider")
    row = (
        await context.session.execute(
            select(ProviderConfigurationRow).where(
                ProviderConfigurationRow.workspace_id == context.workspace_id,
                ProviderConfigurationRow.provider == provider,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = ProviderConfigurationRow(
            workspace_id=context.workspace_id,
            provider=provider,
            enabled=payload.enabled,
            settings_json=payload.settings,
            secret_reference=payload.secret_reference,
        )
        context.session.add(row)
    else:
        row.enabled = payload.enabled
        row.settings_json = payload.settings
        row.secret_reference = payload.secret_reference
    await context.session.flush()
    record_audit_event(
        context,
        "providerConfiguration.updated",
        "providerConfiguration",
        row.id,
        {"provider": provider, "enabled": payload.enabled},
    )
    await context.session.commit()
    await context.session.refresh(row)
    return _provider_configuration_response(row)


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
