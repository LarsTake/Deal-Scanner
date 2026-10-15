from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import AuditEventRow, ListingRow, SearchProfileRow


async def archive_expired_listings(session: AsyncSession, workspace_id: UUID) -> int:
    now = datetime.now(UTC)
    profiles = (
        await session.scalars(
            select(SearchProfileRow).where(
                SearchProfileRow.workspace_id == workspace_id,
                SearchProfileRow.enabled.is_(True),
            )
        )
    ).all()
    archived = 0
    for profile in profiles:
        days = profile.notification_settings.get("archive_after_days", 14)
        if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 3650:
            continue
        rows = (
            await session.scalars(
                select(ListingRow)
                .where(
                    ListingRow.workspace_id == workspace_id,
                    ListingRow.search_profile_id == profile.id,
                    ListingRow.is_hidden.is_(False),
                    ListingRow.is_favorite.is_(False),
                    ListingRow.first_seen_at < now - timedelta(days=days),
                    ListingRow.last_seen_at < now - timedelta(hours=48),
                )
                .limit(1000)
            )
        ).all()
        for listing in rows:
            listing.is_hidden = True
            listing.removed_at = now  # Non-null identifies recoverable automatic archival.
            listing.version += 1
            session.add(
                AuditEventRow(
                    workspace_id=workspace_id,
                    actor_user_id=None,
                    event_type="listing.autoArchived",
                    aggregate_type="listing",
                    aggregate_id=listing.id,
                    payload={"archiveAfterDays": days, "reason": "age"},
                )
            )
            archived += 1
    await session.commit()
    return archived
