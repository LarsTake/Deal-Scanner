from __future__ import annotations

import asyncio
import selectors
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import structlog
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection

from .database import engine
from .db_models import Base
from .problems import install_problem_handlers
from .rate_limit import FixedWindowRateLimiter
from .routers import (
    auth,
    ebay_notifications,
    health,
    images,
    imports,
    listings,
    market,
    search_profiles,
    system,
    workers,
)
from .schemas import ProblemDetails
from .settings import get_settings

settings = get_settings()
logger = structlog.get_logger("deal_scanner_api")
rate_limiter = FixedWindowRateLimiter(
    settings.rate_limit_per_minute,
    settings.sensitive_rate_limit_per_minute,
)


def _listing_column_names(connection: Connection) -> set[str]:
    return {column["name"] for column in inspect(connection).get_columns("listings")}


def _extension_pairing_columns(connection: Connection) -> dict[str, dict[str, object]]:
    return {column["name"]: column for column in inspect(connection).get_columns("extension_pairings")}


async def _migrate_legacy_sqlite_schema(connection: AsyncConnection) -> None:
    """Bring pre-migration desktop databases forward without losing pairings."""
    columns = await connection.run_sync(_extension_pairing_columns)
    expires_at = columns["expires_at"]
    if "display_name" in columns and bool(expires_at["nullable"]):
        return

    # SQLite cannot drop NOT NULL from an existing column. Rebuild the small,
    # local pairing table so permanent browser connections can store no expiry.
    await connection.execute(text("ALTER TABLE extension_pairings RENAME TO extension_pairings_legacy"))
    await connection.execute(
        text(
            """
            CREATE TABLE extension_pairings (
                id CHAR(32) NOT NULL PRIMARY KEY,
                workspace_id CHAR(32) NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
                created_by_user_id CHAR(32) NOT NULL,
                token_hash VARCHAR(64) NOT NULL UNIQUE,
                extension_id VARCHAR(255),
                display_name VARCHAR(120) NOT NULL DEFAULT 'Browser-Erweiterung',
                expires_at DATETIME,
                revoked_at DATETIME,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    legacy_display_name = (
        "display_name"
        if "display_name" in columns
        else "'Browser-Erweiterung'"
    )
    copy_sql = {
        "display_name": """
            INSERT INTO extension_pairings (
                id, workspace_id, created_by_user_id, token_hash, extension_id,
                display_name, expires_at, revoked_at, created_at
            )
            SELECT id, workspace_id, created_by_user_id, token_hash, extension_id,
                   display_name, expires_at, revoked_at, created_at
            FROM extension_pairings_legacy
        """,
        "'Browser-Erweiterung'": """
            INSERT INTO extension_pairings (
                id, workspace_id, created_by_user_id, token_hash, extension_id,
                display_name, expires_at, revoked_at, created_at
            )
            SELECT id, workspace_id, created_by_user_id, token_hash, extension_id,
                   'Browser-Erweiterung', expires_at, revoked_at, created_at
            FROM extension_pairings_legacy
        """,
    }[legacy_display_name]
    await connection.execute(
        text(copy_sql)
    )
    await connection.execute(text("DROP TABLE extension_pairings_legacy"))


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.JSONRenderer(),
    ]
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.auto_create_db:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            if settings.database_url.startswith("sqlite"):
                listing_columns = await connection.run_sync(_listing_column_names)
                if "manual_note" not in listing_columns:
                    await connection.execute(text("ALTER TABLE listings ADD COLUMN manual_note TEXT"))
                await _migrate_legacy_sqlite_schema(connection)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
    responses={
        code: {
            "model": ProblemDetails,
            "content": {"application/problem+json": {}},
        }
        for code in (400, 401, 403, 404, 409, 422, 429, 500)
    },
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "X-EBAY-SIGNATURE",
        "X-Development-User",
        "X-Internal-Key",
        "X-Extension-Pairing",
    ],
)
install_problem_handlers(app)


@app.middleware("http")
async def security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id", str(uuid4()))[:128]
    started_at = perf_counter()
    allowed, remaining, retry_after = await rate_limiter.check(request)
    if not allowed and request.url.path.startswith("/api/"):
        response: Response = JSONResponse(
            status_code=429,
            media_type="application/problem+json",
            content={
                "type": "https://deal-scanner.local/problems/rate-limit",
                "title": "Rate limit exceeded",
                "status": 429,
                "detail": "Too many requests; retry later.",
                "instance": request.url.path,
            },
            headers={"Retry-After": str(retry_after)},
        )
    else:
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    duration_ms = round((perf_counter() - started_at) * 1000, 2)
    logger.info(
        "http_request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


for module in (auth, ebay_notifications, health, images, imports, listings, market, search_profiles, system, workers):
    app.include_router(module.router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"name": settings.api_title, "docs": "/api/docs"}


def run() -> None:
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                uvicorn.Server(
                    uvicorn.Config("deal_scanner_api.main:app", host="127.0.0.1", port=8000)
                ).serve()
            )
        finally:
            loop.close()
        return
    uvicorn.run("deal_scanner_api.main:app", host="127.0.0.1", port=8000)
