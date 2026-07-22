from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from deal_scanner_core.models import ImageOcrResult, TextAnalysisResult
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select

from ..context import Context
from ..db_models import (
    AnalysisJobRow,
    AnalysisResultRow,
    ListingImageRow,
    ListingRow,
    ListingSnapshotRow,
    WorkerRow,
)
from ..market_service import evaluate_listing_record
from ..product_service import persist_listing_products
from ..schemas import (
    JobClaimRequest,
    JobCompleteRequest,
    JobFailRequest,
    JobResponse,
    LeaseRenewRequest,
    WorkerHeartbeat,
    WorkerRegistration,
    WorkerResponse,
)
from ..settings import get_settings

router = APIRouter(tags=["workers"])


def _worker_response(worker: WorkerRow) -> WorkerResponse:
    return WorkerResponse(
        id=worker.id,
        name=worker.name,
        operating_system=worker.operating_system,
        hostname=worker.hostname,
        cpu=worker.cpu,
        ram_gb=worker.ram_gb,
        gpu=worker.gpu,
        vram_gb=worker.vram_gb,
        runtime=worker.runtime,
        capabilities=worker.capabilities,
        installed_models=worker.installed_models,
        last_heartbeat_at=worker.last_heartbeat_at,
        enabled=worker.enabled,
    )


async def _owned_worker(context: Context, worker_id: UUID) -> WorkerRow:
    result = await context.session.execute(
        select(WorkerRow).where(WorkerRow.id == worker_id, WorkerRow.workspace_id == context.workspace_id)
    )
    worker = result.scalar_one_or_none()
    if worker is None or not worker.enabled:
        raise HTTPException(status_code=404, detail="worker not found")
    return worker


def _job_response(job: AnalysisJobRow, payload: dict[str, object] | None = None) -> JobResponse:
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
        payload=payload,
    )


@router.get("/workers", response_model=list[WorkerResponse])
async def list_workers(context: Context) -> list[WorkerResponse]:
    result = await context.session.execute(
        select(WorkerRow).where(WorkerRow.workspace_id == context.workspace_id).order_by(WorkerRow.name)
    )
    return [_worker_response(worker) for worker in result.scalars()]


@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    context: Context,
    job_status: str | None = Query(default=None, alias="status", max_length=20),
) -> list[JobResponse]:
    query = select(AnalysisJobRow).where(AnalysisJobRow.workspace_id == context.workspace_id)
    if job_status is not None:
        query = query.where(AnalysisJobRow.status == job_status)
    result = await context.session.execute(query.order_by(AnalysisJobRow.created_at.desc()).limit(200))
    return [_job_response(job) for job in result.scalars()]


@router.post("/workers/register", response_model=WorkerResponse, status_code=201)
async def register_worker(payload: WorkerRegistration, context: Context) -> WorkerResponse:
    result = await context.session.execute(
        select(WorkerRow).where(
            WorkerRow.workspace_id == context.workspace_id,
            WorkerRow.hostname == payload.hostname,
            WorkerRow.name == payload.name,
        )
    )
    worker = result.scalar_one_or_none()
    values = payload.model_dump(by_alias=False)
    if worker is None:
        worker = WorkerRow(workspace_id=context.workspace_id, **values)
        context.session.add(worker)
    else:
        for field, value in values.items():
            setattr(worker, field, value)
        worker.enabled = True
        worker.last_heartbeat_at = datetime.now(UTC)
    await context.session.commit()
    await context.session.refresh(worker)
    return _worker_response(worker)


@router.post("/workers/{worker_id}/heartbeat", response_model=WorkerResponse)
async def heartbeat(worker_id: UUID, payload: WorkerHeartbeat, context: Context) -> WorkerResponse:
    worker = await _owned_worker(context, worker_id)
    worker.current_load = Decimal(str(payload.current_load))
    if payload.capabilities is not None:
        worker.capabilities = payload.capabilities
    if payload.installed_models is not None:
        worker.installed_models = payload.installed_models
    worker.last_heartbeat_at = datetime.now(UTC)
    await context.session.commit()
    return _worker_response(worker)


