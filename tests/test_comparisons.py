import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID

import pytest

os.environ["DEAL_SCANNER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DEAL_SCANNER_AUTO_CREATE_DB"] = "true"
os.environ["DEAL_SCANNER_AUTH_MODE"] = "development"

from deal_scanner_api.comparison_service import condition_group
from deal_scanner_api.database import session_factory
from deal_scanner_api.db_models import DealEvaluationRow, PriceObservationRow
from deal_scanner_api.main import app
from deal_scanner_api.product_service import _resolve_canonical_product, canonicalize_detection
from deal_scanner_core.models import ProductDetection
from fastapi.testclient import TestClient
from sqlalchemy import select


def offer(client: TestClient, key: str, title: str = "NVIDIA RTX 4070 Super", price: str = "500") -> dict:
    response = client.post(
        "/api/v1/imports/manual",
        json={
            "platform": "kleinanzeigen",
            "externalId": key,
            "url": f"https://www.kleinanzeigen.de/s-anzeige/{key}/1234567890-228-1234",
            "title": title,
            "description": "Abholung möglich",
            "price": price,
            "categoryProfile": "computer",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["listing"]


def test_own_repeated_snapshots_are_not_market_evidence() -> None:
    with TestClient(app) as client:
        for index in range(5):
            listing = offer(client, "self-history", price=str(500 + index))
        result = client.get(f"/api/v1/listings/{listing['id']}/market-value").json()
        assert result["status"] == "insufficientData"
        assert result["observationCount"] == 0
        assert any("5 × eigene Angebotshistorie" in text for text in result["explanation"])
        assert client.get(f"/api/v1/listings/{listing['id']}").json()["comparisonObservations"] == []


def test_one_source_counts_once_and_bundles_never_supply_gpu_prices() -> None:
    with TestClient(app) as client:
        target = offer(client, "target")
        for price in ("600", "610", "620", "630"):
            offer(client, "one-source", price=price)
        pc = offer(client, "whole-pc", "Gaming PC RTX 4070 Super", "1800")
        bundle = offer(client, "bundle", "RTX 4070 Super Bundle", "1500")
        product_id = target["products"][0]["canonicalProductId"]

        async def simulate_legacy_pollution() -> None:
            async with session_factory() as session:
                rows = (
                    await session.scalars(
                        select(PriceObservationRow).where(
                            PriceObservationRow.listing_id.in_([UUID(pc["id"]), UUID(bundle["id"])])
                        )
                    )
                ).all()
                assert all(row.canonical_product_id is None for row in rows)
                for row in rows:
                    row.canonical_product_id = UUID(product_id)
                await session.commit()

        asyncio.run(simulate_legacy_pollution())
        result = client.get(f"/api/v1/listings/{target['id']}/market-value").json()
        assert result["status"] == "insufficientData"
        assert result["observationCount"] == 1
        assert any("3 × wiederholter Preisstand" in text for text in result["explanation"])
        assert any("2 × abweichender oder unklarer Angebotsumfang" in text for text in result["explanation"])
        compared = client.get(f"/api/v1/listings/{target['id']}").json()["comparisonObservations"]
        assert len(compared) == 1
        assert compared[0]["observedPrice"] == "630.00"
        # Component reference sales must not value an entire PC.
        for price in ("900", "950", "1000"):
            assert (
                client.post(
                    "/api/v1/price-observations",
                    json={
                        "canonicalProductId": product_id,
                        "platform": "manual",
                        "observedPrice": price,
                        "observationKind": "soldConfirmed",
                        "observedAt": datetime.now(UTC).isoformat(),
                    },
                ).status_code
                == 201
            )
        assert client.get(f"/api/v1/listings/{pc['id']}/market-value").json()["status"] == "insufficientData"
        assert client.get(f"/api/v1/listings/{target['id']}/market-value").json()["status"] == "ready"


def test_known_different_conditions_are_not_mixed() -> None:
    with TestClient(app) as client:
        target = offer(client, "used-target", "RTX 4070 Super gebraucht")
        for index, title in enumerate(("RTX 4070 Super neu", "RTX 4070 Super defekt", "RTX 4070 Super")):
            offer(client, f"condition-{index}", title)
        offer(client, "used-source", "RTX 4070 Super gebraucht")
        result = client.get(f"/api/v1/listings/{target['id']}/market-value").json()
        assert result["observationCount"] == 1
        assert any("3 × abweichender oder unklarer Zustand" in text for text in result["explanation"])


def test_zero_prices_are_excluded_without_breaking_evaluation() -> None:
    with TestClient(app) as client:
        target = offer(client, "paid-target")
        offer(client, "free-or-placeholder", price="0")
        result = client.post(f"/api/v1/listings/{target['id']}/evaluate")
        assert result.status_code == 200, result.text
        assert result.json()["market"]["observationCount"] == 0
        assert any("kein positiver belastbarer Preis" in text for text in result.json()["market"]["explanation"])


def test_legacy_scores_remain_history_but_are_not_current_top_deals() -> None:
    with TestClient(app) as client:
        target = offer(client, "legacy-score")

        async def seed() -> None:
            async with session_factory() as session:
                session.add(
                    DealEvaluationRow(
                        workspace_id=UUID(target["workspaceId"]),
                        listing_id=UUID(target["id"]),
                        deal_score=100,
                        risk_score=5,
                        data_quality_score=100,
                        estimated_market_value_median=1000,
                        calculation_version="deal-v1+risk-v1+market-v1",
                        explanation={},
                        created_at=datetime.now(UTC),
                    )
                )
                await session.commit()

        asyncio.run(seed())
        detail = client.get(f"/api/v1/listings/{target['id']}").json()
        assert detail["dealScore"] is None
        assert detail["marketValueMedian"] is None
        assert detail["riskScore"] == 5
        assert detail["evaluations"][0]["dealScore"] == 100
        assert any("neu bewerten" in warning for warning in detail["warnings"])
        assert client.get("/api/v1/listings?assessment=interesting").json()["items"] == []
        assert len(client.get("/api/v1/listings?assessment=unknown").json()["items"]) == 1


def test_variants_survive_canonicalization_and_do_not_share_alias_identity() -> None:
    with TestClient(app) as client:
        listing = offer(client, "variants")
        detection = ProductDetection(
            product_type="gpu",
            manufacturer="NVIDIA",
            model="RTX 4070S",
            variant="12 GB OC",
            quantity=1,
            confidence=1,
            evidence="Titel RTX 4070S",
            sources=["title"],
        )
        canonical = canonicalize_detection(detection)
        assert canonical.model == "RTX 4070 Super"
        assert canonical.variant == "12 GB OC"

        async def resolve() -> None:
            async with session_factory() as session:
                first = await _resolve_canonical_product(session, UUID(listing["workspaceId"]), "computer", canonical)
                second = await _resolve_canonical_product(
                    session,
                    UUID(listing["workspaceId"]),
                    "computer",
                    canonical.model_copy(update={"variant": "12 GB non-OC"}),
                )
                assert first.id != second.id
                await session.commit()

        asyncio.run(resolve())


@pytest.mark.parametrize(
    ("text", "group"), [("neuwertig", "used"), ("neu ungeöffnet", "new"), ("ungetestet", "damaged"), (None, "unknown")]
)
def test_condition_groups(text: str | None, group: str) -> None:
    assert condition_group(text) == group
