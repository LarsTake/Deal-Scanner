from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from deal_scanner_core.models import SearchProfile
from deal_scanner_ebay import EbayProvider, EbaySettings
from deal_scanner_email import KleinanzeigenMailParser
from deal_scanner_manual import extract_ebay_legacy_id
from deal_scanner_scheduler.main import Scheduler


def test_ebay_id_is_extracted_only_from_allowed_https_url() -> None:
    assert extract_ebay_legacy_id("https://www.ebay.de/itm/RTX-4070/123456789012") == "123456789012"
    assert extract_ebay_legacy_id("http://www.ebay.de/itm/123456789012") is None
    assert extract_ebay_legacy_id("https://evil.example/itm/123456789012") is None


def test_kleinanzeigen_mail_parser() -> None:
    raw = Path("tests/fixtures/email/kleinanzeigen.eml").read_bytes()
    parsed = KleinanzeigenMailParser({"kleinanzeigen.de"}).parse(raw)
    assert parsed.price == "499.00"
    assert parsed.listing_url == "https://www.kleinanzeigen.de/s-anzeige/gaming-pc/1234567890-228-1234"
    assert parsed.needs_recheck is False


def test_unknown_mail_sender_is_rejected() -> None:
    raw = (
        Path("tests/fixtures/email/kleinanzeigen.eml")
        .read_bytes()
        .replace(b"newsletter@kleinanzeigen.de", b"attacker@example.com")
    )
    with pytest.raises(ValueError, match="sender"):
        KleinanzeigenMailParser({"kleinanzeigen.de"}).parse(raw)


def test_sender_domain_substring_does_not_bypass_allowlist() -> None:
    raw = (
        Path("tests/fixtures/email/kleinanzeigen.eml")
        .read_bytes()
        .replace(b"newsletter@kleinanzeigen.de", b"attacker@kleinanzeigen.de.evil.example")
    )
    with pytest.raises(ValueError, match="sender"):
        KleinanzeigenMailParser({"kleinanzeigen.de"}).parse(raw)


def test_scheduler_applies_required_and_excluded_profile_filters() -> None:
    profile = SearchProfile(
        name="Filtered",
        query="Simracing",
        required_terms=["boost kit"],
        excluded_terms=["defekt"],
        required_products=["QR2"],
    )
    assert Scheduler._matches_profile(profile, "Fanatec QR2 Bundle", "Mit Boost Kit")
    assert not Scheduler._matches_profile(profile, "Fanatec QR2 Bundle", "Ohne Boost Kit, defekt")
    assert not Scheduler._matches_profile(profile, "Fanatec QR1 Bundle", "Mit Boost Kit")

    local_profile = profile.model_copy(update={"location": "Hamburg", "radius_km": 25})
    assert Scheduler._matches_profile(local_profile, "Fanatec QR2 Bundle", "Mit Boost Kit", "Hamburg", 12)
    assert not Scheduler._matches_profile(local_profile, "Fanatec QR2 Bundle", "Mit Boost Kit", "Berlin", 12)
    assert not Scheduler._matches_profile(local_profile, "Fanatec QR2 Bundle", "Mit Boost Kit", "Hamburg", 40)


@pytest.mark.asyncio
async def test_ebay_delta_cursor_uses_overlap_and_stops_at_known_items() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["sort"] == "newlyListed"
        assert request.url.params["offset"] == "0"
        return httpx.Response(
            200,
            json={
                "itemSummaries": [
                    {
                        "itemId": "v1|new|0",
                        "legacyItemId": "111111111111",
                        "itemWebUrl": "https://www.ebay.de/itm/111111111111",
                        "itemCreationDate": "2026-07-22T12:01:00.000Z",
                    },
                    {
                        "itemId": "v1|known|0",
                        "legacyItemId": "222222222222",
                        "itemWebUrl": "https://www.ebay.de/itm/222222222222",
                        "itemCreationDate": "2026-07-22T11:50:00.000Z",
                    },
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = EbayProvider(EbaySettings(client_id="id", client_secret="fixture"), client)  # noqa: S106
    provider._access_token = "fixture"  # noqa: S105
    provider._token_expires_at = datetime.now(UTC) + timedelta(hours=1)
    discovered = [
        snapshot
        async for snapshot in provider.discover(
            SearchProfile(name="GPU", query="RTX 4070 Super"),
            "2026-07-22T12:00:00Z",
        )
    ]
    await client.aclose()
    assert [snapshot.external_id for snapshot in discovered] == ["111111111111"]
