from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import NotificationDeliveryRow, NotificationRow
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
        del title, body
        ntfy_url = get_settings().ntfy_url
        if not ntfy_url:
            return False
        self.session.add(
            NotificationDeliveryRow(
                workspace_id=self.workspace_id,
                notification_id=notification_id,
                channel=self.channel,
                status="PENDING",
                attempts=0,
            )
        )
        return True


async def dispatch_ntfy_notifications(session: AsyncSession, workspace_id: UUID) -> int:
    ntfy_url = get_settings().ntfy_url
    if not ntfy_url:
        return 0
    rows = (
        await session.execute(
            select(NotificationDeliveryRow, NotificationRow)
            .join(NotificationRow, NotificationDeliveryRow.notification_id == NotificationRow.id)
            .where(
                NotificationDeliveryRow.workspace_id == workspace_id,
                NotificationRow.workspace_id == workspace_id,
                NotificationDeliveryRow.channel == "ntfy",
                NotificationDeliveryRow.status.in_(["PENDING", "FAILED"]),
                NotificationDeliveryRow.attempts < 3,
            )
            .order_by(NotificationRow.created_at)
            .limit(100)
            .with_for_update(of=NotificationDeliveryRow, skip_locked=True)
        )
    ).all()
    groups = [rows] if len(rows) > 5 else [[row] for row in rows]
    delivered = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for group in groups:
            titles = [
                str(notification.reason.get("title", "Angebot"))[:500]
                + ("\n" + str(notification.reason["url"]) if notification.reason.get("url") else "")
                for _, notification in group
            ]
            title = f"{len(group)} neue Deal-Scanner-Angebote" if len(group) > 1 else "Deal Scanner"
            body = "\n".join(titles)
            for delivery, _ in group:
                delivery.attempts += 1
            try:
                response = await client.post(
                    ntfy_url,
                    content=body,
                    headers={"Title": title, "Tags": "moneybag"},
                )
                response.raise_for_status()
                for delivery, _ in group:
                    delivery.status = "DELIVERED"
                    delivery.last_error = None
                    delivery.delivered_at = datetime.now(UTC)
                    delivered += 1
            except httpx.HTTPError as exc:
                for delivery, _ in group:
                    delivery.status = "FAILED"
                    delivery.last_error = str(exc)[:1000]
    await session.commit()
    return delivered
