from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Protocol
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from .settings import Settings, get_settings


class Identity(BaseModel):
    user_id: UUID
    email: str | None = None
    roles: list[str] = []


class IdentityProvider(Protocol):
    async def authenticate(self, authorization: str | None, development_user: str | None) -> Identity: ...


class DevelopmentIdentityProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def authenticate(self, authorization: str | None, development_user: str | None) -> Identity:
        del authorization
        try:
            user_id = UUID(development_user or self.settings.development_user_id)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="invalid development user id") from exc
        return Identity(user_id=user_id, email="developer@local", roles=["owner"])


class SupabaseIdentityProvider:
    def __init__(self, settings: Settings) -> None:
        assert settings.supabase_url is not None
        self.settings = settings
        self.jwk_client = jwt.PyJWKClient(
            f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json",
            cache_keys=True,
        )

    async def authenticate(self, authorization: str | None, development_user: str | None) -> Identity:
        del development_user
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = authorization.removeprefix("Bearer ").strip()
        try:
            signing_key = self.jwk_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self.settings.supabase_jwt_audience,
                options={"require": ["exp", "sub"]},
            )
            roles = payload.get("app_metadata", {}).get("roles", [])
            return Identity(user_id=UUID(payload["sub"]), email=payload.get("email"), roles=roles)
        except (jwt.PyJWTError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc


@lru_cache
def get_identity_provider() -> IdentityProvider:
    settings = get_settings()
    if settings.auth_mode == "supabase":
        return SupabaseIdentityProvider(settings)
    return DevelopmentIdentityProvider(settings)


async def get_identity(
    authorization: Annotated[str | None, Header()] = None,
    x_development_user: Annotated[str | None, Header()] = None,
    provider: IdentityProvider = Depends(get_identity_provider),
) -> Identity:
    return await provider.authenticate(authorization, x_development_user)


CurrentIdentity = Annotated[Identity, Depends(get_identity)]