@router.post("/jobs/claim", response_model=JobResponse | None)
async def claim_job(payload: JobClaimRequest, context: Context) -> JobResponse | None:
    worker = await _owned_worker(context, payload.worker_id)
    now = datetime.now(UTC)
    settings = get_settings()
    async with context.session.begin_nested():
        result = await context.session.execute(
            select(AnalysisJobRow)
            .where(
                AnalysisJobRow.workspace_id == context.workspace_id,
                AnalysisJobRow.status.in_(["PENDING", "RETRY"]),
                AnalysisJobRow.available_at <= now,
                AnalysisJobRow.required_capability.in_(payload.capabilities),
            )
            .order_by(AnalysisJobRow.priority.desc(), AnalysisJobRow.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        job.status = "LEASED"
        job.assigned_worker_id = worker.id
        job.lease_expires_at = now + timedelta(seconds=settings.default_lease_seconds)
        job.started_at = job.started_at or now
        job.attempts += 1
    await context.session.commit()
    snapshot = await context.session.get(ListingSnapshotRow, job.snapshot_id)
    listing = await context.session.get(ListingRow, job.listing_id)
    job_payload: dict[str, object] | None = None
    if snapshot and listing:
        if job.job_type == "image_ocr":
            image = (
                await context.session.execute(
                    select(ListingImageRow).where(
                        ListingImageRow.workspace_id == context.workspace_id,
                        ListingImageRow.listing_id == listing.id,
                        ListingImageRow.sha256_hash == job.input_hash,
                    )
                )
            ).scalar_one_or_none()
            if image is not None:
                job_payload = {
                    "imageId": str(image.id),
                    "imageAccessPath": f"/api/v1/listing-images/{image.id}/access",
                }
        else:
            job_payload = {
                "title": listing.title,
                "description": listing.description,
                "categoryProfile": listing.category_profile,
                "snapshot": snapshot.raw_data,
            }
    return _job_response(job, job_payload)


async def _leased_job(context: Context, job_id: UUID, worker_id: UUID) -> AnalysisJobRow:
    result = await context.session.execute(
        select(AnalysisJobRow).where(
            AnalysisJobRow.id == job_id,
            AnalysisJobRow.workspace_id == context.workspace_id,
        )
    )
    job = result.scalar_one_or_none()
    now = datetime.now(UTC)
    lease_expires_at = job.lease_expires_at if job is not None else None
    if lease_expires_at is not None and lease_expires_at.tzinfo is None:
        lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
    if (
        job is None
        or job.status != "LEASED"
        or job.assigned_worker_id != worker_id
        or lease_expires_at is None
        or lease_expires_at <= now
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="job lease is not active")
    return job


@router.post("/jobs/{job_id}/renew", response_model=JobResponse)
async def renew_lease(job_id: UUID, payload: LeaseRenewRequest, context: Context) -> JobResponse:
    job = await _leased_job(context, job_id, payload.worker_id)
    job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=get_settings().default_lease_seconds)
    await context.session.commit()
    return _job_response(job)


@router.post("/jobs/{job_id}/complete", response_model=JobResponse)
async def complete_job(job_id: UUID, payload: JobCompleteRequest, context: Context) -> JobResponse:
    job = await _leased_job(context, job_id, payload.worker_id)
    if payload.input_hash != job.input_hash:
        raise HTTPException(status_code=409, detail="job input hash changed")
    text_result: TextAnalysisResult | None = None
    image_result: ImageOcrResult | None = None
    if job.job_type == "text_analysis":
        try:
            text_result = TextAnalysisResult.model_validate(payload.result)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="analysis result violates schema v1") from exc
    elif job.job_type == "image_ocr":
        try:
            image_result = ImageOcrResult.model_validate(payload.result)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="OCR result violates schema v1") from exc
    result = AnalysisResultRow(
        workspace_id=context.workspace_id,
        listing_id=job.listing_id,
        job_id=job.id,
        analysis_type=payload.analysis_type,
        model_name=payload.model_name,
        model_version=payload.model_version,
        prompt_version=payload.prompt_version,
        result_schema_version=payload.result_schema_version,
        input_hash=payload.input_hash,
        result_json=payload.result,
        confidence=Decimal(str(payload.confidence)),
    )
    context.session.add(result)
    await context.session.flush()
    job.status = "COMPLETE"
    job.completed_at = datetime.now(UTC)
    listing = await context.session.get(ListingRow, job.listing_id)
    if listing:
        if text_result is not None:
            listing.analysis_status = "COMPLETE"
            listing.status = "TEXT_ANALYZED"
            await persist_listing_products(
                context.session,
                context.workspace_id,
                listing.id,
                listing.category_profile,
                text_result.products,
                source=f"analysis-result:{result.id}",
                attributes=[attribute.model_dump(by_alias=True) for attribute in text_result.attributes],
            )
            await evaluate_listing_record(
                context.session,
                context.workspace_id,
                listing.id,
                allow_notification=True,
            )
        elif image_result is not None:
            image = (
                await context.session.execute(
                    select(ListingImageRow).where(
                        ListingImageRow.id == image_result.image_id,
                        ListingImageRow.workspace_id == context.workspace_id,
                        ListingImageRow.listing_id == listing.id,
                        ListingImageRow.sha256_hash == job.input_hash,
                    )
                )
            ).scalar_one_or_none()
            if image is None:
                raise HTTPException(status_code=409, detail="OCR image no longer matches the leased job")
            image.analysis_status = "COMPLETE"
            listing.status = "IMAGE_ANALYZED"
    await context.session.commit()
    return _job_response(job)


@router.post("/jobs/{job_id}/fail", response_model=JobResponse)
async def fail_job(job_id: UUID, payload: JobFailRequest, context: Context) -> JobResponse:
    job = await _leased_job(context, job_id, payload.worker_id)
    job.last_error = payload.error
    job.assigned_worker_id = None
    job.lease_expires_at = None
    if job.attempts >= 3:
        job.status = "DEAD"
    else:
        delays = [30, 120, 600]
        job.status = "RETRY"
        job.available_at = datetime.now(UTC) + timedelta(seconds=delays[job.attempts - 1])
    await context.session.commit()
    return _job_response(job)
