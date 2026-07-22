from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse
from uuid import UUID

import httpx
from deal_scanner_extraction import ImageFingerprint, InvalidImage, fingerprint_image
from fastapi import HTTPException

from .settings import Settings, get_settings

IMAGE_HOSTS = {
    "ebay": {"i.ebayimg.com"},
    "kleinanzeigen": {"img.kleinanzeigen.de", "img.classistatic.de"},
}


def validate_image_url(source_url: str, platform: str) -> None:
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(status_code=422, detail="image URL must be a public HTTPS provider URL")
    if parsed.port not in (None, 443):
        raise HTTPException(status_code=422, detail="image URL uses a forbidden port")
    allowed = IMAGE_HOSTS.get(platform, set())
    hostname = parsed.hostname.casefold().rstrip(".")
    if hostname not in allowed:
        raise HTTPException(status_code=422, detail="image host is not allowed for this provider")


async def download_provider_image(
    source_url: str,
    platform: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[bytes, ImageFingerprint]:
    validate_image_url(source_url, platform)
    owns_client = client is None
    http_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(20, connect=5),
        follow_redirects=False,
        trust_env=False,
    )
    try:
        async with http_client.stream(
            "GET",
            source_url,
            headers={"Accept": "image/avif,image/webp,image/png,image/jpeg"},
        ) as response:
            if response.is_redirect:
                raise HTTPException(status_code=422, detail="image redirects are not accepted")
            response.raise_for_status()
            declared_size = int(response.headers.get("Content-Length", "0") or 0)
            if declared_size > 15 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="image exceeds the 15 MB limit")
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > 15 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="image exceeds the 15 MB limit")
                chunks.append(chunk)
        content = b"".join(chunks)
        try:
            return content, fingerprint_image(content)
        except InvalidImage as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="provider image could not be downloaded") from exc
    finally:
        if owns_client:
            await http_client.aclose()


async def store_private_image(
    workspace_id: UUID,
    content: bytes,
    fingerprint: ImageFingerprint,
    settings: Settings | None = None,
) -> str:
    config = settings or get_settings()
    extension = fingerprint.image_format.casefold().replace("jpeg", "jpg")
    storage_path = f"{workspace_id}/{fingerprint.sha256}.{extension}"
    if config.supabase_url and config.supabase_service_role_key:
        upload_url = (
            f"{config.supabase_url.rstrip('/')}/storage/v1/object/listing-images/{quote(storage_path, safe='/')}"
        )
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            response = await client.post(
                upload_url,
                content=content,
                headers={
                    "apikey": config.supabase_service_role_key,
                    "Authorization": f"Bearer {config.supabase_service_role_key}",
                    "Content-Type": fingerprint.mime_type,
                    "x-upsert": "false",
                },
            )
            if response.status_code != 409:
                response.raise_for_status()
        return storage_path

    local_target = Path(config.image_storage_dir) / storage_path
    await asyncio.to_thread(_write_once, local_target, content)
    return storage_path


def _write_once(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(content)


async def create_image_access(
    storage_path: str,
    image_id: UUID,
    settings: Settings | None = None,
) -> tuple[str, datetime | None]:
    config = settings or get_settings()
    if config.supabase_url and config.supabase_service_role_key:
        target = (
            f"{config.supabase_url.rstrip('/')}/storage/v1/object/sign/listing-images/{quote(storage_path, safe='/')}"
        )
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            response = await client.post(
                target,
                json={"expiresIn": 300},
                headers={
                    "apikey": config.supabase_service_role_key,
                    "Authorization": f"Bearer {config.supabase_service_role_key}",
                },
            )
            response.raise_for_status()
        signed_path = response.json()["signedURL"]
        return f"{config.supabase_url.rstrip('/')}/storage/v1{signed_path}", datetime.now(UTC) + timedelta(minutes=5)
    return f"/api/v1/listing-images/{image_id}/content", None


def resolve_local_image(storage_path: str, settings: Settings | None = None) -> Path:
    config = settings or get_settings()
    root = Path(config.image_storage_dir).resolve()
    target = (root / storage_path).resolve()
    if root not in target.parents:
        raise HTTPException(status_code=404, detail="image is unavailable")
    return target
