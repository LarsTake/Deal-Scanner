import html
import json
from decimal import Decimal

import httpx
import pytest
from deal_scanner_api.services import validate_import_url
from deal_scanner_core.errors import ProviderError
from deal_scanner_core.models import SearchProfile
from deal_scanner_marketplace_web import PublicMarketplaceProvider, parse_mydealz, parse_vinted
from fastapi import HTTPException


def deal(**updates: object) -> str:
    thread = {
        "threadId": 123,
        "title": "Gaming PC Angebot",
        "titleSlug": "gaming-pc",
        "price": 499.99,
        "shipping": {"price": 5},
        "type": "Deal",
        "isExpired": False,
        **updates,
    }
    component = json.dumps({"name": "ThreadMainListItemNormalizer", "props": {"thread": thread}})
    return f'<article data-vue3="{html.escape(component, quote=True)}"></article>'


VINTED = """<a data-testid="item-123--overlay-link" href="/items/123-gaming-pc?ref=search"
    title="Gaming PC, Marke: HP, Zustand: Gut, 100.00 €, 106.00 €"></a>
    <img data-testid="item-123--image--img" src="https://images1.vinted.net/pc.jpg">"""


def test_mydealz_parses_active_prices_shipping_and_deduplicates() -> None:
    items = parse_mydealz(deal() + deal() + deal(threadId=456, isExpired=True))
    assert len(items) == 1
    assert items[0]["price"] == "499.99"
    assert items[0]["shippingCost"] == "5.00"
    assert items[0]["url"] == "https://www.mydealz.de/deals/gaming-pc-123"
    assert parse_mydealz(deal(price=None)) == []
    assert parse_mydealz(deal(price=True)) == []
    assert parse_mydealz(deal(price="NaN")) == []
    with pytest.raises(ProviderError, match="layout"):
        parse_mydealz("<div>unexpected redesign</div>")


def test_vinted_keeps_item_price_and_buyer_protection_separate() -> None:
    items = parse_vinted(VINTED + VINTED)
    assert len(items) == 1
    assert items[0]["title"] == "Gaming PC"
    assert items[0]["price"] == "100.00"
    assert items[0]["buyerProtectionFee"] == "6.00"
    assert items[0]["shippingKnown"] is False
    assert "?" not in items[0]["url"]
    assert (
        parse_vinted(VINTED.replace("/items/123-gaming-pc?ref=search", "https://evil.example/items/123-gaming-pc"))
        == []
    )
    assert parse_vinted("<h1>Keine Artikel gefunden</h1>") == []


@pytest.mark.parametrize(
    "platform,url",
    [
        ("mydealz", "https://www.vinted.de/items/123-pc"),
        ("vinted", "https://www.mydealz.de/deals/pc-123"),
        ("mydealz", "https://www.mydealz.de.evil.example/deals/pc-123"),
    ],
)
def test_new_import_platforms_do_not_widen_the_host_boundary(platform: str, url: str) -> None:
    with pytest.raises(HTTPException) as error:
        validate_import_url(url, platform)
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_vinted_warms_once_normalizes_fee_and_filters_actual_known_cost() -> None:
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        return httpx.Response(200, text=VINTED if request.url.path == "/catalog" else "<html>Home</html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = PublicMarketplaceProvider("vinted", client)
        provider._gateway._next_request = 0
        # A test gateway with no delay preserves real parser and transport logic.
        from dataclasses import replace

        provider._gateway.settings = replace(provider._gateway.settings, request_interval_seconds=0)
        profile = SearchProfile(name="Vinted", query="gaming", maximum_price=Decimal("106"))
        snapshots = [item async for item in provider.discover(profile)]
        assert (await provider.normalize(snapshots[0])).price.amount == Decimal("106")
        profile.maximum_price = Decimal("105")
        assert [item async for item in provider.discover(profile)] == []
        assert requests.count("/") == 1
        profile.location = "Berlin"
        with pytest.raises(ProviderError, match="geographic"):
            _ = [item async for item in provider.discover(profile)]
