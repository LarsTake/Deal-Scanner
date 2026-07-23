from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import Uuid


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkspaceRow(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    erp_tenant_id: Mapped[str | None] = mapped_column(String(255))


class WorkspaceMemberRow(Base):
    __tablename__ = "workspace_members"

    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchProfileRow(Base, TimestampMixin):
    __tablename__ = "search_profiles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    query: Mapped[str] = mapped_column(String(100))
    category_profile: Mapped[str] = mapped_column(String(64), default="general")
    enabled_platforms: Mapped[list[str]] = mapped_column(JSON, default=list)
    minimum_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    maximum_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    location: Mapped[str | None] = mapped_column(String(255))
    radius_km: Mapped[int | None] = mapped_column(Integer)
    required_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    excluded_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    required_products: Mapped[list[str]] = mapped_column(JSON, default=list)
    excluded_products: Mapped[list[str]] = mapped_column(JSON, default=list)
    minimum_deal_score: Mapped[int] = mapped_column(Integer, default=75)
    maximum_risk_score: Mapped[int] = mapped_column(Integer, default=45)
    notification_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scan_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class SellerRow(Base):
    __tablename__ = "sellers"
    __table_args__ = (UniqueConstraint("workspace_id", "platform", "external_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    account_age_text: Mapped[str | None] = mapped_column(String(255))
    account_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rating_text: Mapped[str | None] = mapped_column(String(255))
    rating_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    review_count: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(255))
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ListingRow(Base, TimestampMixin):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("workspace_id", "platform", "external_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    search_profile_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("search_profiles.id", ondelete="SET NULL"), index=True
    )
    seller_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("sellers.id", ondelete="SET NULL"), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    location: Mapped[str | None] = mapped_column(String(255))
    category_profile: Mapped[str] = mapped_column(String(64), default="general")
    status: Mapped[str] = mapped_column(String(32), default="DISCOVERED")
    analysis_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    current_snapshot_id: Mapped[UUID | None] = mapped_column(Uuid)
    version: Mapped[int] = mapped_column(Integer, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshots: Mapped[list[ListingSnapshotRow]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
        foreign_keys="ListingSnapshotRow.listing_id",
    )


class ListingSnapshotRow(Base):
    __tablename__ = "listing_snapshots"
    __table_args__ = (UniqueConstraint("listing_id", "content_hash"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    provider_version: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    listing: Mapped[ListingRow] = relationship(back_populates="snapshots", foreign_keys=[listing_id])


class ListingImageRow(Base):
    __tablename__ = "listing_images"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    source_url: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str | None] = mapped_column(Text)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    perceptual_hash: Mapped[str | None] = mapped_column(String(255), index=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    analysis_status: Mapped[str] = mapped_column(String(32), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkerRow(Base):
    __tablename__ = "workers"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    operating_system: Mapped[str] = mapped_column(String(100))
    hostname: Mapped[str] = mapped_column(String(255))
    cpu: Mapped[str | None] = mapped_column(String(255))
    ram_gb: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    gpu: Mapped[str | None] = mapped_column(String(255))
    vram_gb: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    runtime: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    installed_models: Mapped[list[str]] = mapped_column(JSON, default=list)
    current_load: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0"))
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisJobRow(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (UniqueConstraint("listing_id", "snapshot_id", "job_type", "input_hash"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    snapshot_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("listing_snapshots.id", ondelete="CASCADE"))
    job_type: Mapped[str] = mapped_column(String(64))
    required_capability: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    assigned_worker_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("workers.id", ondelete="SET NULL"))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnalysisResultRow(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (UniqueConstraint("job_id", "input_hash"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("analysis_jobs.id", ondelete="SET NULL"))
    analysis_type: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(64))
    result_schema_version: Mapped[str] = mapped_column(String(64))
    input_hash: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CanonicalProductRow(Base, TimestampMixin):
    __tablename__ = "canonical_products"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "category_profile",
            "product_type",
            "manufacturer",
            "model",
            "variant",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    category_profile: Mapped[str] = mapped_column(String(64))
    product_type: Mapped[str] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(255))
    variant: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)


class ProductAliasRow(Base):
    __tablename__ = "product_aliases"
    __table_args__ = (UniqueConstraint("workspace_id", "normalized_alias"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    canonical_product_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(500))
    normalized_alias: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ListingProductRow(Base):
    __tablename__ = "listing_products"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    canonical_product_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("canonical_products.id", ondelete="SET NULL"), index=True
    )
    product_type: Mapped[str] = mapped_column(String(100))
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(255))
    variant: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    detection_source: Mapped[str] = mapped_column(String(255))
    raw_match: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductAttributeRow(Base):
    __tablename__ = "product_attributes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    listing_product_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("listing_products.id", ondelete="CASCADE"), index=True
    )
    attribute_key: Mapped[str] = mapped_column(String(255))
    value_text: Mapped[str | None] = mapped_column(Text)
    value_number: Mapped[Decimal | None] = mapped_column(Numeric)
    value_boolean: Mapped[bool | None] = mapped_column(Boolean)
    unit: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    source: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskSignalRow(Base):
    __tablename__ = "risk_signals"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    positive: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(100))
    evidence: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceObservationRow(Base):
    __tablename__ = "price_observations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    canonical_product_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("canonical_products.id", ondelete="CASCADE"), index=True
    )
    listing_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("listings.id", ondelete="SET NULL"), index=True)
    platform: Mapped[str] = mapped_column(String(32))
    observed_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    condition: Mapped[str | None] = mapped_column(String(64))
    observation_kind: Mapped[str] = mapped_column(String(32))
    region: Mapped[str | None] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_quality: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("1"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketValueEstimateRow(Base):
    __tablename__ = "market_value_estimates"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    minimum: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    median: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    maximum: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    observation_count: Mapped[int] = mapped_column(Integer)
    data_quality_score: Mapped[int] = mapped_column(Integer)
    calculation_version: Mapped[str] = mapped_column(String(64))
    explanation: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DealEvaluationRow(Base):
    __tablename__ = "deal_evaluations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    estimated_market_value_min: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    estimated_market_value_median: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    estimated_market_value_max: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    expected_resale_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    estimated_margin: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    deal_score: Mapped[int | None] = mapped_column(Integer)
    risk_score: Mapped[int] = mapped_column(Integer)
    data_quality_score: Mapped[int] = mapped_column(Integer, default=0)
    relevance_score: Mapped[int] = mapped_column(Integer, default=50)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSON)
    calculation_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserFeedbackRow(Base):
    __tablename__ = "user_feedback"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    feedback_type: Mapped[str] = mapped_column(String(64))
    base_listing_version: Mapped[int] = mapped_column(Integer)
    corrected_products: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    corrected_attributes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    corrected_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProviderConfigurationRow(Base, TimestampMixin):
    __tablename__ = "provider_configurations"
    __table_args__ = (UniqueConstraint("workspace_id", "provider"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    settings_json: Mapped[dict[str, Any]] = mapped_column("settings", JSON, default=dict)
    secret_reference: Mapped[str | None] = mapped_column(String(255))
    last_health_status: Mapped[str | None] = mapped_column(String(32))
    last_health_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProviderSyncRunRow(Base):
    __tablename__ = "provider_sync_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    search_profile_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("search_profiles.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20))
    cursor: Mapped[str | None] = mapped_column(Text)
    discovered_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MailImportRow(Base):
    __tablename__ = "mail_imports"
    __table_args__ = (UniqueConstraint("workspace_id", "message_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(Text)
    sender: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_storage_path: Mapped[str] = mapped_column(Text)
    raw_sha256: Mapped[str] = mapped_column(String(64))
    parser_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationRow(Base):
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    evaluation_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("deal_evaluations.id", ondelete="CASCADE"), unique=True
    )
    reason: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationDeliveryRow(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    notification_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("notifications.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExtensionPairingRow(Base):
    __tablename__ = "extension_pairings"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    extension_id: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120), default="Browser-Erweiterung")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyKeyRow(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("workspace_id", "operation", "key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(255))
    operation: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid)
    event_type: Mapped[str] = mapped_column(String(100))
    aggregate_type: Mapped[str] = mapped_column(String(100))
    aggregate_id: Mapped[UUID | None] = mapped_column(Uuid)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
