"""Descriptive findings, deliberately separate from fraud/risk scoring and push delivery."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from itertools import pairwise

from .comparison_service import COMPARISON_VERSION
from .db_models import DealEvaluationRow, ListingRow, ListingSnapshotRow
from .schemas import ListingFindingResponse

FINDINGS_VERSION = "listing-findings-v1"
MARKET_DEVIATION_PERCENT = Decimal("40")
MINIMUM_MARKET_QUALITY = 60


def _money(value: object) -> Decimal | None:
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def _time(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def listing_findings(
    listing: ListingRow,
    snapshots: list[ListingSnapshotRow],
    evaluation: DealEvaluationRow | None,
) -> list[ListingFindingResponse]:
    findings: list[ListingFindingResponse] = []
    ordered = sorted(snapshots, key=lambda row: (_time(row.fetched_at), str(row.id)))
    for before, after in pairwise(ordered):
        old = before.raw_data.get("normalizedInput", {})
        new = after.raw_data.get("normalizedInput", {})
        old_price, new_price = _money(old.get("price")), _money(new.get("price"))
        old_shipping, new_shipping = _money(old.get("shippingCost")), _money(new.get("shippingCost"))
        currency = old.get("currency")
        if (
            currency is None
            or currency != new.get("currency")
            or any(value is None for value in (old_price, new_price, old_shipping, new_shipping))
        ):
            continue
        assert old_price is not None and new_price is not None
        assert old_shipping is not None and new_shipping is not None
        previous, current = old_price + old_shipping, new_price + new_shipping
        if previous == current:
            continue
        delta = current - previous
        percent = (delta / previous * 100).quantize(Decimal("0.1")) if previous else None
        direction = "gesunken" if delta < 0 else "gestiegen"
        findings.append(
            ListingFindingResponse(
                id=f"price:{before.id}:{after.id}",
                kind="priceDrop" if delta < 0 else "priceIncrease",
                title=f"Gesamtpreis {direction}",
                observed_at=after.fetched_at,
                source=FINDINGS_VERSION,
                description=f"Von {previous:.2f} auf {current:.2f} {currency}, einschließlich erfasster Versandkosten. "
                "Beobachtete Angebotspreise, kein nachgewiesener Verkauf.",
                evidence={
                    "previousSnapshotId": str(before.id),
                    "snapshotId": str(after.id),
                    "previousPrice": str(old_price),
                    "price": str(new_price),
                    "previousShippingCost": str(old_shipping),
                    "shippingCost": str(new_shipping),
                    "previousTotal": str(previous),
                    "total": str(current),
                    "currency": currency,
                    "delta": str(delta),
                    "changePercent": str(percent) if percent is not None else None,
                },
            )
        )
    # Historical evaluations do not describe the current price after a new import.
    latest_snapshot = next((row for row in snapshots if row.id == listing.current_snapshot_id), None)
    current_evaluation = (
        evaluation is not None
        and latest_snapshot is not None
        and _time(evaluation.created_at) >= _time(latest_snapshot.fetched_at)
        and evaluation.calculation_version.endswith(f"+{COMPARISON_VERSION}")
    )
    if current_evaluation:
        assert evaluation is not None
        median = evaluation.estimated_market_value_median
        total = listing.price + listing.shipping_cost
        if median is not None and median > 0 and evaluation.data_quality_score >= MINIMUM_MARKET_QUALITY:
            deviation = (total - median) / median * 100
            if abs(deviation) >= MARKET_DEVIATION_PERCENT:
                findings.append(
                    ListingFindingResponse(
                        id=f"market:{evaluation.id}",
                        kind="marketDeviation",
                        title="Starke Preisabweichung",
                        description=f"Gesamtpreis {abs(deviation):.1f}% {'unter' if deviation < 0 else 'über'} "
                        "dem Vergleichsmedian. Anlass zur Prüfung, kein Betrugsnachweis.",
                        observed_at=evaluation.created_at,
                        source=FINDINGS_VERSION,
                        evidence={
                            "evaluationId": str(evaluation.id),
                            "snapshotId": str(listing.current_snapshot_id),
                            "total": str(total),
                            "median": str(median),
                            "currency": listing.currency,
                            "deviationPercent": str(deviation.quantize(Decimal("0.1"))),
                            "thresholdPercent": str(MARKET_DEVIATION_PERCENT),
                            "minimumDataQuality": MINIMUM_MARKET_QUALITY,
                            "dataQuality": evaluation.data_quality_score,
                            "calculationVersion": evaluation.calculation_version,
                            "comparisonExplanation": evaluation.explanation.get("market", {}).get("explanation", []),
                        },
                    )
                )
    return sorted(findings, key=lambda item: (_time(item.observed_at), item.id), reverse=True)[:20]
