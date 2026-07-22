from __future__ import annotations

from uuid import UUID

from deal_scanner_extraction import perceptually_similar
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from ..context import BrowserContext, Context
from ..db_models import AnalysisJobRow, ListingImageRow, ListingRow
from ..image_service import (
    create_image_access,
    download_provider_image,
    resolve_local_image,
    store_private_image,
)
from ..schemas import ImageAccessResponse, ListingImageImport, ListingImageResponse

router = APIRouter(tags=["images"])


def _image_response(
    row: ListingImageRow,
    *,
    exact_duplicate_of: UUID | None = None,
    perceptual_duplicate_of: UUID | None = None,
) -> ListingImageResponse:
    assert row.sha256_hash and row.perceptual_hash and row.width and row.height and row.mime_type
    return ListingImageResponse(
        id=row.id,
        listing_id=row.listing_id,
        source_url=row.source_url,
        sha256_hash=row.sha256_hash,
        perceptual_hash=row.perceptual_hash,
        width=row.width,
        height=row.height,
        mime_type=row.mime_type,
        analysis_status=row.analysis_status,
        exact_duplicate_of=exact_duplicate_of,
        perceptual_duplicate_of=perceptual_duplicate_of,
    )


@router.post("/listings/{listing_id}/images", response_model=list[ListingImageResponse], status_code=201)
async def import_listing_images(
    listing_id: UUID,
    payload: ListingImageImport,
    context: BrowserContext,
) -> list[ListingImageResponse]:
    listing = (
        await context.session.execute(
            select(ListingRow).where(
                ListingRow.id == listing_id,
                ListingRow.workspace_id == context.workspace_id,
            )
        )
    ).scalar_one_or_none()
    if listing is None or listing.current_snapshot_id is None:
        raise HTTPException(status_code=404, detail="listing snapshot not found")

    responses: list[ListingImageResponse] = []
    for source_url in payload.source_urls:
        content, fingerprint = await download_provider_image(str(source_url), listing.platform)
        exact = (
            await context.session.execute(
                select(ListingImageRow)
                .where(
                    ListingImageRow.workspace_id == context.workspace_id,
                    ListingImageRow.sha256_hash == fingerprint.sha256,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        perceptual: ListingImageRow | None = None
        if exact is None:
            candidates = (
                await context.session.execute(
                    select(ListingImageRow).where(
                        ListingImageRow.workspace_id == context.workspace_id,
                        ListingImageRow.perceptual_hash.is_not(None),
                    )
                )
            ).scalars()
            perceptual = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.perceptual_hash
                    and perceptually_similar(fingerprint.perceptual_hash, candidate.perceptual_hash)
                ),
                None,
            )
        storage_path = (
            exact.storage_path
            if exact is not None and exact.storage_path
            else await store_private_image(context.workspace_id, content, fingerprint)
        )
        row = ListingImageRow(
            workspace_id=context.workspace_id,
            listing_id=listing.id,
            source_url=str(source_url),
            storage_path=storage_path,
            sha256_hash=fingerprint.sha256,
            perceptual_hash=fingerprint.perceptual_hash,
            width=fingerprint.width,
            height=fingerprint.height,
            mime_type=fingerprint.mime_type,
            analysis_status="DUPLICATE" if exact is not None else "PENDING",
        )
        context.session.add(row)
        await context.session.flush()
        if exact is None:
            context.session.add(
                AnalysisJobRow(
                    workspace_id=context.workspace_id,
                    listing_id=listing.id,
                    snapshot_id=listing.current_snapshot_id,
                    job_type="image_ocr",
                    required_capability="ocr",
                    input_hash=fingerprint.sha256,
                    priority=5,
                    status="PENDING",
                )
            )
        responses.append(
            _image_response(
                row,
                exact_duplicate_of=exact.id if exact is not None else None,
                perceptual_duplicate_of=perceptual.id if perceptual is not None else None,
            )
        )
    await context.session.commit()
    return responses


@router.get("/listings/{listing_id}/images", response_model=list[ListingImageResponse])
async def listing_images(listing_id: UUID, context: Context) -> list[ListingImageResponse]:
    rows = (
        await context.session.execute(
            select(ListingImageRow)
            .where(
                ListingImageRow.workspace_id == context.workspace_id,
                ListingImageRow.listing_id == listing_id,
            )
            .order_by(ListingImageRow.created_at)
        )
    ).scalars()
    return [_image_response(row) for row in rows]


async def _owned_image(image_id: UUID, context: Context) -> ListingImageRow:
    image = (
        await context.session.execute(
            select(ListingImageRow).where(
                ListingImageRow.id == image_id,
                ListingImageRow.workspace_id == context.workspace_id,
            )
        )
    ).scalar_one_or_none()
    if image is None or image.storage_path is None:
        raise HTTPException(status_code=404, detail="image not found")
    return image


@router.get("/listing-images/{image_id}/access", response_model=ImageAccessResponse)
async def image_access(image_id: UUID, context: Context) -> ImageAccessResponse:
    image = await _owned_image(image_id, context)
    assert image.storage_path is not None
    url, expires_at = await create_image_access(image.storage_path, image.id)
    return ImageAccessResponse(url=url, expires_at=expires_at)


@router.get("/listing-images/{image_id}/content", response_class=FileResponse)
async def image_content(image_id: UUID, context: Context) -> FileResponse:
    image = await _owned_image(image_id, context)
    assert image.storage_path is not None
    target = resolve_local_image(image.storage_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="local image is unavailable")
    return FileResponse(target, media_type=image.mime_type, filename=target.name)
