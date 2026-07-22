from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from deal_scanner_core.models import CamelModel
from pydantic import Field, HttpUrl, field_serializer, model_validator


class WorkspaceResponse(CamelModel):
    id: UUID
    name: str
    role: str


class ProblemDetails(CamelModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    errors: list[dict[str, Any]] | None = None


class AuthMeResponse(CamelModel):
    user_id: UUID
    email: str | None
    workspaces: list[WorkspaceResponse]


class NotificationSettings(CamelModel):
    minimum_market_advantage_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    maximum_listing_age_hours: int | None = Field(default=None, ge=1, le=8_760)
    desktop_enabled: bool = True
    ntfy_enabled: bool = False


class SearchProfileCreate(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=100)
    category_profile: Literal["computer", "simracing", "fpv", "general"] = "general"
    enabled_platforms: list[str] = Field(default_factory=lambda: ["ebay"])
    minimum_price: Decimal | None = Field(default=None, ge=0)
    maximum_price: Decimal | None = Field(default=None, ge=0)
    location: str | None = Field(default=None, max_length=255)
    radius_km: int | None = Field(default=None, ge=0, le=1_000)
    required_terms: list[str] = Field(default_factory=list)
    excluded_terms: list[str] = Field(default_factory=list)
    required_products: list[str] = Field(default_factory=list)
    excluded_products: list[str] = Field(default_factory=list)
    minimum_deal_score: int = Field(default=75, ge=0, le=100)
    maximum_risk_score: int = Field(default=45, ge=0, le=100)
    notification_settings: NotificationSettings = Field(default_factory=NotificationSettings)
    scan_interval_minutes: int = Field(default=15, ge=5, le=10_080)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_prices(self) -> SearchProfileCreate:
        if (
            self.minimum_price is not None
            and self.maximum_price is not None
            and self.minimum_price > self.maximum_price
        ):
            raise ValueError("minimumPrice must not exceed maximumPrice")
        return self


class SearchProfileResponse(SearchProfileCreate):
    id: UUID
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime

    @field_serializer("minimum_price", "maximum_price")
    def serialize_optional_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None


class SellerInput(CamelModel):
    external_id: str = Field(min_length=1, max_length=255)
    display_name: str | None = Field(default=None, max_length=255)
    account_age_text: str | None = Field(default=None, max_length=255)
    account_created_at: datetime | None = None
    rating_text: str | None = Field(default=None, max_length=255)
    rating_score: Decimal | None = Field(default=None, ge=0, le=100)
    review_count: int | None = Field(default=None, ge=0)
    location: str | None = Field(default=None, max_length=255)
    raw_data: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("rating_score")
    def serialize_rating(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None


class SellerResponse(SellerInput):
    id: UUID
    platform: str
    first_seen_at: datetime
    last_seen_at: datetime


class ManualImportRequest(CamelModel):
    platform: Literal["ebay", "kleinanzeigen", "manual"]
    external_id: str = Field(min_length=1, max_length=255)
    url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=100_000)
    price: Decimal = Field(ge=0)
    shipping_cost: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")
    location: str | None = Field(default=None, max_length=255)
    category_profile: Literal["computer", "simracing", "fpv", "general"] = "general"
    published_at: datetime | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
    provider_version: str = "manual-v1"
    search_profile_id: UUID | None = None
    seller: SellerInput | None = None


class RiskSignalResponse(CamelModel):
    type: str
    severity: int
    confidence: float
    positive: bool
    source: str
    evidence: str


class ProductAttributeResponse(CamelModel):
    id: UUID
    attribute_key: str
    value: str | Decimal | bool
    unit: str | None
    confidence: float
    source: str


class ListingProductResponse(CamelModel):
    id: UUID
    canonical_product_id: UUID | None
    product_type: str
    manufacturer: str | None
    model: str
    variant: str | None
    quantity: int
    confidence: float
    detection_source: str
    evidence: str
    created_at: datetime
    attributes: list[ProductAttributeResponse] = Field(default_factory=list)


class ListingSnapshotResponse(CamelModel):
    id: UUID
    content_hash: str
    raw_data: dict[str, Any]
    provider_version: str
    fetched_at: datetime
    created_at: datetime


class AnalysisResultResponse(CamelModel):
    id: UUID
    analysis_type: str
    model_name: str
    model_version: str
    prompt_version: str
    result_schema_version: str
    result: dict[str, Any]
    confidence: float
    created_at: datetime


class DealEvaluationHistoryResponse(CamelModel):
    id: UUID
    market_value_minimum: Decimal | None
    market_value_median: Decimal | None
    market_value_maximum: Decimal | None
    expected_resale_value: Decimal | None
    estimated_margin: Decimal | None
    deal_score: int | None
    risk_score: int
    data_quality_score: int
    relevance_score: int
    explanation: dict[str, Any]
    calculation_version: str
    created_at: datetime

    @field_serializer(
        "market_value_minimum",
        "market_value_median",
        "market_value_maximum",
        "expected_resale_value",
        "estimated_margin",
    )
    def serialize_history_decimal(self, value: Decimal | None) -> str | None:
        return format(value, "f") if value is not None else None


class FeedbackResponse(CamelModel):
    id: UUID
    feedback_type: str
    corrected_products: list[dict[str, Any]] | None
    corrected_attributes: list[dict[str, Any]] | None
    corrected_value: dict[str, Any] | None
    note: str | None
    base_listing_version: int
    created_at: datetime


class ListingSummary(CamelModel):
    id: UUID
    workspace_id: UUID
    platform: str
    external_id: str
    url: str
    title: str
    price: Decimal
    shipping_cost: Decimal
    currency: str
    status: str
    analysis_status: str
    is_favorite: bool
    is_hidden: bool
    version: int
    last_seen_at: datetime
    deal_score: int | None = None
    risk_score: int | None = None

    @field_serializer("price", "shipping_cost")
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")


class ListingDetail(ListingSummary):
    description: str
    location: str | None
    category_profile: str
    current_snapshot_id: UUID | None
    risk_signals: list[RiskSignalResponse] = Field(default_factory=list)
    products: list[ListingProductResponse] = Field(default_factory=list)
    snapshots: list[ListingSnapshotResponse] = Field(default_factory=list)
    analysis_results: list[AnalysisResultResponse] = Field(default_factory=list)
    evaluations: list[DealEvaluationHistoryResponse] = Field(default_factory=list)
    feedback: list[FeedbackResponse] = Field(default_factory=list)
    seller: SellerResponse | None = None


class CorrectedProductInput(CamelModel):
    product_type: str = Field(min_length=1, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str = Field(min_length=1, max_length=255)
    variant: str | None = Field(default=None, max_length=255)
    quantity: int = Field(default=1, ge=1, le=100)
    evidence: str = Field(default="Manuelle Nutzerkorrektur", min_length=1, max_length=2_000)


class CorrectedAttributeInput(CamelModel):
    product_index: int = Field(default=0, ge=0, le=99)
    key: str = Field(min_length=1, max_length=255)
    value: str | Decimal | bool
    unit: str | None = Field(default=None, max_length=64)


class ImportResponse(CamelModel):
    listing: ListingDetail
    snapshot_created: bool
    analysis_job_id: UUID | None


class FeedbackCreate(CamelModel):
    feedback_type: Literal[
        "purchased",
        "sold",
        "tooExpensive",
        "goodDeal",
        "irrelevant",
        "incorrectDetection",
        "scamConcern",
        "incorrectMarketValue",
        "correctedComponents",
        "favorite",
        "unfavorite",
        "hide",
        "unhide",
    ]
    base_listing_version: int = Field(ge=1)
    corrected_products: list[CorrectedProductInput] | None = Field(default=None, max_length=100)
    corrected_attributes: list[CorrectedAttributeInput] | None = Field(default=None, max_length=500)
    corrected_value: dict[str, Any] | None = None
    note: str | None = Field(default=None, max_length=2_000)


class WorkerRegistration(CamelModel):
    name: str = Field(min_length=1, max_length=120)
    operating_system: str
    hostname: str
    cpu: str | None = None
    ram_gb: Decimal | None = Field(default=None, ge=0)
    gpu: str | None = None
    vram_gb: Decimal | None = Field(default=None, ge=0)
    runtime: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[str] = Field(min_length=1)
    installed_models: list[str] = Field(default_factory=list)


class WorkerResponse(WorkerRegistration):
    id: UUID
    last_heartbeat_at: datetime
    enabled: bool


class WorkerHeartbeat(CamelModel):
    current_load: float = Field(ge=0, le=1)
    capabilities: list[str] | None = None
    installed_models: list[str] | None = None


class JobClaimRequest(CamelModel):
    worker_id: UUID
    capabilities: list[str] = Field(min_length=1)


class JobResponse(CamelModel):
    id: UUID
    listing_id: UUID
    snapshot_id: UUID
    job_type: str
    required_capability: str
    input_hash: str
    priority: int
    status: str
    lease_expires_at: datetime | None
    attempts: int
    payload: dict[str, Any] | None = None


class LeaseRenewRequest(CamelModel):
    worker_id: UUID


class JobCompleteRequest(CamelModel):
    worker_id: UUID
    analysis_type: str
    model_name: str
    model_version: str
    prompt_version: str
    result_schema_version: str
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    result: dict[str, Any]
    confidence: float = Field(ge=0, le=1)


class JobFailRequest(CamelModel):
    worker_id: UUID
    error: str = Field(min_length=1, max_length=4_000)


class PairingResponse(CamelModel):
    id: UUID
    token: str
    expires_at: datetime


class ListingPage(CamelModel):
    items: list[ListingSummary]
    next_cursor: str | None = None


class PriceObservationCreate(CamelModel):
    canonical_product_id: UUID | None = None
    listing_id: UUID | None = None
    platform: str = Field(min_length=1, max_length=32)
    observed_price: Decimal = Field(gt=0)
    shipping_cost: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="EUR", pattern=r"^[A-Z]{3}$")
    condition: str | None = None
    observation_kind: Literal["soldConfirmed", "manualSold", "active"]
    region: str | None = None
    observed_at: datetime
    source_quality: float = Field(default=1.0, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PriceObservationResponse(PriceObservationCreate):
    id: UUID


class ProductResponse(CamelModel):
    id: UUID
    category_profile: str
    product_type: str
    manufacturer: str | None
    model: str
    variant: str | None
    aliases: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ProductPage(CamelModel):
    items: list[ProductResponse]


class ListingImageImport(CamelModel):
    source_urls: list[HttpUrl] = Field(min_length=1, max_length=10)


class ProviderConfigurationUpsert(CamelModel):
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)
    secret_reference: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_./:-]{1,255}$")

    @model_validator(mode="after")
    def reject_embedded_secrets(self) -> ProviderConfigurationUpsert:
        forbidden = ("secret", "password", "token", "api_key", "apikey")

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    if any(part in key.casefold() for part in forbidden):
                        raise ValueError("provider settings may reference secrets but must not contain them")
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(self.settings)
        return self


