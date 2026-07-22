from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import NotificationDeliveryRow
from .settings import get_settings


class DesktopNotificationAdapter:
    channel = "desktop"

    def __init__(self, session: AsyncSession, workspace_id: UUID) -> None:
        self.session = session
        self.workspace_id = workspace_id

    async def deliver(self, notification_id: UUID, title: str, body: str) -> bool:
        del title, body
        self.session.add(
            NotificationDeliveryRow(
                workspace_id=self.workspace_id,
                notification_id=notification_id,
                channel=self.channel,
                status="PENDING",
            )
        )
        return True


class NtfyNotificationAdapter:
    channel = "ntfy"

    def __init__(self, session: AsyncSession, workspace_id: UUID) -> None:
        self.session = session
        self.workspace_id = workspace_id

    async def deliver(self, notification_id: UUID, title: str, body: str) -> bool:
        ntfy_url = get_settings().ntfy_url
        if not ntfy_url:
            return False
        delivery = NotificationDeliveryRow(
            workspace_id=self.workspace_id,
            notification_id=notification_id,
            channel=self.channel,
            status="PENDING",
            attempts=1,
        )
        self.session.add(delivery)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    ntfy_url,
                    content=body,
                    headers={"Title": title, "Tags": "moneybag"},
                )
                response.raise_for_status()
            delivery.status = "DELIVERED"
            delivery.delivered_at = datetime.now(UTC)
            return True
        except httpx.HTTPError as exc:
            delivery.status = "FAILED"
            delivery.last_error = str(exc)[:1000]
            return False
