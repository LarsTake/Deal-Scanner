from __future__ import annotations

import asyncio
import imaplib
import os
import ssl
from uuid import UUID

import httpx
import psycopg
import pytest
import truststore
from deal_scanner_core.models import TextAnalysisRequest
from deal_scanner_ebay import EbayProvider, EbaySettings
from deal_scanner_worker.ollama import OllamaProvider

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


def system_ssl_context() -> ssl.SSLContext:
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


@pytest.mark.asyncio
async def test_supabase_auth_health_is_reachable() -> None:
    url = required("DEAL_SCANNER_SUPABASE_URL").rstrip("/")
    publishable_key = os.getenv("DEAL_SCANNER_SUPABASE_PUBLISHABLE_KEY", "").strip()
    headers = {"apikey": publishable_key} if publishable_key else {}
    async with httpx.AsyncClient(timeout=15, verify=system_ssl_context()) as client:
        response = await client.get(f"{url}/auth/v1/health", headers=headers)
    assert response.status_code == 200


def test_supabase_schema_rls_and_private_buckets_read_only() -> None:
    database_url = required("DEAL_SCANNER_SUPABASE_DB_URL")
    expected_tables = {
        "listings",
        "listing_snapshots",
        "analysis_jobs",
        "analysis_results",
        "audit_events",
    }
    with psycopg.connect(database_url, connect_timeout=15) as connection:
        rows = connection.execute(
            """
            select c.relname, c.relrowsecurity
            from pg_catalog.pg_class c
            join pg_catalog.pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'deal_scanner' and c.relname = any(%s)
            """,
            (list(expected_tables),),
        ).fetchall()
        buckets = connection.execute(
            """
            select id, public from storage.buckets
            where id in ('listing-images', 'mail-archive')
            """
        ).fetchall()

    assert {str(name) for name, _ in rows} == expected_tables
    assert all(bool(rls_enabled) for _, rls_enabled in rows)
    assert {(str(bucket_id), bool(public)) for bucket_id, public in buckets} == {
        ("listing-images", False),
        ("mail-archive", False),
    }


@pytest.mark.parametrize("environment", ["sandbox", "production"])
@pytest.mark.asyncio
async def test_ebay_oauth_health_read_only(environment: str) -> None:
    prefix = f"DEAL_SCANNER_EBAY_{environment.upper()}"
    async with httpx.AsyncClient(timeout=20, verify=system_ssl_context()) as client:
        provider = EbayProvider(
            EbaySettings(
                client_id=required(f"{prefix}_CLIENT_ID"),
                client_secret=required(f"{prefix}_CLIENT_SECRET"),
                environment=environment,
            ),
            client=client,
        )
        status = await provider.health_check()
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
    models = {
        value
        for name in (
            "DEAL_SCANNER_OLLAMA_EXTRACTION_MODEL",
            "DEAL_SCANNER_OLLAMA_REASONING_MODEL",
            "DEAL_SCANNER_OLLAMA_VISION_MODEL",
            "DEAL_SCANNER_OLLAMA_EMBEDDING_MODEL",
            "DEAL_SCANNER_OLLAMA_TEXT_MODEL",
        )
        if (value := os.getenv(name))
    }
    if not models:
        pytest.skip("no Ollama model roles configured")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(f"{url}/api/tags")
    response.raise_for_status()
    names = {item.get("name") for item in response.json().get("models", [])}
    for model in models:
        assert model in names or any(isinstance(name, str) and name.startswith(f"{model}:") for name in names)


@pytest.mark.asyncio
async def test_ollama_structured_inference_contract() -> None:
    if os.getenv("DEAL_SCANNER_RUN_OLLAMA_INFERENCE_TESTS") != "1":
        pytest.skip("set DEAL_SCANNER_RUN_OLLAMA_INFERENCE_TESTS=1 for the compute-intensive model call")
    url = required("DEAL_SCANNER_OLLAMA_URL").rstrip("/")
    model = os.getenv("DEAL_SCANNER_OLLAMA_EXTRACTION_MODEL") or required("DEAL_SCANNER_OLLAMA_TEXT_MODEL")
    async with httpx.AsyncClient() as client:
        result = await OllamaProvider(
            url,
            model,
            client,
            reasoning_model=os.getenv("DEAL_SCANNER_OLLAMA_REASONING_MODEL", ""),
        ).analyze_text(
            TextAnalysisRequest(
                listing_id=UUID("00000000-0000-4000-8000-000000000999"),
                title="Gaming PC mit RTX 4070S und Ryzen 7 5800X3D",
                description="32 GB RAM, 1 TB SSD, Rechnung und Abholung mit Funktionstest.",
                category_profile="computer",
            )
        )
    assert result.category == "computer"
    assert result.schema_version == "1.0.0"
    assert 0 <= result.overall_confidence <= 1
