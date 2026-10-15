"""Conservative, shared eligibility rules for market estimates and their evidence UI."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .db_models import ListingProductRow, ListingRow, PriceObservationRow

COMPARISON_VERSION = "comparability-v1"
MAX_COMPARISON_CANDIDATES = 2000


def condition_group(value: str | None) -> str:
    text = (value or "").casefold()
    if re.search(r"\b(defekt|beschädigt|ersatzteil\w*|ungetestet|for parts|broken)\b", text):
        return "damaged"
    if re.search(r"\b(neuwertig|wie neu|gebraucht|used|refurbished|generalüberholt)\b", text):
        return "used"
    if re.search(r"\b(neu|new|unbenutzt|ungeöffnet|ovp versiegelt)\b", text):
        return "new"
    return "unknown"


def single_product_scope(listing: ListingRow, products: list[ListingProductRow]) -> UUID | None:
    """Never infer an entire offer's scope solely from one recognized component."""
    title = listing.title.casefold()
    text = f"{title}\n{listing.description.casefold()}"
    if re.search(
        r"\b(pc|desktop|computer|rechner|komplettsystem|komplettrechner|gaming[- ]?pc|suche|gesuch|wanted)\b", title
    ):
        return None
    if "+" in title or re.search(
        r"\b(bundle|konvolut|paket|komplettset|set|sammlung|komplett[- ]?pc)\b"
        r"|\b[2-9]\d*\s*(?:[x×]|stück|grafikkarten|gpus)\b",
        text,
    ):
        return None
    identities = {row.canonical_product_id for row in products}
    if len(identities) != 1 or None in identities or any(row.quantity != 1 for row in products):
        return None
    return next(iter(identities))


@dataclass
class ComparisonSelection:
    rows: list[PriceObservationRow]
    exclusions: Counter[str]
    scope: str
    window_limited: bool = False

    def explanations(self) -> list[str]:
        return [
            f"Vergleichsprüfung {COMPARISON_VERSION}; Angebotstyp: {self.scope}.",
            *(
                [f"Prüffenster auf die {MAX_COMPARISON_CANDIDATES} jüngsten Kandidaten begrenzt."]
                if self.window_limited
                else []
            ),
            *[f"Ausgeschlossen: {count} × {reason}." for reason, count in sorted(self.exclusions.items())],
            "Unbekannter Zustand wird nur mit unbekanntem Zustand verglichen.",
            "Manuell zugeordnete Verkäufe sind Nutzerevidenz, keine unabhängig verifizierten Verkäufe.",
            "Verwendete Vergleichs-IDs: " + (", ".join(str(row.id) for row in self.rows) or "keine"),
        ]


async def select_comparisons(session: AsyncSession, workspace_id: UUID, listing: ListingRow) -> ComparisonSelection:
    products = list(
        (
            await session.scalars(
                select(ListingProductRow).where(
                    ListingProductRow.workspace_id == workspace_id,
                    ListingProductRow.listing_id == listing.id,
                )
            )
        ).all()
    )
    product_id = single_product_scope(listing, products)
    scope = PriceObservationRow.listing_id == listing.id
    if product_id is not None:
        scope = or_(scope, PriceObservationRow.canonical_product_id == product_id)
    candidates = list(
        (
            await session.scalars(
                select(PriceObservationRow)
                .where(
                    PriceObservationRow.workspace_id == workspace_id,
                    PriceObservationRow.currency == listing.currency,
                    scope,
                )
                .order_by(PriceObservationRow.observed_at.desc(), PriceObservationRow.id.desc())
                .limit(MAX_COMPARISON_CANDIDATES + 1)
            )
        ).all()
    )
    window_limited = len(candidates) > MAX_COMPARISON_CANDIDATES
    candidates = candidates[:MAX_COMPARISON_CANDIDATES]
    source_ids = {row.listing_id for row in candidates if row.listing_id and row.listing_id != listing.id}
    sources = (
        {
            row.id: row
            for row in (
                await session.scalars(
                    select(ListingRow).where(
                        ListingRow.workspace_id == workspace_id,
                        ListingRow.id.in_(source_ids),
                    )
                )
            ).all()
        }
        if source_ids
        else {}
    )
    source_products: dict[UUID, list[ListingProductRow]] = {}
    if source_ids:
        for product in (
            await session.scalars(
                select(ListingProductRow).where(
                    ListingProductRow.workspace_id == workspace_id,
                    ListingProductRow.listing_id.in_(source_ids),
                )
            )
        ).all():
            source_products.setdefault(product.listing_id, []).append(product)
    target_condition = condition_group(f"{listing.title}\n{listing.description}")
    selected: list[PriceObservationRow] = []
    excluded: Counter[str] = Counter()
    seen_sources: set[UUID] = set()
    for row in candidates:
        reason = None
        source = sources.get(row.listing_id) if row.listing_id else None
        repeated_source = source is not None and source.id in seen_sources
        if source is not None:
            seen_sources.add(source.id)
        # Legacy manually attached sold comparables remain valid user evidence;
        # imported snapshot history is never independent evidence for itself.
        attached_manual_sale = (
            row.listing_id == listing.id
            and row.platform == "manual"
            and row.observation_kind in {"soldConfirmed", "manualSold"}
            and not row.metadata_json.get("snapshotId")
        )
        if row.listing_id == listing.id and not attached_manual_sale:
            reason = "eigene Angebotshistorie"
        elif source is not None and (
            product_id is None or single_product_scope(source, source_products.get(source.id, [])) != product_id
        ):
            reason = "abweichender oder unklarer Angebotsumfang"
        elif row.listing_id is not None and row.listing_id != listing.id and source is None:
            reason = "Quellangebot nicht im Workspace verfügbar"
        elif repeated_source:
            reason = "wiederholter Preisstand desselben Angebots"
        elif row.observed_price <= 0 or row.source_quality <= 0:
            reason = "kein positiver belastbarer Preis"
        elif (
            condition_group(row.condition or (f"{source.title}\n{source.description}" if source else ""))
            != target_condition
        ):
            reason = "abweichender oder unklarer Zustand"
        if reason:
            excluded[reason] += 1
        else:
            selected.append(row)
    return ComparisonSelection(
        selected, excluded, "Einzelprodukt" if product_id else "Bundle/System/unklar", window_limited
    )
