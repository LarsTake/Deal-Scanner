from pathlib import Path

import pytest
from deal_scanner_email import KleinanzeigenMailParser
from deal_scanner_manual import extract_ebay_legacy_id


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
