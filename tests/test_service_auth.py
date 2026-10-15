import asyncio
import json
from pathlib import Path

import httpx
import pytest
from deal_scanner_service_auth import ServiceAuthError, ServiceSettings
from deal_scanner_service_auth.auth import ApiAuth


def settings(tmp_path: Path) -> ServiceSettings:
    password_file = tmp_path / "password.txt"
    password_file.write_text("fixture-password", encoding="utf-8")
    return ServiceSettings(
        _env_file=None,
        environment="production",
        service_auth_mode="supabase",
        api_url="http://api:8000",
        supabase_url="https://auth.example.test",
        supabase_publishable_key="fixture-publishable",
        service_email="worker@example.test",
        service_password_file=str(password_file),
    )


def session(number: int) -> httpx.Response:
    return httpx.Response(
        200, json={"access_token": f"access-{number}", "refresh_token": f"refresh-{number}", "expires_in": 3600}
    )


async def test_login_refresh_and_concurrent_requests_share_one_rotation(tmp_path: Path) -> None:
    grants: list[str] = []

    def authenticate(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "auth.example.test"
        assert request.headers["apikey"] == "fixture-publishable"
        grant = request.url.params["grant_type"]
        grants.append(grant)
        body = json.loads(request.content)
        if grant == "password":
            assert body == {"email": "worker@example.test", "password": "fixture-password"}
        else:
            assert body == {"refresh_token": "refresh-1"}
        return session(len(grants))

    auth = ApiAuth(settings(tmp_path), transport=httpx.MockTransport(authenticate))
    tokens: list[str] = []

    def api(request: httpx.Request) -> httpx.Response:
        tokens.append(request.headers["Authorization"])
        return httpx.Response(200)

    async with httpx.AsyncClient(auth=auth, transport=httpx.MockTransport(api)) as client:
        await client.get("http://api:8000/api/v1/workers")
        auth._expires_at = 0
        await asyncio.gather(*(client.get("http://api:8000/api/v1/jobs") for _ in range(8)))
    assert grants == ["password", "refresh_token"]
    assert tokens == ["Bearer access-1"] + ["Bearer access-2"] * 8


async def test_401_refreshes_and_retries_only_once_with_same_body(tmp_path: Path) -> None:
    auth_calls = 0

    def authenticate(request: httpx.Request) -> httpx.Response:
        nonlocal auth_calls
        auth_calls += 1
        return session(auth_calls)

    requests: list[httpx.Request] = []

    def api(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {"workerId": "fixture"}
        requests.append(request)
        return httpx.Response(401)

    auth = ApiAuth(settings(tmp_path), transport=httpx.MockTransport(authenticate))
    async with httpx.AsyncClient(auth=auth, transport=httpx.MockTransport(api)) as client:
        response = await client.post("http://api:8000/api/v1/jobs/claim", json={"workerId": "fixture"})
    assert response.status_code == 401
    assert auth_calls == 2 and len(requests) == 2


async def test_revoked_refresh_blocks_without_password_relogin_or_secret_logs(tmp_path: Path) -> None:
    calls = 0

    def authenticate(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return session(1) if calls == 1 else httpx.Response(400, text="sensitive server payload")

    auth = ApiAuth(settings(tmp_path), transport=httpx.MockTransport(authenticate))
    async with httpx.AsyncClient(auth=auth, transport=httpx.MockTransport(lambda _: httpx.Response(200))) as client:
        await client.get("http://api:8000/api/v1/workers")
        auth._expires_at = 0
        with pytest.raises(ServiceAuthError) as error:
            await client.get("http://api:8000/api/v1/workers")
        assert str(error.value) == "service_session_or_credentials_rejected"
        with pytest.raises(ServiceAuthError, match="restart_after_review"):
            await client.get("http://api:8000/api/v1/workers")
    assert calls == 2


async def test_temporary_auth_outage_retries_without_leaking_response(tmp_path: Path) -> None:
    calls = 0

    def authenticate(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, text="do not log this") if calls == 1 else session(1)

    auth = ApiAuth(settings(tmp_path), transport=httpx.MockTransport(authenticate))
    async with httpx.AsyncClient(auth=auth, transport=httpx.MockTransport(lambda _: httpx.Response(200))) as client:
        with pytest.raises(ServiceAuthError, match="temporarily_unavailable"):
            await client.get("http://api:8000/api/v1/workers")
        assert (await client.get("http://api:8000/api/v1/workers")).status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434/api/tags",
        "https://images.example.test/image.jpg",
        "http://api:8000/unrelated",
        "http://api:8001/api/v1/jobs",
    ],
)
async def test_api_credentials_never_sent_to_ollama_images_or_other_origins(url: str) -> None:
    auth = ApiAuth(
        ServiceSettings(
            _env_file=None,
            api_url="http://api:8000",
            api_token="fixture-static",  # noqa: S106 - fixture
            development_user_id="fixture-user",
        )
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        assert "X-Development-User" not in request.headers
        return httpx.Response(200)

    async with httpx.AsyncClient(auth=auth, transport=httpx.MockTransport(handler)) as client:
        await client.get(url)


@pytest.mark.parametrize("status", [403, 500])
async def test_non_401_api_failures_are_never_replayed(tmp_path: Path, status: int) -> None:
    count = 0

    def api(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(status)

    auth = ApiAuth(settings(tmp_path), transport=httpx.MockTransport(lambda _: session(1)))
    async with httpx.AsyncClient(auth=auth, transport=httpx.MockTransport(api)) as client:
        assert (await client.post("http://api:8000/api/v1/jobs/claim")).status_code == status
    assert count == 1


def test_production_without_credentials_fails_closed() -> None:
    with pytest.raises(ValueError, match="Production services"):
        ApiAuth(ServiceSettings(_env_file=None, environment="production"))


def test_mixed_credentials_are_rejected(tmp_path: Path) -> None:
    config = settings(tmp_path)
    config.api_token = "fixture-static"  # noqa: S105 - fixture
    with pytest.raises(ValueError, match="Do not mix"):
        ApiAuth(config)


async def test_missing_password_file_is_sanitized(tmp_path: Path) -> None:
    config = settings(tmp_path)
    config.service_password_file = str(tmp_path / "missing-password.txt")
    auth = ApiAuth(config)
    async with httpx.AsyncClient(auth=auth, transport=httpx.MockTransport(lambda _: httpx.Response(200))) as client:
        with pytest.raises(ServiceAuthError, match="^service_password_file_unreadable$"):
            await client.get("http://api:8000/api/v1/workers")


@pytest.mark.parametrize("body", [{}, {"access_token": "fixture", "refresh_token": "fixture", "expires_in": "NaN"}])
async def test_malformed_auth_response_does_not_reach_api(tmp_path: Path, body: dict[str, str]) -> None:
    reached_api = False

    def api(request: httpx.Request) -> httpx.Response:
        nonlocal reached_api
        reached_api = True
        return httpx.Response(200)

    auth = ApiAuth(settings(tmp_path), transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    async with httpx.AsyncClient(auth=auth, transport=httpx.MockTransport(api)) as client:
        with pytest.raises(ServiceAuthError, match="^service_auth_invalid_response$"):
            await client.get("http://api:8000/api/v1/workers")
    assert not reached_api


async def test_auth_network_errors_do_not_expose_underlying_exception(tmp_path: Path) -> None:
    def authenticate(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sensitive connection diagnostics", request=request)

    auth = ApiAuth(settings(tmp_path), transport=httpx.MockTransport(authenticate))
    async with httpx.AsyncClient(auth=auth, transport=httpx.MockTransport(lambda _: httpx.Response(200))) as client:
        with pytest.raises(ServiceAuthError, match="^service_auth_network_unavailable$"):
            await client.get("http://api:8000/api/v1/workers")


async def test_static_token_mode_remains_compatible() -> None:
    auth = ApiAuth(ServiceSettings(_env_file=None, api_url="http://api:8000", api_token="fixture-static"))  # noqa: S106

    def api(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer fixture-static"
        return httpx.Response(200)

    async with httpx.AsyncClient(auth=auth, transport=httpx.MockTransport(api)) as client:
        assert (await client.get("http://api:8000/api/v1/workers")).status_code == 200
