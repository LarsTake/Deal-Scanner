from __future__ import annotations

import asyncio
import json
import math
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import monotonic
from typing import Any, Literal
from urllib.parse import quote, urljoin, urlsplit
from zoneinfo import ZoneInfo

import httpx
from deal_scanner_core.errors import ProviderError, ProviderRateLimited
from deal_scanner_core.models import Money, NormalizedListing, RawListingSnapshot, SearchProfile
from deal_scanner_provider_sdk import content_hash
from scrapling.parser import Selector

BASE_URL = "https://www.kleinanzeigen.de"
CARD_SELECTOR = "article[data-adid], article.aditem[data-adid]"
LISTING_PATH = re.compile(r"^/s-anzeige/[^/]+/(\d+)-\d+-\d+/?$")
PRICE = re.compile(r"\d[\d.]*(?:,\d{1,2})?\s*€")
PRICE_LINE = re.compile(r"(?:\d[\d.]*(?:,\d{1,2})?\s*€\s*)+(?:VB)?", re.IGNORECASE)
NO_RESULTS = re.compile(r"keine (?:Ergebnisse|Anzeigen|Treffer)", re.IGNORECASE)
CHALLENGE = re.compile(r"captcha|access denied|verify you are human|cf-chl-", re.IGNORECASE)


@dataclass(frozen=True)
class WebProviderSettings:
    storage_file: str | None = ".data/scrapling/kleinanzeigen.db"
    request_interval_seconds: float = 5.0
    cooldown_seconds: float = 1800.0
    maximum_response_bytes: int = 2 * 1024 * 1024
    fetch_details: bool = False
    maximum_details_per_scan: int = 5
    allowed_hosts: tuple[str, ...] = ("www.kleinanzeigen.de",)
    fetch_mode: Literal["http", "browser", "stealth"] = "http"


def _text(node: Any) -> str:
    return " ".join(node.get_all_text(" ", strip=True).split()) if node is not None else ""


def parse_search_results(html: str, storage_file: str | None = None) -> list[dict[str, Any]]:
    """Parse current and legacy cards; adaptive candidates still require valid listing identities."""
    if NO_RESULTS.search(html) and not re.search(r"data-adid\s*=", html):
        return []
    options: dict[str, Any] = {}
    if storage_file:
        Path(storage_file).parent.mkdir(parents=True, exist_ok=True)
        options = {"adaptive": True, "storage_args": {"storage_file": storage_file, "url": BASE_URL}}
    root = Selector(html, url=BASE_URL, **options)
    cards = list(root.css(CARD_SELECTOR, identifier="listing-card", auto_save=bool(storage_file)))
    if not cards and storage_file:
        cards = list(root.css(CARD_SELECTOR, identifier="listing-card", adaptive=True))
        if cards:
            cards = [cards[0], *cards[0].find_similar()]
    if not cards:
        raise ProviderError("Kleinanzeigen layout not recognized; no verified listing cards")
    found: dict[str, dict[str, Any]] = {}
    for card in cards:
        links = card.css("h3 a[href], h2 a[href], a.ellipsis[href]")
        if not links:
            continue
        link = links[0]
        title = _text(link)
        url = urljoin(BASE_URL, card.attrib.get("data-href") or link.attrib.get("href", ""))
        parsed = urlsplit(url)
        identity = LISTING_PATH.fullmatch(parsed.path)
        if parsed.scheme != "https" or parsed.netloc != "www.kleinanzeigen.de" or not identity or not title:
            continue
        external_id = identity.group(1)
        attribute_id = card.attrib.get("data-adid")
        if attribute_id and attribute_id != external_id:
            continue
        price: Decimal | None = None
        for paragraph in card.css("p, .aditem-main--middle--price-shipping--price"):
            text = _text(paragraph)
            amounts = PRICE.findall(text)
            if amounts and PRICE_LINE.fullmatch(text):
                price = min(
                    Decimal(amount.replace("€", "").replace(".", "").replace(",", ".").strip()) for amount in amounts
                )
                break
            if text.casefold() == "zu verschenken":
                price = Decimal("0")
                break
        if price is None:
            continue
        locations = [_text(node) for node in card.css("span, .aditem-main--top--left")]
        descriptions = card.css(".aditem-main--middle--description, h3 + p, h2 + p")
        images = card.css("img")
        image_url = (images[0].attrib.get("src") or images[0].attrib.get("data-src")) if images else None
        found[external_id] = {
            "externalId": external_id,
            "url": url,
            "title": title[:500],
            "description": _text(descriptions[0])[:100000] if descriptions else "",
            "price": str(price.quantize(Decimal("0.01"))),
            "location": next((value[:255] for value in locations if re.match(r"^\d{5}\s+\S", value)), None),
            "imageUrls": [image_url] if image_url and image_url.startswith("https://") else [],
        }
    if not found:
        raise ProviderError("Kleinanzeigen cards contained no valid priced offers; parser needs review")
    return list(found.values())


