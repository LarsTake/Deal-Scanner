from __future__ import annotations

import math
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from .models import (
    DealScoreInput,
    DealScoreResult,
    MarketEstimate,
    ObservationKind,
    PriceObservation,
    RiskScoreResult,
    RiskSignal,
)


def _weighted_quantile(values: list[tuple[Decimal, float]], quantile: float) -> Decimal:
    ordered = sorted(values, key=lambda item: item[0])
    total_weight = sum(weight for _, weight in ordered)
    threshold = total_weight * quantile
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= threshold or math.isclose(cumulative, threshold, rel_tol=1e-9, abs_tol=1e-12):
            return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return ordered[-1][0].quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


class MarketValueEngine:
    calculation_version = "market-v1"
    half_life_days = 45.0
    kind_weights = {
        ObservationKind.SOLD_CONFIRMED: 1.0,
        ObservationKind.MANUAL_SOLD: 0.8,
        ObservationKind.ACTIVE: 0.35,
    }

    def estimate(self, observations: list[PriceObservation], *, now: datetime | None = None) -> MarketEstimate:
        current = now or datetime.now(UTC)
        usable = [observation for observation in observations if observation.price > 0]
        if not usable:
            return MarketEstimate(status="insufficientData", explanation=["Keine Vergleichsdaten."])

        totals = [
            (observation.price + observation.shipping_cost) / Decimal(str(observation.condition_factor))
            for observation in usable
        ]
        center = _median(totals)
        mad = _median([abs(value - center) for value in totals])
        filtered: list[tuple[PriceObservation, Decimal]] = []
        for observation, total in zip(usable, totals, strict=True):
            if mad == 0 or abs(total - center) <= mad * 3:
                filtered.append((observation, total))

        if len(filtered) < 3:
            return MarketEstimate(
                status="insufficientData",
                observation_count=len(filtered),
                data_quality_score=min(20, len(filtered) * 7),
                explanation=["Weniger als drei verwertbare Vergleichsdaten nach Ausreißerfilter."],
            )

        weighted: list[tuple[Decimal, float]] = []
        freshness_values: list[float] = []
        kinds: set[ObservationKind] = set()
        for observation, total in filtered:
            observed_at = observation.observed_at
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=UTC)
            age_days = max(0.0, (current - observed_at).total_seconds() / 86_400)
            freshness = math.exp(-math.log(2) * age_days / self.half_life_days)
            freshness_values.append(freshness)
            kinds.add(observation.kind)
            weight = self.kind_weights[observation.kind] * observation.source_quality * freshness
            weighted.append((total, max(weight, 0.001)))

        count_score = min(40.0, len(filtered) / 10 * 40)
        kind_score = max(self.kind_weights[kind] for kind in kinds) * 40
        freshness_score = sum(freshness_values) / len(freshness_values) * 20
        quality = round(count_score + kind_score + freshness_score)
        if kinds == {ObservationKind.ACTIVE}:
            quality = min(60, quality)

        return MarketEstimate(
            status="ready",
            minimum=_weighted_quantile(weighted, 0.25),
            median=_weighted_quantile(weighted, 0.50),
            maximum=_weighted_quantile(weighted, 0.75),
            observation_count=len(filtered),
            data_quality_score=max(0, min(100, quality)),
            explanation=[
                f"{len(filtered)} Vergleichsdaten nach MAD-Ausreißerfilter.",
                "Aktive Angebote sind geringer gewichtet als bestätigte Verkäufe.",
            ],
        )


class DealScoreEngine:
    calculation_version = "deal-v1"

    def score(self, value: DealScoreInput) -> DealScoreResult:
        if value.market.status != "ready" or value.market.median is None:
            return DealScoreResult(
                score=None,
                components={},
                explanation=["Deal-Score wegen unzureichender Marktdaten nicht belastbar."],
            )
        median = value.market.median
        advantage_percent = float((median - value.total_cost) / median * 100) if median else -100.0
        price_score = round(max(0.0, min(100.0, 50 + advantage_percent * 2)))
        components = {
            "priceAdvantage": price_score,
            "dataQuality": value.market.data_quality_score,
            "condition": value.condition_score,
            "completeness": value.completeness_score,
            "resale": value.resale_score,
            "relevance": value.relevance_score,
        }
        weighted_score = (
            price_score * 0.45
            + value.market.data_quality_score * 0.15
            + value.condition_score * 0.10
            + value.completeness_score * 0.10
            + value.resale_score * 0.10
            + value.relevance_score * 0.10
        )
        return DealScoreResult(
            score=round(max(0, min(100, weighted_score))),
            components=components,
            explanation=[
                f"Preisvorteil gegenüber Median: {advantage_percent:.1f}%.",
                "Risiko wird getrennt ausgewiesen und nicht in diesen Score eingerechnet.",
            ],
        )


class RiskScoreEngine:
    calculation_version = "risk-v1"

    def score(self, signals: list[RiskSignal]) -> RiskScoreResult:
        negative = sum(signal.weight * signal.confidence for signal in signals if not signal.positive)
        positive = min(
            25.0,
            sum(signal.weight * signal.confidence for signal in signals if signal.positive),
        )
        score = round(max(0.0, min(100.0, negative - positive)))
        return RiskScoreResult(
            score=score,
            negative_points=round(negative, 2),
            positive_reduction=round(positive, 2),
            signals=signals,
        )
