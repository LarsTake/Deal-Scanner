from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from deal_scanner_core.models import CamelModel
from pydantic import Field


class ObservationKind(StrEnum):
    SOLD_CONFIRMED = "soldConfirmed"
    MANUAL_SOLD = "manualSold"
    ACTIVE = "active"


class PriceObservation(CamelModel):
    price: Decimal = Field(gt=0)
    shipping_cost: Decimal = Field(default=Decimal("0"), ge=0)
    observed_at: datetime
    kind: ObservationKind
    source_quality: float = Field(default=1.0, ge=0, le=1)
    condition_factor: float = Field(default=1.0, gt=0, le=2)


class MarketEstimate(CamelModel):
    status: str
    minimum: Decimal | None = None
    median: Decimal | None = None
    maximum: Decimal | None = None
    observation_count: int = 0
    data_quality_score: int = Field(default=0, ge=0, le=100)
    calculation_version: str = "market-v1"
    explanation: list[str] = Field(default_factory=list)


class DealScoreInput(CamelModel):
    total_cost: Decimal = Field(ge=0)
    market: MarketEstimate
    condition_score: int = Field(default=50, ge=0, le=100)
    completeness_score: int = Field(default=50, ge=0, le=100)
    resale_score: int = Field(default=50, ge=0, le=100)
    relevance_score: int = Field(default=50, ge=0, le=100)


class DealScoreResult(CamelModel):
    score: int | None
    components: dict[str, int]
    calculation_version: str = "deal-v1"
    explanation: list[str]


class RiskSignal(CamelModel):
    type: str
    weight: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    evidence: str
    positive: bool = False
    source: str


class RiskScoreResult(CamelModel):
    score: int = Field(ge=0, le=100)
    negative_points: float
    positive_reduction: float
    calculation_version: str = "risk-v1"
    signals: list[RiskSignal]
