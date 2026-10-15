import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from deal_scanner_core.errors import ProviderError, ProviderRateLimited
from deal_scanner_core.models import SearchProfile
from deal_scanner_kleinanzeigen_web import KleinanzeigenWebProvider, WebProviderSettings, parse_search_results
from deal_scanner_scheduler.main import Scheduler, SchedulerSettings

HTML = """
<article data-adid="1234567890" data-href="/s-anzeige/gaming-pc/1234567890-228-1234">
  <h3><a href="/s-anzeige/gaming-pc/1234567890-228-1234">Gaming PC RTX-4070</a></h3>
  <p>Ryzen 7, 32 GB RAM</p><p>1.250 € 999,50 € VB</p>
  <span>10115 Berlin</span><img src="https://img.kleinanzeigen.de/pc.jpg">
</article>
"""


def test_current_cards_prices_duplicates_and_unknown_prices() -> None:
    items = parse_search_results(HTML + HTML + HTML.replace("1.250 € 999,50 € VB", "VB"))
    assert len(items) == 1
    assert items[0]["price"] == "999.50"
    assert items[0]["description"] == "Ryzen 7, 32 GB RAM"
    assert items[0]["location"] == "10115 Berlin"
    with_reference_price = HTML.replace("Ryzen 7, 32 GB RAM", "Neupreis 2.000 € mit Ryzen 7")
    assert parse_search_results(with_reference_price)[0]["price"] == "999.50"
    assert parse_search_results(HTML.replace("1.250 € 999,50 € VB", "Zu verschenken"))[0]["price"] == "0.00"


def test_empty_results_are_distinct_from_layout_failure() -> None:
    assert parse_search_results("<h1>Es wurden keine Ergebnisse gefunden</h1>") == []
    with pytest.raises(ProviderError, match="layout"):
        parse_search_results("<h1>New unknown layout</h1>")
    with pytest.raises(ProviderError, match="no valid priced"):
        parse_search_results(HTML.replace("1.250 € 999,50 € VB", "VB"))


@pytest.mark.parametrize(
    "replacement",
    [
        "https://evil.example/s-anzeige/gaming-pc/1234567890-228-1234",
        "https://www.kleinanzeigen.de@evil.example/s-anzeige/gaming-pc/1234567890-228-1234",
        "/s-anzeige/gaming-pc/9999999999-228-1234",
    ],
)
def test_invalid_or_mismatched_card_identity_is_rejected(replacement: str) -> None:
    with pytest.raises(ProviderError, match="no valid priced"):
        parse_search_results(HTML.replace("/s-anzeige/gaming-pc/1234567890-228-1234", replacement))


def test_tracking_filters_tolerate_punctuation_without_crossing_fields() -> None:
    profile = SearchProfile(name="GPU", query="gaming", required_terms=["RTX 4070"], excluded_terms=["ohne gpu"])
    assert Scheduler._matches_profile(profile, "Gaming RTX-4070", "32 GB")
    assert not Scheduler._matches_profile(profile, "Gaming RTX4070", "ohne-GPU")
    assert not Scheduler._matches_profile(profile, "Gaming RTX", "4070")


def test_adaptive_parser_recovers_card_after_attribute_change(tmp_path: Path) -> None:
    storage = str(tmp_path / "selectors.db")
    assert len(parse_search_results(HTML, storage)) == 1
    changed = HTML.replace('data-adid="1234567890"', 'data-listing="1234567890"')
    assert parse_search_results(changed, storage)[0]["externalId"] == "1234567890"
    assert parse_search_results("<h1>keine Ergebnisse</h1>", storage) == []


@pytest.mark.asyncio
async def test_provider_normalizes_filters_and_hashes_stable_content() -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text=HTML)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = KleinanzeigenWebProvider(WebProviderSettings(storage_file=None, request_interval_seconds=0), client)
        profile = SearchProfile(name="GPU", query="gaming pc", maximum_price=Decimal("1000"))
        first = [item async for item in provider.discover(profile)]
        second = [item async for item in provider.discover(profile)]
        assert len(first) == 1
        assert (await provider.normalize(first[0])).raw_snapshot_hash == (
            await provider.normalize(second[0])
        ).raw_snapshot_hash
        assert calls[0].startswith("https://www.kleinanzeigen.de/s-anzeige:angebote/")
        profile.maximum_price = Decimal("900")
        assert [item async for item in provider.discover(profile)] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,body",
    [
        (429, "blocked"),
        (403, "blocked"),
        (503, "blocked"),
        (200, "verify you are human"),
    ],
)
async def test_blocked_source_cools_down_without_repeated_requests(status: int, body: str) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, text=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = KleinanzeigenWebProvider(WebProviderSettings(storage_file=None, request_interval_seconds=0), client)
        for _ in range(2):
            with pytest.raises(ProviderRateLimited):
                _ = [item async for item in provider.discover(SearchProfile(name="Test", query="pc"))]
        assert calls == 1


