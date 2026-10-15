from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from deal_scanner_core.models import ProductDetection
from deal_scanner_extraction import RuleExtractor
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .comparison_service import single_product_scope
from .db_models import (
    CanonicalProductRow,
    ListingProductRow,
    ListingRow,
    PriceObservationRow,
    ProductAliasRow,
    ProductAttributeRow,
)


def normalize_alias(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _clean_label(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()
    return cleaned or None


def canonicalize_detection(detection: ProductDetection) -> ProductDetection:
    candidates = RuleExtractor().analyze(detection.model, "").products
    known = next((item for item in candidates if item.product_type == detection.product_type), None)
    if known is not None:
        return detection.model_copy(
            update={
                "manufacturer": known.manufacturer,
                "model": known.model,
                "variant": known.variant or _clean_label(detection.variant),
            }
        )
    return detection.model_copy(
        update={
            "product_type": normalize_alias(detection.product_type).replace(" ", "_"),
            "manufacturer": _clean_label(detection.manufacturer),
            "model": _clean_label(detection.model) or detection.model,
            "variant": _clean_label(detection.variant),
        }
    )


async def _resolve_canonical_product(
    session: AsyncSession,
    workspace_id: UUID,
    category_profile: str,
    detection: ProductDetection,
) -> CanonicalProductRow:
    aliases = {
        normalize_alias(value)
        for value in (
            detection.model,
            " ".join(filter(None, (detection.manufacturer, detection.model))),
        )
        if value and normalize_alias(value)
    }
    if aliases:
        aliased = (
            await session.execute(
                select(CanonicalProductRow)
                .join(ProductAliasRow, ProductAliasRow.canonical_product_id == CanonicalProductRow.id)
                .where(
                    ProductAliasRow.workspace_id == workspace_id,
                    ProductAliasRow.normalized_alias.in_(aliases),
                    CanonicalProductRow.product_type == detection.product_type,
                    CanonicalProductRow.workspace_id == workspace_id,
                    CanonicalProductRow.category_profile == category_profile,
                    func.coalesce(CanonicalProductRow.variant, "") == (detection.variant or ""),
                    func.coalesce(CanonicalProductRow.manufacturer, "") == (detection.manufacturer or ""),
                    func.lower(CanonicalProductRow.model) == detection.model.casefold(),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if aliased is not None:
            return aliased

    manufacturer = detection.manufacturer or ""
    variant = detection.variant or ""
    product = (
        await session.execute(
            select(CanonicalProductRow).where(
                CanonicalProductRow.workspace_id == workspace_id,
                CanonicalProductRow.category_profile == category_profile,
                CanonicalProductRow.product_type == detection.product_type,
                func.coalesce(CanonicalProductRow.manufacturer, "") == manufacturer,
                func.lower(CanonicalProductRow.model) == detection.model.casefold(),
                func.coalesce(CanonicalProductRow.variant, "") == variant,
            )
        )
    ).scalar_one_or_none()
    if product is None:
        product = CanonicalProductRow(
            workspace_id=workspace_id,
            category_profile=category_profile,
            product_type=detection.product_type,
            manufacturer=detection.manufacturer,
            model=detection.model,
            variant=detection.variant,
            metadata_json={},
        )
        session.add(product)
        await session.flush()

    existing_aliases = set(
        (
            await session.execute(
                select(ProductAliasRow.normalized_alias).where(
                    ProductAliasRow.workspace_id == workspace_id,
                    ProductAliasRow.normalized_alias.in_(aliases),
                )
            )
        ).scalars()
    )
    for alias in sorted(aliases - existing_aliases):
        session.add(
            ProductAliasRow(
                workspace_id=workspace_id,
                canonical_product_id=product.id,
                alias=alias,
                normalized_alias=alias,
            )
        )
    return product


async def persist_listing_products(
    session: AsyncSession,
    workspace_id: UUID,
    listing_id: UUID,
    category_profile: str,
    detections: list[ProductDetection],
    *,
    source: str,
    attributes: list[dict[str, Any]] | None = None,
) -> list[CanonicalProductRow]:
    products: list[CanonicalProductRow] = []
    listing_products: list[ListingProductRow] = []
    seen: set[UUID] = set()
    for raw_detection in detections:
        detection = canonicalize_detection(raw_detection)
        product = await _resolve_canonical_product(session, workspace_id, category_profile, detection)
        if product.id not in seen:
            products.append(product)
            seen.add(product.id)
        existing = (
            await session.execute(
                select(ListingProductRow).where(
                    ListingProductRow.workspace_id == workspace_id,
                    ListingProductRow.listing_id == listing_id,
                    ListingProductRow.canonical_product_id == product.id,
                    ListingProductRow.detection_source == source,
                    ListingProductRow.raw_match == detection.evidence,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = ListingProductRow(
                workspace_id=workspace_id,
                listing_id=listing_id,
                canonical_product_id=product.id,
                product_type=detection.product_type,
                manufacturer=detection.manufacturer,
                model=detection.model,
                variant=detection.variant,
                quantity=detection.quantity,
                confidence=Decimal(str(detection.confidence)),
                detection_source=source,
                raw_match=detection.evidence,
            )
            session.add(existing)
            await session.flush()
        listing_products.append(existing)

    listing = await session.get(ListingRow, listing_id)
    scoped_product = single_product_scope(listing, listing_products) if listing else None
    if scoped_product is not None:
        observations = (
            await session.execute(
                select(PriceObservationRow).where(
                    PriceObservationRow.workspace_id == workspace_id,
                    PriceObservationRow.listing_id == listing_id,
                    PriceObservationRow.canonical_product_id.is_(None),
                )
            )
        ).scalars()
        for observation in observations:
            # Attach imported prices only when the entire offer is one unit.
            # Manually supplied bundle comparables keep their explicit scope.
            if observation.metadata_json.get("snapshotId"):
                observation.canonical_product_id = scoped_product

    await _persist_attributes(session, workspace_id, listing_products, attributes or [], source)
    return products


async def _persist_attributes(
    session: AsyncSession,
    workspace_id: UUID,
    listing_products: list[ListingProductRow],
    attributes: list[dict[str, Any]],
    source: str,
) -> None:
    for attribute in attributes:
        if not listing_products:
            return
        raw_index = attribute.get("productIndex", 0)
        index = raw_index if isinstance(raw_index, int) and not isinstance(raw_index, bool) else 0
        if index < 0 or index >= len(listing_products):
            continue
        key = attribute.get("key") or attribute.get("name")
        if not isinstance(key, str) or not key.strip() or "value" not in attribute:
            continue
        value = attribute["value"]
        value_text: str | None = None
        value_number: Decimal | None = None
        value_boolean: bool | None = None
        if isinstance(value, bool):
            value_boolean = value
        elif isinstance(value, (int, float, Decimal)):
            try:
                value_number = Decimal(str(value))
            except InvalidOperation:
                continue
        elif isinstance(value, str) and value.strip():
            value_text = value.strip()
        else:
            continue
        raw_confidence = attribute.get("confidence", 1)
        try:
            confidence = max(Decimal("0"), min(Decimal("1"), Decimal(str(raw_confidence))))
        except InvalidOperation:
            confidence = Decimal("1")
        session.add(
            ProductAttributeRow(
                workspace_id=workspace_id,
                listing_product_id=listing_products[index].id,
                attribute_key=key.strip(),
                value_text=value_text,
                value_number=value_number,
                value_boolean=value_boolean,
                unit=str(attribute["unit"])[:64] if attribute.get("unit") is not None else None,
                confidence=confidence,
                source=source,
            )
        )
