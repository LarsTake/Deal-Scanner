from __future__ import annotations

from deal_scanner_api.rate_limit import FixedWindowRateLimiter
from deal_scanner_api.settings import Settings
from deal_scanner_scheduler.main import SchedulerSettings
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


def test_ebay_environment_specific_credentials_do_not_mix_sandbox_and_production() -> None:
    settings = Settings(
        _env_file=None,
        ebay_environment="production",
        ebay_client_id="sandbox-generic-id",
        ebay_client_secret="sandbox-generic-secret",  # noqa: S106
        ebay_production_client_id="production-id",
        ebay_production_client_secret="production-secret",  # noqa: S106
        ebay_deletion_endpoint_url="https://api.example.test/api/v1/webhooks/ebay/account-deletion",
        ebay_deletion_verification_token="production_deletion_token_123456789",  # noqa: S106
    )
    assert settings.ebay_client_id == "production-id"
    assert settings.ebay_client_secret == "production-secret"  # noqa: S105


def test_scheduler_selects_ebay_credentials_for_the_effective_environment() -> None:
    settings = SchedulerSettings(
        _env_file=None,
        ebay_client_id="generic-id",
        ebay_client_secret="generic-secret",  # noqa: S106
        ebay_sandbox_client_id="sandbox-id",
        ebay_sandbox_client_secret="sandbox-secret",  # noqa: S106
        ebay_production_client_id="production-id",
        ebay_production_client_secret="production-secret",  # noqa: S106
    )

    assert settings.ebay_credentials("sandbox") == ("sandbox-id", "sandbox-secret")
    assert settings.ebay_credentials("production") == ("production-id", "production-secret")