class KleinanzeigenWebProvider:
    platform = "kleinanzeigen"
    provider_version = "scrapling-search-v1"

    def __init__(self, settings: WebProviderSettings | None = None, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or WebProviderSettings()
        self.client = client or httpx.AsyncClient(
            timeout=20,
            follow_redirects=False,
            headers={
                "User-Agent": "DealScanner/0.1 (+local marketplace monitoring)",
                "Accept-Language": "de-DE",
            },
        )
        self._owns_client = client is None
        self._lock = asyncio.Lock()
        self._next_request = 0.0
        self._blocked_until = 0.0
        self._locations: dict[str, str] = {}
        self._details: dict[str, tuple[str, dict[str, Any], float]] = {}

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    @staticmethod
    def search_url(profile: SearchProfile) -> str:
        slug = quote("-".join(profile.query.strip().split()), safe="-")
        return f"{BASE_URL}/s-anzeige:angebote/sortierung:neuste/{slug}/k0"

    async def get_document(self, url: str) -> str:
        target = urlsplit(url)
        if target.scheme != "https" or target.netloc not in self.settings.allowed_hosts:
            raise ProviderError("Marketplace request host is not allowed")
        async with self._lock:
            now = monotonic()
            if now < self._blocked_until:
                raise ProviderRateLimited(self._blocked_until - now)
            await asyncio.sleep(max(0, self._next_request - now))
            self._next_request = monotonic() + self.settings.request_interval_seconds
            if self.settings.fetch_mode != "http":
                return await self._browser_document(url)
            chunks: list[bytes] = []
            size = 0
            async with self.client.stream("GET", url) as response:
                if response.status_code in {403, 429, 503}:
                    delay = self.settings.cooldown_seconds
                    retry_after = response.headers.get("Retry-After", "")
                    try:
                        requested_delay = float(retry_after)
                    except ValueError:
                        try:
                            requested_delay = (parsedate_to_datetime(retry_after) - datetime.now(UTC)).total_seconds()
                        except (ValueError, TypeError, OverflowError):
                            requested_delay = 0
                    if math.isfinite(requested_delay):
                        delay = max(delay, requested_delay)
                    self._blocked_until = monotonic() + delay
                    raise ProviderRateLimited(delay)
                if response.status_code != 200:
                    raise ProviderError(f"Marketplace request returned HTTP {response.status_code}")
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > self.settings.maximum_response_bytes:
                        raise ProviderError("Marketplace response exceeds size limit")
                    chunks.append(chunk)
            html = b"".join(chunks).decode("utf-8", errors="replace")
            if len(html) < 30000 and CHALLENGE.search(html):
                self._blocked_until = monotonic() + self.settings.cooldown_seconds
                raise ProviderRateLimited(self.settings.cooldown_seconds)
            return html

    async def _browser_document(self, url: str) -> str:
        def fetch() -> Any:
            try:
                from scrapling.fetchers import DynamicFetcher, StealthyFetcher
            except ImportError as error:
                raise ProviderError("Browser mode requires: uv sync --all-packages --extra browser") from error
            options: dict[str, Any] = {
                "headless": True,
                "disable_resources": True,
                "timeout": 20000,
                "google_search": False,
            }

            def setup(page: Any) -> None:
                def limit_request(route: Any) -> None:
                    destination = urlsplit(route.request.url)
                    if (
                        destination.scheme == "https"
                        and destination.netloc in self.settings.allowed_hosts
                        and route.request.method in {"GET", "HEAD"}
                    ):
                        route.continue_()
                    else:
                        route.abort()

                page.route("**/*", limit_request)

            options["page_setup"] = setup
            if self.settings.fetch_mode == "stealth":
                return StealthyFetcher.fetch(url, solve_cloudflare=False, **options)
            return DynamicFetcher.fetch(url, **options)

        try:
            response = await asyncio.to_thread(fetch)
        except ProviderError:
            raise
        except Exception as error:
            raise ProviderError(f"Browser fetch failed: {type(error).__name__}") from error
        parsed = urlsplit(str(response.url))
        if parsed.scheme != "https" or parsed.netloc not in self.settings.allowed_hosts:
            raise ProviderError("Browser navigation left the allowed marketplace")
        body = bytes(response.body)
        html = body.decode("utf-8", errors="replace")
        if response.status in {403, 429, 503} or len(html) < 30000 and CHALLENGE.search(html):
            self._blocked_until = monotonic() + self.settings.cooldown_seconds
            raise ProviderRateLimited(self.settings.cooldown_seconds)
        if response.status != 200:
            raise ProviderError(f"Browser returned HTTP {response.status}")
        if len(body) > self.settings.maximum_response_bytes:
            raise ProviderError("Browser response exceeds size limit")
        return html

    async def _search_url(self, profile: SearchProfile) -> str:
        if profile.radius_km is None:
            return self.search_url(profile)
        if not profile.location:
            raise ProviderError("Kleinanzeigen radius search requires a postal code")
        if profile.radius_km < 5 or profile.radius_km > 200:
            raise ProviderError("Kleinanzeigen supports radius searches between 5 and 200 km")
        if not re.fullmatch(r"\d{5}", profile.location.strip()):
            raise ProviderError("Kleinanzeigen radius search requires a five-digit postal code")
        postal_code = profile.location.strip()
        location_id = self._locations.get(postal_code)
        if location_id is None:
            raw = await self.get_document(f"{BASE_URL}/s-ort-empfehlungen.json?query={postal_code}")
            try:
                candidates = json.loads(raw)
                location_id = next((key[1:] for key in candidates if re.fullmatch(r"_[1-9]\d*", key)), None)
            except (ValueError, TypeError) as exc:
                raise ProviderError("Kleinanzeigen location response is invalid") from exc
            if location_id is None:
                raise ProviderError("Postal code could not be resolved; nationwide fallback refused")
            self._locations[postal_code] = location_id
        allowed = [5, 10, 20, 30, 50, 100, 150, 200]
        # Prefer a smaller supported radius over returning offers outside the requested area.
        radius = max((value for value in allowed if value <= profile.radius_km), default=5)
        slug = quote("-".join(profile.query.strip().split()), safe="-")
        return f"{BASE_URL}/s-{postal_code}/anzeige:angebote/sortierung:neuste/{slug}/k0l{location_id}r{radius}"

    async def discover(self, profile: SearchProfile, cursor: str | None = None) -> AsyncIterator[RawListingSnapshot]:
        del cursor
        url = await self._search_url(profile)
        html = await self.get_document(url)
        items = await asyncio.to_thread(parse_search_results, html, self.settings.storage_file)
        detail_count = 0
        fetched_at = datetime.now(UTC)
        for item in items:
            price = Decimal(item["price"])
            if profile.minimum_price is not None and price < profile.minimum_price:
                continue
            if profile.maximum_price is not None and price > profile.maximum_price:
                continue
            if profile.radius_km is not None and profile.location:
                item["locationFilter"] = profile.location
                item["searchRadiusKm"] = profile.radius_km
            if self.settings.fetch_details:
                digest = content_hash(item)
                cached = self._details.get(item["externalId"])
                if cached and cached[0] == digest and monotonic() < cached[2]:
                    item = {**item, **cached[1]}
                elif detail_count < self.settings.maximum_details_per_scan:
                    detail_count += 1
                    try:
                        detail = await self.fetch(item["url"])
                        if len(self._details) >= 1000:
                            self._details.pop(next(iter(self._details)))
                        self._details[item["externalId"]] = (digest, detail.payload, monotonic() + 3600)
                        item = {**item, **detail.payload}
                    except (ProviderError, httpx.HTTPError):
                        # Preserve verified search-card evidence even when details are temporarily unavailable.
                        if cached and cached[0] == digest:
                            item = {**item, **cached[1]}
            price = Decimal(item["price"])
            if profile.minimum_price is not None and price < profile.minimum_price:
                continue
            if profile.maximum_price is not None and price > profile.maximum_price:
                continue
            yield RawListingSnapshot(
                platform=self.platform,
                external_id=item["externalId"],
                source_url=item["url"],
                fetched_at=fetched_at,
                payload=item,
                provider_version=self.provider_version,
            )

    async def fetch(self, reference: str) -> RawListingSnapshot:
        parsed = urlsplit(reference)
        identity = LISTING_PATH.fullmatch(parsed.path)
        if parsed.scheme != "https" or parsed.netloc != "www.kleinanzeigen.de" or not identity:
            raise ProviderError("Only verified Kleinanzeigen detail URLs are accepted")
        html = await self.get_document(reference)
        root = Selector(html, url=reference)
        descriptions = root.css('#viewad-description-text, [itemprop="description"]')
        detail: dict[str, Any] = {}
        if descriptions:
            detail["description"] = _text(descriptions[0])[:100000]
        title_nodes = root.css("h1")
        price_nodes = root.css('#viewad-price, [itemprop="price"]')
        if not title_nodes or not price_nodes:
            raise ProviderError("Kleinanzeigen detail lacks a verified title or price")
        price_text = price_nodes[0].attrib.get("content") or _text(price_nodes[0])
        if price_text.casefold() == "zu verschenken":
            price = Decimal("0")
        elif price_nodes[0].attrib.get("content") and re.fullmatch(r"\d+(?:[.,]\d{1,2})?", price_text):
            price = Decimal(price_text.replace(",", "."))
        else:
            amounts = PRICE.findall(price_text)
            if not amounts:
                raise ProviderError("Kleinanzeigen detail price is unknown")
            price = min(Decimal(value.replace("€", "").replace(".", "").replace(",", ".").strip()) for value in amounts)
        detail.update(
            {
                "externalId": identity.group(1),
                "url": reference,
                "title": _text(title_nodes[0])[:500],
                "price": str(price.quantize(Decimal("0.01"))),
            }
        )
        detail["detailsLoaded"] = True
        detail.setdefault("description", "")
        dates = root.css(
            'time[itemprop="datePosted"][datetime], time[itemprop="datePublished"][datetime], '
            'meta[itemprop="datePosted"], meta[itemprop="datePublished"]'
        )
        for node in dates:
            value = node.attrib.get("datetime") or node.attrib.get("content", "")
            try:
                posted = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
            if posted.tzinfo is not None and posted <= datetime.now(UTC):
                detail["publishedAt"] = posted.isoformat()
                break
        if "publishedAt" not in detail:
            for node in root.css("#viewad-extra-info"):
                match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", _text(node))
                if not match:
                    continue
                try:
                    posted = datetime.strptime(match.group(1), "%d.%m.%Y").replace(tzinfo=ZoneInfo("Europe/Berlin"))
                except ValueError:
                    continue
                if posted <= datetime.now(UTC):
                    detail["publishedAt"] = posted.isoformat()
                    detail["publishedAtPrecision"] = "day"
                    break
        images = root.css('[itemprop="image"], meta[property="og:image"]')
        urls = [node.attrib.get("content") or node.attrib.get("src", "") for node in images]
        if urls:
            detail["imageUrls"] = list(dict.fromkeys(value for value in urls if value.startswith("https://")))[:10]
        if not detail:
            raise ProviderError("Kleinanzeigen detail layout not recognized")
        return RawListingSnapshot(
            platform=self.platform,
            external_id=identity.group(1),
            source_url=reference,
            fetched_at=datetime.now(UTC),
            payload=detail,
            provider_version=self.provider_version,
        )

    async def normalize(self, snapshot: RawListingSnapshot) -> NormalizedListing:
        item = snapshot.payload
        return NormalizedListing(
            platform=self.platform,
            external_id=snapshot.external_id,
            url=snapshot.source_url,
            title=item["title"],
            description=item["description"],
            price=Money(amount=Decimal(item["price"])),
            location=item.get("location"),
            published_at=datetime.fromisoformat(item["publishedAt"]) if item.get("publishedAt") else None,
            raw_snapshot_hash=content_hash(item),
        )