class ProviderConfigurationResponse(ProviderConfigurationUpsert):
    id: UUID
    provider: str
    last_health_status: str | None
    last_health_checked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ListingImageResponse(CamelModel):
    id: UUID
    listing_id: UUID
    source_url: str
    sha256_hash: str
    perceptual_hash: str
    width: int
    height: int
    mime_type: str
    analysis_status: str
    exact_duplicate_of: UUID | None = None
    perceptual_duplicate_of: UUID | None = None


class ImageAccessResponse(CamelModel):
    url: str
    expires_at: datetime | None


class ProviderSyncRunCreate(CamelModel):
    search_profile_id: UUID
    provider: str = Field(min_length=1, max_length=32)
    cursor: str | None = Field(default=None, max_length=2_000)


class ProviderSyncRunUpdate(CamelModel):
    status: Literal["COMPLETED", "FAILED"]
    cursor: str | None = Field(default=None, max_length=2_000)
    discovered_count: int = Field(default=0, ge=0)
    imported_count: int = Field(default=0, ge=0)
    error_summary: str | None = Field(default=None, max_length=4_000)


class ProviderSyncRunResponse(CamelModel):
    id: UUID
    search_profile_id: UUID | None
    provider: str
    status: str
    cursor: str | None
    discovered_count: int
    imported_count: int
    error_summary: str | None
    started_at: datetime
    completed_at: datetime | None


