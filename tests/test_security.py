from __future__ import annotations

from deal_scanner_api.rate_limit import FixedWindowRateLimiter
from deal_scanner_api.settings import Settings
from starlette.requests import Request


def _request(path: str, identity: str = "test-user") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"x-development-user", identity.encode())],
            "client": ("127.0.0.1", 12345),
            "server": ("test", 80),
            "scheme": "http",
        }
    )


async def test_sensitive_rate_limit_is_independent_and_returns_retry_delay() -> None:
    limiter = FixedWindowRateLimiter(default_limit=3, sensitive_limit=2, window_seconds=60)
    assert (await limiter.check(_request("/api/v1/imports/manual")))[0] is True
    allowed, remaining, _ = await limiter.check(_request("/api/v1/imports/manual"))
    assert allowed is True
    assert remaining == 0
    allowed, remaining, retry_after = await limiter.check(_request("/api/v1/imports/manual"))
    assert allowed is False
    assert remaining == 0
    assert retry_after >= 1

    # A sensitive bucket does not consume the normal API budget.
    assert (await limiter.check(_request("/api/v1/listings")))[0] is True


def test_local_angular_origins_are_allowed_by_default() -> None:
    settings = Settings(_env_file=None)
    assert "http://127.0.0.1:4200" in settings.allowed_origins
    assert "http://localhost:4200" in settings.allowed_origins
