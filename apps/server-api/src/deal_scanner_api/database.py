from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        try:
            if settings.database_url.startswith("postgresql"):
                # The login role may own the database. Every request is forced
                # through the non-bypass role before any domain query executes.
                await session.execute(text(f'SET ROLE "{settings.database_role}"'))
                await session.execute(text("select pg_catalog.set_config('search_path', 'deal_scanner,public', false)"))
            yield session
        finally:
            if session.in_transaction():
                await session.rollback()
            if settings.database_url.startswith("postgresql"):
                # Claims are session scoped so commits inside use cases do not
                # accidentally disable RLS. Always clear them before pooling.
                await session.execute(text("select pg_catalog.set_config('request.jwt.claim.sub', '', false)"))
                await session.execute(text("select pg_catalog.set_config('search_path', '\"$user\", public', false)"))
                await session.execute(text("RESET ROLE"))
                await session.commit()
