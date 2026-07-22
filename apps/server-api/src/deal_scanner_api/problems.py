from __future__ import annotations

from collections.abc import Sequence

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger("deal_scanner_api.errors")


def _problem(
    request: Request,
    status: int,
    title: str,
    detail: str,
    problem_type: str = "about:blank",
    errors: Sequence[object] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": problem_type,
            "title": title,
            "status": status,
            "detail": detail,
            "instance": str(request.url.path),
            **({"errors": list(errors)} if errors else {}),
        },
    )


def install_problem_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        logger.warning("http_error", path=request.url.path, status_code=exc.status_code)
        return _problem(request, exc.status_code, "Request failed", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception(request: Request, exc: RequestValidationError) -> JSONResponse:
        safe_errors: list[dict[str, object]] = []
        for raw_error in exc.errors():
            error = dict(raw_error)
            context = error.get("ctx")
            if isinstance(context, dict):
                error["ctx"] = {str(key): str(value) for key, value in context.items()}
            raw_input = error.get("input")
            if isinstance(raw_input, bytes):
                error["input"] = "<binary input>"
            safe_errors.append(error)
        return _problem(
            request,
            422,
            "Validation failed",
            "Request validation failed",
            errors=safe_errors,
        )

    @app.exception_handler(Exception)
    async def unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_api_error", path=request.url.path, error_type=type(exc).__name__)
        return _problem(
            request,
            500,
            "Internal server error",
            "The request could not be completed.",
            "https://deal-scanner.local/problems/internal",
        )