@pytest.mark.asyncio
async def test_retry_after_can_extend_the_default_cooldown() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(429, headers={"Retry-After": "3600"}))
    ) as client:
        provider = KleinanzeigenWebProvider(WebProviderSettings(storage_file=None), client)
        with pytest.raises(ProviderRateLimited) as error:
            _ = [item async for item in provider.discover(SearchProfile(name="Test", query="pc"))]
        assert error.value.retry_after_seconds == 3600


@pytest.mark.asyncio
async def test_web_source_is_opt_in() -> None:
    scheduler = Scheduler(SchedulerSettings(_env_file=None, kleinanzeigen_web_enabled=False))
    try:
        assert scheduler._web_provider is None
        assert await scheduler.sync_kleinanzeigen() == 0
    finally:
        await scheduler.client.aclose()


@pytest.mark.asyncio
async def test_details_enrich_and_cache_verified_cards_without_using_future_dates() -> None:
    detail_requests = 0
    detail_html = """<h1>Gaming PC RTX-4070</h1><p id="viewad-price">999,50 € VB</p>
    <div id="viewad-description-text">Vollständige Beschreibung mit 32 GB RAM</div>
    <time itemprop="datePosted" datetime="2099-01-01T00:00:00Z"></time>
    <meta itemprop="datePublished" content="2026-10-01T12:00:00+02:00">"""

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal detail_requests
        if "/s-anzeige/" in request.url.path:
            detail_requests += 1
            return httpx.Response(200, text=detail_html)
        return httpx.Response(200, text=HTML)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = KleinanzeigenWebProvider(
            WebProviderSettings(
                storage_file=None,
                request_interval_seconds=0,
                fetch_details=True,
            ),
            client,
        )
        profile = SearchProfile(name="Details", query="pc")
        first = [snapshot async for snapshot in provider.discover(profile)]
        second = [snapshot async for snapshot in provider.discover(profile)]
        assert first[0].payload["description"].startswith("Vollständige")
        assert (await provider.normalize(first[0])).published_at is not None
        assert first[0].payload["publishedAt"].startswith("2026-10-01")
        assert second[0].payload == first[0].payload
        assert detail_requests == 1
        with pytest.raises(ProviderError, match="verified"):
            await provider.fetch("https://evil.example/s-anzeige/gaming/1234567890-228-1234")


@pytest.mark.asyncio
async def test_radius_search_resolves_postal_code_and_caches_location() -> None:
    urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if request.url.path.endswith(".json"):
            return httpx.Response(200, json={"_0": "Deutschland", "_3331": "10115 Berlin"})
        return httpx.Response(200, text=HTML)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = KleinanzeigenWebProvider(WebProviderSettings(storage_file=None, request_interval_seconds=0), client)
        profile = SearchProfile(name="Local", query="pc", location="10115", radius_km=25)
        first = [snapshot async for snapshot in provider.discover(profile)]
        _ = [snapshot async for snapshot in provider.discover(profile)]
        assert first[0].payload["locationFilter"] == "10115"
        assert urls[1].endswith("/k0l3331r20")
        assert len([url for url in urls if ".json" in url]) == 1
        profile.location = None
        with pytest.raises(ProviderError, match="postal code"):
            _ = [snapshot async for snapshot in provider.discover(profile)]


@pytest.mark.asyncio
async def test_unknown_postal_code_never_falls_back_to_nationwide_search() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"_0": "Deutschland"}))
    ) as client:
        provider = KleinanzeigenWebProvider(WebProviderSettings(storage_file=None, request_interval_seconds=0), client)
        with pytest.raises(ProviderError, match="nationwide fallback refused"):
            _ = [
                snapshot
                async for snapshot in provider.discover(
                    SearchProfile(
                        name="Unknown",
                        query="pc",
                        location="99999",
                        radius_km=20,
                    )
                )
            ]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["browser", "stealth"])
