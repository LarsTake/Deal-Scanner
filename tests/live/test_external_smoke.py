from __future__ import annotations

import asyncio
import imaplib
import os

import httpx
import pytest
from deal_scanner_ebay import EbayProvider, EbaySettings

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("DEAL_SCANNER_RUN_LIVE_TESTS") != "1",
        reason="set DEAL_SCANNER_RUN_LIVE_TESTS=1 with explicit read-only credentials",
    ),
]


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        pytest.skip(f"{name} is not configured")
    return value


@pytest.mark.asyncio
async def test_supabase_auth_health_is_reachable() -> None:
    url = required("DEAL_SCANNER_SUPABASE_URL").rstrip("/")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{url}/auth/v1/health")
    assert response.status_code == 200


@pytest.mark.parametrize("environment", ["sandbox", "production"])
@pytest.mark.asyncio
async def test_ebay_oauth_health_read_only(environment: str) -> None:
    prefix = f"DEAL_SCANNER_EBAY_{environment.upper()}"
    provider = EbayProvider(
        EbaySettings(
            client_id=required(f"{prefix}_CLIENT_ID"),
            client_secret=required(f"{prefix}_CLIENT_SECRET"),
            environment=environment,
        )
    )
    try:
        status = await provider.health_check()
    finally:
        await provider.close()
    assert status["available"] is True


def test_imap_login_and_noop_read_only() -> None:
    host = required("DEAL_SCANNER_IMAP_HOST")
    username = required("DEAL_SCANNER_IMAP_USERNAME")
    password = required("DEAL_SCANNER_IMAP_PASSWORD")

    def check() -> str:
        with imaplib.IMAP4_SSL(host, timeout=15) as connection:
            connection.login(username, password)
            status, _ = connection.noop()
            return status

    assert asyncio.run(asyncio.to_thread(check)) == "OK"


@pytest.mark.asyncio
async def test_ollama_model_is_available_read_only() -> None:
    url = required("DEAL_SCANNER_OLLAMA_URL").rstrip("/")
    model = required("DEAL_SCANNER_OLLAMA_TEXT_MODEL")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{url}/api/tags")
    response.raise_for_status()
    names = {item.get("name") for item in response.json().get("models", [])}
    assert model in names or any(isinstance(name, str) and name.startswith(f"{model}:") for name in names)