class ProviderSyncRunPage(CamelModel):
    items: list[ProviderSyncRunResponse]


class MailImportCreate(CamelModel):
    message_id: str = Field(min_length=1, max_length=1_000)
    sender: str = Field(max_length=1_000)
    subject: str = Field(max_length=2_000)
    received_at: datetime
    raw_storage_path: str = Field(min_length=1, max_length=4_000)
    raw_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parser_version: str = Field(min_length=1, max_length=64)
    status: Literal["IMPORTED", "QUARANTINED", "FAILED"]
    parsed_data: dict[str, Any] | None = None
    error_summary: str | None = Field(default=None, max_length=4_000)


class MailImportResponse(MailImportCreate):
    id: UUID
    created_at: datetime


class MarketEstimateResponse(CamelModel):
    status: str
    minimum: Decimal | None = None
    median: Decimal | None = None
    maximum: Decimal | None = None
    observation_count: int
    data_quality_score: int
    calculation_version: str
    explanation: list[str]


class CsvImportResponse(CamelModel):
    rows_imported: int
    filename: str


class ListingEvaluationResponse(CamelModel):
    listing_id: UUID
    market: MarketEstimateResponse
    deal_score: int | None
    risk_score: int
    notification_created: bool


class NotificationResponse(CamelModel):
    id: UUID
    listing_id: UUID | None
    reason: dict[str, Any]
    created_at: datetime


class ErpExportResponse(CamelModel):
    status: Literal["mocked"] = "mocked"
    listing_id: UUID
    purchase_payload: dict[str, Any]
