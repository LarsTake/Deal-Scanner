from __future__ import annotations

import asyncio
import math
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Literal

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEAL_SCANNER_", env_file=".env", extra="ignore")

    environment: str = "development"
    api_url: str = "http://127.0.0.1:8000"
    api_token: str | None = None
    development_user_id: str | None = None
    service_auth_mode: Literal["static", "supabase"] = "static"
    service_email: str = ""
    service_password_file: str = ""
    supabase_url: str = ""
    supabase_publishable_key: str = ""


class ServiceAuthError(httpx.HTTPError):
    """Only sanitized error codes are exposed to service logs and job failure payloads."""


class ApiAuth(httpx.Auth):
    requires_request_body = True
    requires_response_body = True

    def __init__(self, settings: ServiceSettings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._api = httpx.URL(settings.api_url)
        self._mode = settings.service_auth_mode
        self._token = settings.api_token or ""
        self._development_user = settings.development_user_id or ""
        self._auth_url = settings.supabase_url.rstrip("/")
        self._publishable_key = settings.supabase_publishable_key
        self._email = settings.service_email
        self._password_file = settings.service_password_file
        self._transport = transport
        self._refresh_token = ""
        self._expires_at = 0.0
        self._blocked = False
        self._lock = asyncio.Lock()
        if self._mode == "supabase":
            if not all((self._auth_url, self._publishable_key, self._email, self._password_file)):
                raise ValueError("Supabase service auth requires URL, publishable key, email and password file")
            url = httpx.URL(self._auth_url)
            if url.scheme != "https" and not (url.scheme == "http" and url.host in {"127.0.0.1", "localhost"}):
                raise ValueError("Supabase service credentials require HTTPS")
            if url.username or url.password or url.query or url.fragment:
                raise ValueError("Supabase URL must not contain credentials, query or fragment")
            if self._token or self._development_user:
                raise ValueError("Do not mix service auth with static tokens or development identity")
        elif settings.environment == "production" and (not self._token or self._development_user):
            raise ValueError("Production services require service auth or a static token without development identity")

    def _is_api(self, url: httpx.URL) -> bool:
        return (url.scheme, url.host, url.port) == (
            self._api.scheme,
            self._api.host,
            self._api.port,
        ) and url.path.startswith("/api/v1/")

    def _read_password(self) -> str:
        with Path(self._password_file).open(encoding="utf-8-sig") as source:
            return source.read(4098).rstrip("\r\n")

    async def _session(self, *, rejected_token: str | None = None) -> None:
        async with self._lock:
            if self._blocked:
                raise ServiceAuthError("service_session_rejected_restart_after_review")
            if (
                self._token
                and time.monotonic() < self._expires_at
                and (rejected_token is None or rejected_token != self._token)
            ):
                return
            refreshing = bool(self._refresh_token)
            if refreshing:
                payload = {"refresh_token": self._refresh_token}
            else:
                try:
                    password = await asyncio.to_thread(self._read_password)
                except (OSError, UnicodeError):
                    raise ServiceAuthError("service_password_file_unreadable") from None
                if not password or len(password) > 4096:
                    raise ServiceAuthError("service_password_file_empty_or_invalid")
                payload = {"email": self._email, "password": password}
            try:
                async with httpx.AsyncClient(transport=self._transport, timeout=20, follow_redirects=False) as client:
                    response = await client.post(
                        self._auth_url + "/auth/v1/token",
                        params={"grant_type": "refresh_token" if refreshing else "password"},
                        headers={"apikey": self._publishable_key},
                        json=payload,
                    )
            except httpx.HTTPError:
                raise ServiceAuthError("service_auth_network_unavailable") from None
            if response.status_code in {400, 401, 403, 422}:
                self._blocked = True
                self._token = self._refresh_token = ""
                raise ServiceAuthError("service_session_or_credentials_rejected")
            if response.status_code != 200:
                raise ServiceAuthError("service_auth_temporarily_unavailable")
            try:
                body = response.json()
                access, refresh, lifetime = body["access_token"], body["refresh_token"], float(body["expires_in"])
                if (
                    not isinstance(access, str)
                    or not access
                    or not isinstance(refresh, str)
                    or not refresh
                    or not math.isfinite(lifetime)
                    or lifetime <= 0
                ):
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                raise ServiceAuthError("service_auth_invalid_response") from None
            self._token, self._refresh_token = access, refresh
            self._expires_at = time.monotonic() + lifetime - min(60, lifetime / 5)

    async def async_auth_flow(self, request: httpx.Request) -> AsyncGenerator[httpx.Request, httpx.Response]:
        if not self._is_api(request.url):
            yield request
            return
        if self._mode == "supabase":
            await self._session()
        if self._token:
            request.headers["Authorization"] = f"Bearer {self._token}"
        if self._mode == "static" and self._development_user:
            request.headers["X-Development-User"] = self._development_user
        token_used = self._token
        response = yield request
        if response.status_code == 401 and self._mode == "supabase":
            await self._session(rejected_token=token_used)
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request  # Exactly one retry; no replay for 403, 5xx, or transport failures.


def create_api_auth(settings: ServiceSettings) -> ApiAuth:
    return ApiAuth(settings)
