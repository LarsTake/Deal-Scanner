import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

os.environ["DEAL_SCANNER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEAL_SCANNER_AUTO_CREATE_DB"] = "true"
os.environ["DEAL_SCANNER_AUTH_MODE"] = "development"

from deal_scanner_api.db_models import DealEvaluationRow, ListingRow, ListingSnapshotRow
from deal_scanner_api.findings_service import listing_findings
from deal_scanner_api.main import app
from fastapi.testclient import TestClient


def snapshot(price: str, shipping: str = "0", currency: str = "EUR", *, offset: int = 0) -> ListingSnapshotRow:
    return ListingSnapshotRow(
        id=uuid4(),
        fetched_at=datetime.now(UTC) + timedelta(seconds=offset),
        raw_data={"normalizedInput": {"price": price, "shippingCost": shipping, "currency": currency}},
    )


def test_total_cost_change_includes_shipping_and_exact_snapshot_evidence() -> None:
    before, after = snapshot("100", "10"), snapshot("80", "20", offset=1)
    findings = listing_findings(ListingRow(current_snapshot_id=after.id), [after, before], None)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "priceDrop"
    assert finding.evidence["previousTotal"] == "110"
    assert finding.evidence["total"] == "100"
    assert finding.evidence["changePercent"] == "-9.1"
    assert finding.evidence["previousSnapshotId"] == str(before.id)
    assert finding.evidence["snapshotId"] == str(after.id)


@pytest.mark.parametrize(
    ("price", "shipping", "currency"), [("90", "20", "EUR"), ("80", "0", "USD"), ("NaN", "0", "EUR")]
)
def test_no_misleading_price_drop_for_equal_totals_currency_switch_or_invalid_data(
    price: str,
    shipping: str,
    currency: str,
) -> None:
    before, after = snapshot("100", "10"), snapshot(price, shipping, currency, offset=1)
    assert listing_findings(ListingRow(current_snapshot_id=after.id), [before, after], None) == []


def test_zero_price_baseline_never_divides_by_zero() -> None:
    before, after = snapshot("0"), snapshot("100", offset=1)
    finding = listing_findings(ListingRow(current_snapshot_id=after.id), [before, after], None)[0]
    assert finding.kind == "priceIncrease"
    assert finding.evidence["changePercent"] is None


@pytest.mark.parametrize(("quality", "stale", "expected"), [(60, False, True), (59, False, False), (90, True, False)])
def test_market_deviation_needs_current_qualified_evidence(quality: int, stale: bool, expected: bool) -> None:
    current = snapshot("600")
    listing = ListingRow(
        current_snapshot_id=current.id, price=Decimal("600"), shipping_cost=Decimal("0"), currency="EUR"
    )
    evaluation = DealEvaluationRow(
        id=uuid4(),
        data_quality_score=quality,
        risk_score=0,
        estimated_market_value_median=Decimal("1000"),
        calculation_version="deal-v1+market-v1+comparability-v1",
        explanation={},
        created_at=current.fetched_at + timedelta(seconds=-1 if stale else 1),
    )
    findings = listing_findings(listing, [current], evaluation)
    assert bool(findings) is expected
    assert evaluation.risk_score == 0
    if expected:
        assert findings[0].kind == "marketDeviation"
        assert findings[0].evidence["deviationPercent"] == "-40.0"
        assert "kein Betrugsnachweis" in findings[0].description


def test_price_reversion_is_new_snapshot_and_unchanged_retry_is_idempotent() -> None:
    body = {
        "platform": "kleinanzeigen",
        "externalId": "price-reversion",
        "url": "https://www.kleinanzeigen.de/s-anzeige/gpu/1234567890-228-1234",
        "title": "RTX 4070 Super",
        "description": "Abholung möglich",
        "price": "100",
        "shippingCost": "5",
        "currency": "EUR",
        "categoryProfile": "computer",
    }
    with TestClient(app, headers={"X-Development-User": "00000000-0000-4000-8000-000000000930"}) as client:
        first = client.post("/api/v1/imports/manual", json=body).json()
        body["price"] = "80"
        second = client.post("/api/v1/imports/manual", json=body).json()
        body["price"] = "100"
        reverted_response = client.post("/api/v1/imports/manual", json=body)
        assert reverted_response.status_code == 201, reverted_response.text
        reverted = reverted_response.json()
        assert reverted["snapshotCreated"] is True
        assert reverted["analysisJobId"] not in {first["analysisJobId"], second["analysisJobId"]}
        assert reverted["listing"]["price"] == "100.00"
        assert len(reverted["listing"]["snapshots"]) == 3
        assert [finding["kind"] for finding in reverted["listing"]["findings"]] == ["priceIncrease", "priceDrop"]
        assert reverted["listing"]["riskScore"] == first["listing"]["riskScore"]
        retry = client.post("/api/v1/imports/manual", json=body).json()
        assert retry["snapshotCreated"] is False
        assert retry["analysisJobId"] is None
        assert len(retry["listing"]["findings"]) == 2
        body["currency"] = "USD"
        changed = client.post("/api/v1/imports/manual", json=body).json()
        assert changed["listing"]["currency"] == "USD"
        assert len(changed["listing"]["findings"]) == 2
        assert client.get("/api/v1/notifications").json() == []