async def test_optional_browser_transport_keeps_navigation_scoped_and_does_not_solve_challenges(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options: dict[str, object] = {}

    class FakeFetcher:
        @staticmethod
        def fetch(url: str, **kwargs: object) -> object:
            options.update(kwargs)
            return SimpleNamespace(url=url, body=HTML.encode(), status=200)

    monkeypatch.setitem(
        sys.modules,
        "scrapling.fetchers",
        SimpleNamespace(
            DynamicFetcher=FakeFetcher,
            StealthyFetcher=FakeFetcher,
        ),
    )
    provider = KleinanzeigenWebProvider(
        WebProviderSettings(
            storage_file=None,
            fetch_mode=mode,  # type: ignore[arg-type]
        )
    )
    try:
        snapshots = [item async for item in provider.discover(SearchProfile(name="Browser", query="pc"))]
        assert len(snapshots) == 1
        assert options["headless"] is True
        if mode == "stealth":
            assert options["solve_cloudflare"] is False
        handlers: list[object] = []
        page = SimpleNamespace(route=lambda pattern, handler: handlers.append(handler))
        options["page_setup"](page)  # type: ignore[operator]
        actions: list[str] = []
        route = SimpleNamespace(
            request=SimpleNamespace(url="https://evil.example/", method="GET"),
            continue_=lambda: actions.append("allowed"),
            abort=lambda: actions.append("blocked"),
        )
        handlers[0](route)  # type: ignore[operator]
        assert actions == ["blocked"]
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_oversized_response_is_rejected() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=HTML))
    ) as client:
        provider = KleinanzeigenWebProvider(WebProviderSettings(storage_file=None, maximum_response_bytes=10), client)
        with pytest.raises(ProviderError, match="size limit"):
            _ = [item async for item in provider.discover(SearchProfile(name="Test", query="pc"))]


@pytest.mark.asyncio
async def test_scheduler_imports_web_offers_records_run_and_respects_interval() -> None:
    profile_id = str(uuid4())
    profile = SearchProfile(id=profile_id, name="Gaming", query="pc", enabled_platforms=["kleinanzeigen"])
    imports: list[dict[str, object]] = []
    history: list[dict[str, object]] = []

    async def api(request: httpx.Request) -> httpx.Response:
        import json

        path = request.url.path
        if path == "/api/v1/provider-configurations":
            return httpx.Response(200, json=[])
        if path == "/api/v1/search-profiles":
            return httpx.Response(200, json=[profile.model_dump(mode="json")])
        if path == "/api/v1/provider-sync-runs" and request.method == "GET":
            assert request.url.params["provider"] == "kleinanzeigen"
            return httpx.Response(200, json={"items": history})
        if path == "/api/v1/provider-sync-runs" and request.method == "POST":
            return httpx.Response(201, json={"id": "run-1"})
        if path == "/api/v1/provider-sync-runs/run-1":
            body = json.loads(request.content)
            assert body["status"] == "COMPLETED"
            assert body["importedCount"] == 1
            history.append({**body, "completedAt": body["cursor"]})
            return httpx.Response(200, json=body)
        if path == "/api/v1/imports/manual":
            body = json.loads(request.content)
            assert body["platform"] == "kleinanzeigen"
            assert body["searchProfileId"] == profile_id
            assert body["price"] == "999.50"
            assert len(request.headers["Idempotency-Key"]) == 64
            imports.append(body)
            return httpx.Response(201, json={"snapshotCreated": True, "listing": {"id": "listing-1"}})
        if path == "/api/v1/listings/listing-1/images":
            return httpx.Response(201, json={})
        raise AssertionError(f"Unexpected API request {request.method} {path}")

    scheduler = Scheduler(SchedulerSettings(_env_file=None, kleinanzeigen_web_enabled=True))
    await scheduler.client.aclose()
    assert scheduler._web_provider is not None
    await scheduler._web_provider.close()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=HTML))) as web:
        scheduler._web_provider = KleinanzeigenWebProvider(
            WebProviderSettings(storage_file=None, request_interval_seconds=0), web
        )
        scheduler.client = httpx.AsyncClient(base_url="http://test", transport=httpx.MockTransport(api))
        try:
            assert await scheduler.sync_kleinanzeigen() == 1
            assert await scheduler.sync_kleinanzeigen() == 0
            assert len(imports) == 1
        finally:
            await scheduler.client.aclose()
