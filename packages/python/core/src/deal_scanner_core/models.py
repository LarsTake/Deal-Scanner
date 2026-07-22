from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )


class ListingStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    FETCHED = "FETCHED"
    NORMALIZED = "NORMALIZED"
    RULE_ANALYZED = "RULE_ANALYZED"
    TEXT_ANALYZED = "TEXT_ANALYZED"
    IMAGE_ANALYZED = "IMAGE_ANALYZED"
    PRICE_EVALUATED = "PRICE_EVALUATED"
    READY = "READY"
    FAILED = "FAILED"
    REMOVED = "REMOVED"


class AnalysisStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class Money(CamelModel):
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="EUR", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value, "f")


class SearchProfile(CamelModel):
    id: UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=100)
    category_profile: str = Field(default="general", max_length=64)
    enabled_platforms: list[str] = Field(default_factory=lambda: ["ebay"])
    minimum_price: Decimal | None = Field(default=None, ge=0)
    maximum_price: Decimal | None = Field(default=None, ge=0)
    required_terms: list[str] = Field(default_factory=list)
    excluded_terms: list[str] = Field(default_factory=list)
    minimum_deal_score: int = Field(default=75, ge=0, le=100)
    maximum_risk_score: int = Field(default=45, ge=0, le=100)
    scan_interval_minutes: int = Field(default=15, ge=5, le=10_080)
    enabled: bool = True


class RawListingSnapshot(CamelModel):
    platform: str = Field(min_length=1, max_length=32)
    external_id: str = Field(min_length=1, max_length=255)
    source_url: HttpUrl
    fetched_at: datetime
    payload: dict[str, Any]
    provider_version: str = Field(min_length=1, max_length=64)


class NormalizedListing(CamelModel):
    platform: str
    external_id: str
    url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=100_000)
    price: Money
    shipping_cost: Money | None = None
    location: str | None = Field(default=None, max_length=255)
    seller_external_id: str | None = Field(default=None, max_length=255)
    published_at: datetime | None = None
    category_profile: str = "general"
    raw_snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class TextAnalysisRequest(CamelModel):
    listing_id: UUID
    title: str
    description: str
    category_profile: str
    schema_version: str = "1.0.0"


class ProductDetection(CamelModel):
    product_type: str
    manufacturer: str | None = None
    model: str
    variant: str | None = None
    quantity: int = Field(default=1, ge=1)
    confidence: float = Field(ge=0, le=1)
    sources: list[str]
    evidence: str


class TextAnalysisResult(CamelModel):
    category: str
    products: list[ProductDetection]
    attributes: list[dict[str, Any]] = Field(default_factory=list)
    risk_signals: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0, le=1)
    schema_version: str = "1.0.0"


class ImageOcrResult(CamelModel):
    image_id: UUID
    text: str = Field(max_length=100_000)
    language: str | None = Field(default=None, max_length=32)
    confidence: float = Field(ge=0, le=1)
    engine: str = Field(min_length=1, max_length=64)
    schema_version: str = "1.0.0"


class ModelProviderStatus(CamelModel):
    available: bool
    provider: str
    models: list[str] = Field(default_factory=list)
    detail: str | None = None
