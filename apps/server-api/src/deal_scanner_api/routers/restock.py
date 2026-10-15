from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from deal_scanner_core.models import CamelModel
from fastapi import APIRouter
from pydantic import Field, HttpUrl, model_validator
from sqlalchemy import select

from ..context import Context
from ..db_models import NotificationRow, ProviderConfigurationRow
from ..notification_service import DesktopNotificationAdapter, NtfyNotificationAdapter
from ..restock_service import parse_availability, validate_shop_url

router = APIRouter(prefix="/restock", tags=["restock"])


class RestockConfiguration(CamelModel):
    urls: list[HttpUrl] = Field(default_factory=list, max_length=20)
    enabled: bool = False
    desktop_enabled: bool = True
    ntfy_enabled: bool = False
    notify_on_first_run: bool = False
    interval_seconds: int = Field(default=300, ge=60, le=86400)

    @model_validator(mode="after")
    def supported_shops(self) -> RestockConfiguration:
        for url in self.urls:
            validate_shop_url(str(url))
        return self


async def configuration_row(context: Context, *, lock: bool = False) -> ProviderConfigurationRow | None:
    query = select(ProviderConfigurationRow).where(
        ProviderConfigurationRow.workspace_id == context.workspace_id,
        ProviderConfigurationRow.provider == "shopRestock",
    )
    if lock:
        query = query.with_for_update()
    row: ProviderConfigurationRow | None = (await context.session.execute(query)).scalar_one_or_none()
    return row


@router.get("", response_model=RestockConfiguration)
async def configuration(context: Context) -> RestockConfiguration:
    row = await configuration_row(context)
    return RestockConfiguration.model_validate(
        {
            **{key: value for key, value in (row.settings_json if row else {}).items() if key != "states"},
            "enabled": row.enabled if row else False,
        }
    )


@router.put("", response_model=RestockConfiguration)
async def save_configuration(payload: RestockConfiguration, context: Context) -> RestockConfiguration:
    row = await configuration_row(context, lock=True)
    states = row.settings_json.get("states", {}) if row else {}
    urls = {str(url) for url in payload.urls}
    settings = payload.model_dump(mode="json", by_alias=False, exclude={"enabled"})
    settings["states"] = {url: state for url, state in states.items() if url in urls}
    if row is None:
        row = ProviderConfigurationRow(
            workspace_id=context.workspace_id, provider="shopRestock", enabled=payload.enabled, settings_json=settings
        )
        context.session.add(row)
    else:
        row.enabled = payload.enabled
        row.settings_json = settings
    await context.session.commit()
    return payload


@router.post("/check")
async def check_restock(context: Context) -> dict[str, Any]:
    row = await configuration_row(context, lock=True)
    if row is None or not row.enabled:
        return {"checked": 0, "notifications": 0, "states": {}}
    settings = row.settings_json
    states = dict(settings.get("states", {}))
    now = datetime.now(UTC)
    checked = notifications = 0
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as client:
        for url in settings.get("urls", []):
            if checked >= 5:
                break
            validate_shop_url(url)
            previous = states.get(url, {})
            if previous.get("checkedAt"):
                checked_at = datetime.fromisoformat(previous["checkedAt"])
                if (now - checked_at).total_seconds() < settings.get("interval_seconds", 300):
                    continue
            checked += 1
            try:
                content = bytearray()
                async with client.stream(
                    "GET", url, headers={"User-Agent": "DealScanner/0.1 (restock monitoring)"}
                ) as response:
                    response.raise_for_status()
                    if response.is_redirect:
                        raise ValueError("Shop redirect requires a direct product URL")
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 4 * 1024 * 1024:
                            raise ValueError("Shop page exceeds size limit")
                available, title = parse_availability(content.decode("utf-8", errors="replace"), url)
                state = {
                    "available": available,
                    "title": title,
                    "checkedAt": now.isoformat(),
                    "lastKnownAvailable": previous.get("lastKnownAvailable") if available is None else available,
                }
                transition = available is True and (
                    previous.get("lastKnownAvailable") is False
                    or (not previous and settings.get("notify_on_first_run", False))
                )
                if transition:
                    notice = NotificationRow(
                        workspace_id=context.workspace_id,
                        reason={"type": "restock", "title": title, "url": url, "body": "Wieder verfügbar"},
                    )
                    context.session.add(notice)
                    await context.session.flush()
                    if settings.get("desktop_enabled", True):
                        await DesktopNotificationAdapter(context.session, context.workspace_id).deliver(
                            notice.id, title, url
                        )
                    if settings.get("ntfy_enabled", False):
                        await NtfyNotificationAdapter(context.session, context.workspace_id).deliver(
                            notice.id, title, url
                        )
                    notifications += 1
                states[url] = state
            except (httpx.HTTPError, ValueError) as error:
                states[url] = {
                    **previous,
                    "available": None,
                    "checkedAt": now.isoformat(),
                    "error": f"{type(error).__name__}: {error}"[:1000],
                }
    row.settings_json = {**settings, "states": states}
    row.last_health_checked_at = now
    row.last_health_status = "degraded" if any(state.get("available") is None for state in states.values()) else "ok"
    await context.session.commit()
    return {"checked": checked, "notifications": notifications, "states": states}
