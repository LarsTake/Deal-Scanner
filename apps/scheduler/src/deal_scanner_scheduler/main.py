from __future__ import annotations

import asyncio
import hashlib
import imaplib
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx
import structlog
from deal_scanner_core.models import SearchProfile
from deal_scanner_ebay import EbayProvider, EbaySettings
from deal_scanner_email import KleinanzeigenMailParser
from deal_scanner_extraction import RuleExtractor
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logger = structlog.get_logger("deal_scanner_scheduler")


class SchedulerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DEAL_SCANNER_", env_file=".env", extra="ignore")

    api_url: str = "http://127.0.0.1:8000"
    api_token: str | None = None
    development_user_id: str | None = None
    ebay_environment: str = "sandbox"
    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    imap_host: str = ""
    imap_username: str = ""
    imap_password: str = ""
    imap_allowed_senders: str = "kleinanzeigen.de"
    scheduler_interval_seconds: int = 300
    database_url: str = ""
    mail_archive_dir: str = ".data/mail-archive"
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    health_file: str = ""


class Scheduler:
    def __init__(self, settings: SchedulerSettings) -> None:
        self.settings = settings
        headers: dict[str, str] = {}
        if settings.api_token:
            headers["Authorization"] = f"Bearer {settings.api_token}"
        if settings.development_user_id:
            headers["X-Development-User"] = settings.development_user_id
        self.client = httpx.AsyncClient(base_url=settings.api_url, headers=headers, timeout=30)
        self._workspace_id: str | None = None

    async def sync_ebay(self) -> int:
        if not self.settings.ebay_client_id or not self.settings.ebay_client_secret:
            return 0
        configuration_response = await self.client.get("/api/v1/provider-configurations")
        configuration_response.raise_for_status()
        ebay_configuration = next(
            (item for item in configuration_response.json() if item["provider"] == "ebay"),
            None,
        )
        if ebay_configuration is not None and not ebay_configuration["enabled"]:
            return 0
        provider_settings = ebay_configuration["settings"] if ebay_configuration is not None else {}
        response = await self.client.get("/api/v1/search-profiles")
        response.raise_for_status()
        imported = 0
        provider = EbayProvider(
            EbaySettings(
                client_id=self.settings.ebay_client_id,
                client_secret=self.settings.ebay_client_secret,
                environment=str(provider_settings.get("environment", self.settings.ebay_environment)),
                marketplace_id=str(provider_settings.get("marketplaceId", "EBAY_DE")),
            )
        )
        try:
            for item in response.json():
                if not item["enabled"] or "ebay" not in item["enabledPlatforms"]:
                    continue
                history_response = await self.client.get(
                    "/api/v1/provider-sync-runs",
                    params={"provider": "ebay", "searchProfileId": item["id"], "limit": 1},
                )
                history_response.raise_for_status()
                history = history_response.json()["items"]
                previous = history[0] if history else None
                if previous and previous["status"] == "COMPLETED" and previous["completedAt"]:
                    completed_at = datetime.fromisoformat(previous["completedAt"].replace("Z", "+00:00"))
                    if datetime.now(UTC) - completed_at < timedelta(minutes=item["scanIntervalMinutes"]):
                        continue
                if previous and previous["status"] == "RUNNING":
                    interrupted = await self.client.patch(
                        f"/api/v1/provider-sync-runs/{previous['id']}",
                        json={
                            "status": "FAILED",
                            "cursor": previous["cursor"],
                            "discoveredCount": previous["discoveredCount"],
                            "importedCount": previous["importedCount"],
                            "errorSummary": "scheduler restarted before finalization",
                        },
                    )
                    interrupted.raise_for_status()
                cursor = previous["cursor"] if previous and previous["cursor"] else "0"
                delta_window_end = datetime.now(UTC)
                run_response = await self.client.post(
                    "/api/v1/provider-sync-runs",
                    json={"searchProfileId": item["id"], "provider": "ebay", "cursor": cursor},
                )
                run_response.raise_for_status()
                run_id = run_response.json()["id"]
                discovered = 0
                run_imported = 0
                profile = SearchProfile.model_validate(
                    {
                        key: value
                        for key, value in item.items()
                        if key
                        in {
                            "id",
                            "name",
                            "query",
                            "categoryProfile",
                            "enabledPlatforms",
                            "minimumPrice",
                            "maximumPrice",
                            "location",
                            "radiusKm",
                            "requiredTerms",
                            "excludedTerms",
                            "requiredProducts",
                            "excludedProducts",
                            "minimumDealScore",
                            "maximumRiskScore",
                            "notificationSettings",
                            "scanIntervalMinutes",
                            "enabled",
                        }
                    }
                )
                try:
                    async for snapshot in provider.discover(profile, cursor):
                        discovered += 1
                        normalized = await provider.normalize(snapshot)
                        if not self._matches_profile(
                            profile,
                            normalized.title,
                            normalized.description,
                            normalized.location,
                            snapshot.payload.get("distanceKm"),
                        ):
                            continue
                        payload: dict[str, Any] = {
                            "platform": "ebay",
                            "externalId": normalized.external_id,
                            "url": str(normalized.url),
                            "title": normalized.title,
                            "description": normalized.description,
                            "price": str(normalized.price.amount),
                            "shippingCost": str(
                                normalized.shipping_cost.amount if normalized.shipping_cost else Decimal("0")
                            ),
                            "currency": normalized.price.currency,
                            "location": normalized.location,
                            "categoryProfile": item["categoryProfile"],
                            "rawData": snapshot.payload,
                            "providerVersion": snapshot.provider_version,
                            "searchProfileId": item["id"],
                            "publishedAt": normalized.published_at.isoformat() if normalized.published_at else None,
                        }
                        seller_data = snapshot.payload.get("seller")
                        if normalized.seller_external_id and isinstance(seller_data, dict):
                            payload["seller"] = {
                                "externalId": normalized.seller_external_id,
                                "displayName": seller_data.get("username"),
                                "ratingScore": seller_data.get("feedbackPercentage"),
                                "reviewCount": seller_data.get("feedbackScore"),
                                "rawData": seller_data,
                            }
                        result = await self.client.post(
                            "/api/v1/imports/manual",
                            json=payload,
                            headers={"Idempotency-Key": normalized.raw_snapshot_hash},
                        )
                        result.raise_for_status()
                        import_result = result.json()
                        created = int(import_result["snapshotCreated"])
                        imported += created
                        run_imported += created
                        image_urls = self._ebay_image_urls(snapshot.payload)
                        if created and image_urls:
                            image_result = await self.client.post(
                                f"/api/v1/listings/{import_result['listing']['id']}/images",
                                json={"sourceUrls": image_urls},
                            )
                            image_result.raise_for_status()
                    next_cursor = delta_window_end.isoformat().replace("+00:00", "Z")
                    completed = await self.client.patch(
                        f"/api/v1/provider-sync-runs/{run_id}",
                        json={
                            "status": "COMPLETED",
                            "cursor": next_cursor,
                            "discoveredCount": discovered,
                            "importedCount": run_imported,
                        },
                    )
                    completed.raise_for_status()
                except Exception as exc:
                    failed = await self.client.patch(
                        f"/api/v1/provider-sync-runs/{run_id}",
                        json={
                            "status": "FAILED",
                            "cursor": cursor,
                            "discoveredCount": discovered,
                            "importedCount": run_imported,
                            "errorSummary": str(exc)[:4000],
                        },
                    )
                    failed.raise_for_status()
        finally:
            await provider.close()
        return imported

    @staticmethod
    def _matches_profile(
        profile: SearchProfile,
        title: str,
        description: str,
        location: str | None = None,
        distance_km: object | None = None,
    ) -> bool:
        text = f"{title}\n{description}".casefold()
        if any(term.casefold() not in text for term in profile.required_terms if term.strip()):
            return False
        if any(term.casefold() in text for term in profile.excluded_terms if term.strip()):
            return False
        detected = RuleExtractor().analyze(title, description).products
        product_text = " ".join(
            f"{item.product_type} {item.manufacturer or ''} {item.model} {item.variant or ''}" for item in detected
        ).casefold()
        if any(product.casefold() not in product_text for product in profile.required_products if product.strip()):
            return False
        if any(product.casefold() in product_text for product in profile.excluded_products if product.strip()):
            return False
        if profile.location and (not location or profile.location.casefold() not in location.casefold()):
            return False
        if profile.radius_km is not None and distance_km is not None:
            try:
                if Decimal(str(distance_km)) > profile.radius_km:
                    return False
            except ArithmeticError:
                return False
        return True

    @staticmethod
    def _ebay_image_urls(payload: dict[str, Any]) -> list[str]:
        candidates = [
            (payload.get("image") or {}).get("imageUrl"),
            *[image.get("imageUrl") for image in payload.get("additionalImages", [])],
        ]
        return list(dict.fromkeys(url for url in candidates if isinstance(url, str) and url.startswith("https://")))[
            :10
        ]

    async def poll_imap(self) -> int:
        if not self.settings.imap_host or not self.settings.imap_username:
            return 0
        messages = await asyncio.to_thread(self._fetch_unseen)
        parser = KleinanzeigenMailParser(self._allowed_mail_senders())
        imported = 0
        processed_ids: list[str] = []
        try:
            for message_id, raw in messages:
                archive_path = self._archive_mail(raw, quarantine=False)
                try:
                    parsed = parser.parse(raw)
                except ValueError as exc:
                    archive_path = self._archive_mail(raw, quarantine=True)
                    await self._upload_mail(raw, quarantine=True)
                    await self._record_mail(raw, archive_path, "QUARANTINED", error=str(exc))
                    processed_ids.append(message_id)
                    continue
                if parsed.needs_recheck or not parsed.listing_url or not parsed.price:
                    archive_path = self._archive_mail(raw, quarantine=True)
                    await self._upload_mail(raw, quarantine=True)
                    await self._record_mail(
                        raw,
                        archive_path,
                        "QUARANTINED",
                        parsed=parsed.model_dump(mode="json"),
                        error="known parser could not extract URL and price",
                    )
                    processed_ids.append(message_id)
                    continue
                await self._upload_mail(raw, quarantine=False)
                result = await self.client.post(
                    "/api/v1/imports/email",
                    headers={"Idempotency-Key": parsed.raw_sha256},
                    json={
                        "platform": "kleinanzeigen",
                        "externalId": hashlib.sha256(parsed.listing_url.encode()).hexdigest()[:24],
                        "url": parsed.listing_url,
                        "title": parsed.title or parsed.subject,
                        "description": "Importiert aus Kleinanzeigen-Suchbenachrichtigung.",
                        "price": parsed.price,
                        "currency": "EUR",
                        "rawData": parsed.model_dump(mode="json"),
                        "providerVersion": parsed.parser_version,
                    },
                )
                result.raise_for_status()
                imported += int(result.json()["snapshotCreated"])
                await self._record_mail(
                    raw,
                    archive_path,
                    "IMPORTED",
                    parsed=parsed.model_dump(mode="json"),
                )
                processed_ids.append(message_id)
        finally:
            if processed_ids:
                await asyncio.to_thread(self._mark_seen, processed_ids)
        return imported

    def _fetch_unseen(self) -> list[tuple[str, bytes]]:
        allowed_senders = self._allowed_mail_senders()
        if not allowed_senders:
            return []
        mailbox = imaplib.IMAP4_SSL(self.settings.imap_host)
        try:
            mailbox.login(self.settings.imap_username, self._imap_password())
            mailbox.select("INBOX")
            message_ids: list[bytes] = []
            seen_ids: set[bytes] = set()
            for sender in sorted(allowed_senders):
                status, data = mailbox.search(None, "UNSEEN", "FROM", sender)
                if status != "OK" or not data:
                    continue
                for message_id in data[0].split():
                    if message_id not in seen_ids:
                        message_ids.append(message_id)
                        seen_ids.add(message_id)
            messages: list[tuple[str, bytes]] = []
            for message_id in message_ids[:100]:
                message_id_text = message_id.decode("ascii")
                fetch_status, payload = mailbox.fetch(message_id_text, "(BODY.PEEK[])")
                if fetch_status == "OK" and payload and isinstance(payload[0], tuple):
                    messages.append((message_id_text, payload[0][1]))
            return messages
        finally:
            try:
                mailbox.logout()
            except imaplib.IMAP4.error:
                pass

    def _allowed_mail_senders(self) -> set[str]:
        return {sender.strip().casefold() for sender in self.settings.imap_allowed_senders.split(",") if sender.strip()}

    def _imap_password(self) -> str:
        if self.settings.imap_host.casefold() == "imap.gmail.com":
            return "".join(self.settings.imap_password.split())
        return self.settings.imap_password

    def _mark_seen(self, message_ids: list[str]) -> None:
        mailbox = imaplib.IMAP4_SSL(self.settings.imap_host)
        try:
            mailbox.login(self.settings.imap_username, self._imap_password())
            mailbox.select("INBOX")
            for message_id in message_ids:
                mailbox.store(message_id, "+FLAGS", "\\Seen")
        finally:
            try:
                mailbox.logout()
            except imaplib.IMAP4.error:
                pass

    def _archive_mail(self, raw: bytes, *, quarantine: bool) -> Path:
        digest = hashlib.sha256(raw).hexdigest()
        archive = Path(self.settings.mail_archive_dir)
        if quarantine:
            archive /= "quarantine"
        archive.mkdir(parents=True, exist_ok=True)
        target = archive / f"{digest}.eml"
        if not target.exists():
            target.write_bytes(raw)
        return target

    async def _upload_mail(self, raw: bytes, *, quarantine: bool) -> None:
        if not self.settings.supabase_url or not self.settings.supabase_publishable_key or not self.settings.api_token:
            return
        if self._workspace_id is None:
            response = await self.client.get("/api/v1/auth/me")
            response.raise_for_status()
            workspaces = response.json()["workspaces"]
            if not workspaces:
                raise RuntimeError("scheduler identity has no workspace")
            self._workspace_id = workspaces[0]["id"]
        digest = hashlib.sha256(raw).hexdigest()
        folder = "quarantine/" if quarantine else ""
        target = (
            f"{self.settings.supabase_url.rstrip('/')}/storage/v1/object/mail-archive/"
            f"{self._workspace_id}/{folder}{digest}.eml"
        )
        response = await self.client.post(
            target,
            content=raw,
            headers={
                "apikey": self.settings.supabase_publishable_key,
                "Content-Type": "message/rfc822",
                "x-upsert": "false",
            },
        )
        if response.status_code != 409:
            response.raise_for_status()

    async def _record_mail(
        self,
        raw: bytes,
        archive_path: Path,
        status: str,
        *,
        parsed: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        message = BytesParser(policy=policy.default).parsebytes(raw, headersonly=True)
        digest = hashlib.sha256(raw).hexdigest()
        date_header = str(message.get("Date", ""))
        try:
            received_at = parsedate_to_datetime(date_header) if date_header else datetime.now(UTC)
        except (TypeError, ValueError):
            received_at = datetime.now(UTC)
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=UTC)
        response = await self.client.post(
            "/api/v1/mail-imports",
            json={
                "messageId": str(message.get("Message-ID") or digest),
                "sender": str(message.get("From", "")),
                "subject": str(message.get("Subject", "")),
                "receivedAt": received_at.isoformat(),
                "rawStoragePath": str(archive_path),
                "rawSha256": digest,
                "parserVersion": str((parsed or {}).get("parserVersion", "unknown-v1")),
                "status": status,
                "parsedData": parsed,
                "errorSummary": error,
            },
        )
        response.raise_for_status()

    async def run_forever(self) -> None:
        try:
            while True:
                try:
                    await self._run_locked_cycle()
                    self._mark_healthy()
                except Exception as exc:
                    logger.error("scheduler_cycle_failed", error_type=type(exc).__name__)
                await asyncio.sleep(self.settings.scheduler_interval_seconds)
        finally:
            await self.client.aclose()

    def _mark_healthy(self) -> None:
        if self.settings.health_file:
            Path(self.settings.health_file).touch()

    async def _run_locked_cycle(self) -> None:
        started_at = perf_counter()
        if not self.settings.database_url.startswith("postgresql"):
            ebay_imports, email_imports = await asyncio.gather(self.sync_ebay(), self.poll_imap())
            logger.info(
                "scheduler_cycle_completed",
                ebay_imports=ebay_imports,
                email_imports=email_imports,
                duration_ms=round((perf_counter() - started_at) * 1000, 2),
            )
            return
        engine = create_async_engine(self.settings.database_url, pool_pre_ping=True)
        try:
            async with engine.connect() as connection:
                acquired = await connection.scalar(
                    text("select pg_try_advisory_lock(hashtext('deal-scanner-scheduler'))")
                )
                if not acquired:
                    logger.info("scheduler_cycle_skipped", reason="advisory_lock_held")
                    return
                try:
                    ebay_imports, email_imports = await asyncio.gather(self.sync_ebay(), self.poll_imap())
                    logger.info(
                        "scheduler_cycle_completed",
                        ebay_imports=ebay_imports,
                        email_imports=email_imports,
                        duration_ms=round((perf_counter() - started_at) * 1000, 2),
                    )
                finally:
                    await connection.execute(text("select pg_advisory_unlock(hashtext('deal-scanner-scheduler'))"))
        finally:
            await engine.dispose()


def run() -> None:
    structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()])
    if os.getenv("DEAL_SCANNER_ENVIRONMENT") == "production" and not os.getenv("DEAL_SCANNER_API_TOKEN"):
        raise RuntimeError("production scheduler requires an API token")
    asyncio.run(Scheduler(SchedulerSettings()).run_forever())
