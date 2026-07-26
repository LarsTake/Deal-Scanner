from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy import text

from ..database import session_factory
from ..ebay_account_deletion import (
    EbayDeletionEvent,
    EbayNotificationConfigurationError,
    EbayNotificationUpstreamError,
    EbayNotificationVerifier,
    challenge_response,
    process_account_deletion,
)
from ..settings import Settings, get_settings

router = APIRouter(tags=["eBay compliance"])
ACCOUNT_DELETION_PATH = "/webhooks/ebay/account-deletion"
MAX_NOTIFICATION_BYTES = 64 * 1024


@lru_cache
def get_ebay_notification_verifier() -> EbayNotificationVerifier:
    return EbayNotificationVerifier(get_settings())


Verifier = Annotated[EbayNotificationVerifier, Depends(get_ebay_notification_verifier)]


@router.get(ACCOUNT_DELETION_PATH, include_in_schema=False)
async def validate_account_deletion_endpoint(
    challenge_code: Annotated[str, Query(min_length=1, max_length=512)],
) -> dict[str, str]:
    settings = _configured_settings()
    return {
        "challengeResponse": challenge_response(
            challenge_code,
            settings.ebay_deletion_verification_token,
            settings.ebay_deletion_endpoint_url,
        )
    }


@router.post(ACCOUNT_DELETION_PATH, status_code=204, include_in_schema=False)
async def receive_account_deletion(
    request: Request,
    verifier: Verifier,
    x_ebay_signature: Annotated[str | None, Header(alias="X-EBAY-SIGNATURE")] = None,
) -> Response:
    settings = _configured_settings()
    raw_body = await request.body()
    if len(raw_body) > MAX_NOTIFICATION_BYTES:
        raise HTTPException(status_code=413, detail="notification body is too large")
    try:
        payload: Any = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="notification body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="notification body must be a JSON object")

    try:
        signature_valid = await verifier.verify(payload, x_ebay_signature)
    except EbayNotificationConfigurationError as exc:
        raise HTTPException(status_code=503, detail="eBay notification verification is not configured") from exc
    except EbayNotificationUpstreamError as exc:
        raise HTTPException(
            status_code=503,
            detail="eBay notification verification is temporarily unavailable",
        ) from exc
    if not signature_valid:
        raise HTTPException(status_code=412, detail="invalid eBay notification signature")

    try:
        event = EbayDeletionEvent.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail="invalid account deletion notification") from exc

    async with session_factory() as session:
        if settings.database_url.startswith("postgresql"):
            await session.execute(text("RESET ROLE"))
            await session.execute(text("SET LOCAL search_path TO deal_scanner, public"))
            await session.execute(text("SET LOCAL deal_scanner.account_deletion = 'on'"))
        await process_account_deletion(session, event, settings)
    return Response(status_code=204)


def _configured_settings() -> Settings:
    settings = get_settings()
    if not settings.ebay_deletion_endpoint_url or not settings.ebay_deletion_verification_token:
        raise HTTPException(status_code=503, detail="eBay account deletion endpoint is not configured")
    return settings
