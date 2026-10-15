from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, SessionTransaction

from .settings import get_settings

settings = get_settings()
if settings.database_url.startswith("sqlite"):
    Path(".data").mkdir(exist_ok=True)

engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@event.listens_for(Session, "after_begin")
def _apply_request_transaction_context(
    session: Session,
    transaction: SessionTransaction,
    connection: Connection,
) -> None:
    """Every new transaction may use a different pooled physical connection."""
    role = session.info.get("deal_scanner_role")
    if role is None or connection.dialect.name != "postgresql":
        return
    # This identifier originates only from the validated server setting.
    if not isinstance(role, str) or not role.replace("_", "").isalnum() or not role.isascii():
        raise ValueError("invalid database role")
    connection.execute(text(f'SET LOCAL ROLE "{role}"'))
    connection.execute(text("select pg_catalog.set_config('search_path', 'deal_scanner,public', true)"))
    connection.execute(
        text("select pg_catalog.set_config('request.jwt.claim.sub', :subject, true)"),
        {"subject": session.info.get("deal_scanner_subject", "")},
    )


async def set_request_subject(session: AsyncSession, user_id: UUID) -> None:
    session.info["deal_scanner_subject"] = str(user_id)
    # Also applies when a pairing resolver already opened this transaction.
    await session.execute(
        text("select pg_catalog.set_config('request.jwt.claim.sub', :subject, true)"),
        {"subject": str(user_id)},
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        if settings.database_url.startswith("postgresql"):
            session.info["deal_scanner_role"] = settings.database_role
        try:
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()
            # SET LOCAL settings expire on commit/rollback, without opening a
            # new cleanup connection (which could mask a failed initial connect).
