from datetime import UTC, datetime, timedelta
from decimal import Decimal

from deal_scanner_scoring import (
    DealScoreEngine,
    DealScoreInput,
    MarketValueEngine,
    PriceObservation,
    RiskScoreEngine,
    RiskSignal,
)


def observation(price: str, kind: str = "active", days: int = 0) -> PriceObservation:
    return PriceObservation(
        price=Decimal(price),
        observed_at=datetime.now(UTC) - timedelta(days=days),
        kind=kind,
    )


def test_market_value_requires_three_observations() -> None:
    estimate = MarketValueEngine().estimate([observation("500"), observation("520")])
    assert estimate.status == "insufficientData"
    assert estimate.median is None


def test_active_only_market_quality_is_capped_and_outlier_is_removed() -> None:
    estimate = MarketValueEngine().estimate(
        [
            observation("490"),
            observation("500"),
            observation("510"),
            observation("505"),
            observation("5000"),
        ]
    )
    assert estimate.status == "ready"
    assert estimate.median == Decimal("500.00")
    assert estimate.data_quality_score <= 60
    assert estimate.observation_count == 4


def test_sold_data_can_raise_quality_above_active_cap() -> None:
    estimate = MarketValueEngine().estimate([observation(str(price), "soldConfirmed") for price in range(450, 550, 10)])
    assert estimate.status == "ready"
    assert estimate.data_quality_score > 60


def test_deal_score_is_independent_of_risk_score() -> None:
    market = MarketValueEngine().estimate(
        [
            observation("900", "manualSold"),
            observation("950", "manualSold"),
            observation("1000", "manualSold"),
        ]
    )
    deal = DealScoreEngine().score(
        DealScoreInput(
            total_cost=Decimal("400"),
            market=market,
            condition_score=90,
            completeness_score=90,
            resale_score=90,
            relevance_score=90,
        )
    )
    risk = RiskScoreEngine().score(
        [
            RiskSignal(
                type="external_payment_link",
                weight=90,
                confidence=1,
                evidence="payment link",
                source="description",
            )
        ]
    )
    assert deal.score is not None and deal.score >= 80
    assert risk.score == 90


def test_positive_risk_signals_have_capped_reduction() -> None:
    result = RiskScoreEngine().score(
        [
            RiskSignal(type="warning", weight=50, confidence=1, evidence="x", source="text"),
            RiskSignal(type="pickup", weight=100, confidence=1, evidence="y", source="text", positive=True),
        ]
    )
    assert result.positive_reduction == 25
    assert result.score == 25
