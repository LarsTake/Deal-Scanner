from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from urllib.parse import quote, urlencode, urljoin, urlsplit

import httpx
from deal_scanner_core.errors import ProviderError
from deal_scanner_core.models import Money, NormalizedListing, RawListingSnapshot, SearchProfile
from deal_scanner_kleinanzeigen_web import KleinanzeigenWebProvider, WebProviderSettings
from deal_scanner_provider_sdk import content_hash
from scrapling.parser import Selector


def _amount(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        return None
    return amount.quantize(Decimal("0.01")) if amount.is_finite() and 0 <= amount <= 999999999999 else None


def parse_mydealz(html: str) -> list[dict[str, Any]]:
    root = Selector(html)
    components = root.css("[data-vue3]")
    if not components:
        raise ProviderError("mydealz layout not recognized")
    offers: dict[str, dict[str, Any]] = {}
    for node in components:
        try:
            component = json.loads(node.attrib["data-vue3"])
            if component.get("name") != "ThreadMainListItemNormalizer":
                continue
            item = component.get("props", {}).get("thread", {})
            identity = str(item.get("threadId", ""))
            title = str(item.get("title", "")).strip()
            amount = _amount(item.get("price"))
            if (
                not identity.isdigit()
                or not title
                or amount is None
                or item.get("isExpired")
                or item.get("type") != "Deal"
            ):
                continue
            shipping = _amount((item.get("shipping") or {}).get("price"))
            image = item.get("mainImage") or {}
            image_urls = []
            if image.get("path") and image.get("name"):
                path = quote(str(image["path"]), safe="/")
                name = quote(str(image["name"]), safe="")
                image_urls = [f"https://static.mydealz.de/{path}/{name}/re/300x300/qt/60/{name}.jpg"]
            slug = quote(str(item.get("titleSlug") or "deal"), safe="-")
            offers[identity] = {
                "externalId": identity,
                "url": f"https://www.mydealz.de/deals/{slug}-{identity}",
                "title": title[:500],
                "description": str(item.get("description") or "")[:100000],
                "price": str(amount),
                "shippingCost": str(shipping or Decimal("0")),
                "imageUrls": image_urls,
                "merchant": (item.get("merchant") or {}).get("merchantName"),
                "shippingKnown": shipping is not None,
            }
        except (ValueError, TypeError, AttributeError):
            continue
    return list(offers.values())


def parse_vinted(html: str) -> list[dict[str, Any]]:
    root = Selector(html)
    links = root.css('a[data-testid$="--overlay-link"]')
    if not links:
        if re.search(r"keine (?:Artikel|Ergebnisse)|no items found", html, re.IGNORECASE):
            return []
        raise ProviderError("Vinted catalogue layout not recognized")
    offers: dict[str, dict[str, Any]] = {}
    for link in links:
        url = urljoin("https://www.vinted.de", link.attrib.get("href", ""))
        parsed = urlsplit(url)
        identity = re.fullmatch(r"/items/(\d+)(?:-[^/]*)?/?", parsed.path)
        if parsed.scheme != "https" or parsed.netloc != "www.vinted.de" or identity is None:
            continue
        label = link.attrib.get("title", "")
        parsed_prices = [_amount(value) for value in re.findall(r"(\d+(?:[.,]\d{1,2})?)\s*€", label)]
        prices = [value for value in parsed_prices if value is not None]
        if not prices:
            continue
        title = re.split(r",\s*(?:Marke|Zustand|Größe):|\d+(?:[.,]\d{1,2})?\s*€", label)[0].rstrip(", ")
        if not title:
            continue
        suffix = link.attrib.get("data-testid", "").removesuffix("--overlay-link") + "--image--img"
        images = [node for node in root.css("img[data-testid]") if node.attrib.get("data-testid") == suffix]
        image = images[0].attrib.get("src", "") if images else ""
        offers[identity.group(1)] = {
            "externalId": identity.group(1),
            "url": f"https://www.vinted.de{parsed.path}",
            "title": title[:500],
            "description": label[:100000],
            "price": str(prices[0]),
            "buyerProtectionFee": str(max(Decimal("0"), prices[-1] - prices[0])),
            "buyerProtectionKnown": len(prices) > 1,
            "imageUrls": [image]
            if (
                urlsplit(image).scheme == "https"
                and urlsplit(image).netloc in {"images1.vinted.net", "images2.vinted.net"}
            )
            else [],
            "shippingKnown": False,
        }
    return list(offers.values())


class PublicMarketplaceProvider:
    provider_version = "public-search-v1"

    def __init__(
        self,
        platform: Literal["mydealz", "vinted"],
        client: httpx.AsyncClient | None = None,
        fetch_mode: Literal["http", "browser", "stealth"] = "http",
    ) -> None:
        self.platform = platform
        self._gateway = KleinanzeigenWebProvider(
            WebProviderSettings(
                storage_file=None,
                allowed_hosts=(f"www.{platform}.de",),
                maximum_response_bytes=8 * 1024 * 1024 if platform == "vinted" else 2 * 1024 * 1024,
                fetch_mode=fetch_mode,
            ),
            client,
        )
        self._warmed = False

    async def close(self) -> None:
        await self._gateway.close()

    async def discover(self, profile: SearchProfile, cursor: str | None = None) -> AsyncIterator[RawListingSnapshot]:
        del cursor
        if profile.location or profile.radius_km is not None:
            raise ProviderError(f"{self.platform} does not provide verified geographic search")
        base = f"https://www.{self.platform}.de"
        if self.platform == "mydealz":
            url = f"{base}/search?{urlencode({'q': profile.query})}"
            parser = parse_mydealz
        else:
            if not self._warmed:
                await self._gateway.get_document(f"{base}/")
                self._warmed = True
            url = f"{base}/catalog?{urlencode({'search_text': profile.query, 'order': 'newest_first'})}"
            parser = parse_vinted
        items = await asyncio.to_thread(parser, await self._gateway.get_document(url))
        for item in items:
            price = Decimal(item["price"]) + Decimal(item.get("buyerProtectionFee", "0"))
            if profile.minimum_price is not None and price < profile.minimum_price:
                continue
            if profile.maximum_price is not None and price > profile.maximum_price:
                continue
            if self.platform == "mydealz" and not all(
                token.casefold() in item["title"].casefold() for token in profile.query.split()
            ):
                continue
            yield RawListingSnapshot(
                platform=self.platform,
                external_id=item["externalId"],
                source_url=item["url"],
                fetched_at=datetime.now(UTC),
                payload=item,
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
            price=Money(amount=Decimal(item["price"]) + Decimal(item.get("buyerProtectionFee", "0"))),
            shipping_cost=Money(amount=Decimal(item.get("shippingCost", "0"))),
            raw_snapshot_hash=content_hash(item),
        )
