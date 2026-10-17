from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from deal_scanner_core.market_identity import model_identity
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import exists, select

from .audit import record_audit_event
from .comparison_service import condition_group
from .context import Context
from .db_models import AuditEventRow, ListingRow, PriceObservationRow
from .market_service import evaluate_listing_record

router = APIRouter(tags=["market-research"])
RESEARCH_VERSION = "advertised-model-v1"


def source_url(value: str, platform: str) -> str | None:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    allowed = {"ebay": ("ebay.de", "ebay.com"), "kleinanzeigen": ("kleinanzeigen.de",)}
    if parsed.scheme != "https" or parsed.username or parsed.password or port not in (None, 443):
        return None
    if not any(host == domain or host.endswith("." + domain) for domain in allowed.get(platform, ())):
        return None
    if not parsed.path or parsed.path == "/":
        return None
    return urlunsplit(("https", host.removeprefix("www."), parsed.path.rstrip("/"), "", ""))


class Candidate(BaseModel):
    platform: str = Field(max_length=32)
    url: str = Field(max_length=2000)
    title: str = Field(max_length=500)
    description: str = Field(default="", max_length=5000)
    price: Decimal = Field(gt=0, le=1_000_000)
    shipping: Decimal = Field(default=Decimal(0), ge=0, le=10000)
    currency: str = Field(default="EUR", pattern="^[A-Z]{3}$")


class ResearchBatch(BaseModel):
    candidates: list[Candidate] = Field(default_factory=list, max_length=40)


@router.get("/market-research/targets")
async def targets(context: Context, limit: int = Query(default=3, ge=1, le=10)) -> list[dict[str, str]]:
    recent = exists().where(
        AuditEventRow.workspace_id == context.workspace_id,
        AuditEventRow.aggregate_id == ListingRow.id,
        AuditEventRow.event_type == "market.researched",
        AuditEventRow.created_at >= datetime.now(UTC) - timedelta(hours=6),
    )
    rows = await context.session.scalars(
        select(ListingRow)
        .where(ListingRow.workspace_id == context.workspace_id, ListingRow.is_hidden.is_(False), ~recent)
        .order_by(ListingRow.last_seen_at.desc())
        .limit(500)
    )
    result = []
    for row in rows:
        identity = model_identity(row.title)
        if identity:
            result.append({"id": str(row.id), "query": identity, "title": row.title})
        if len(result) >= limit:
            break
    return result


@router.post("/listings/{listing_id}/market-research")
async def ingest(listing_id: UUID, payload: ResearchBatch, context: Context) -> dict[str, int]:
    # Serialize overlapping requests for a target; dedup also works across scheduler restarts.
    listing = await context.session.scalar(
        select(ListingRow)
        .where(ListingRow.id == listing_id, ListingRow.workspace_id == context.workspace_id)
        .with_for_update()
    )
    if listing is None:
        raise HTTPException(404, "listing not found")
    identity = model_identity(listing.title)
    if not identity:
        raise HTTPException(422, "No unambiguous supported product model in title")
    existing = list(
        (
            await context.session.scalars(
                select(PriceObservationRow).where(
                    PriceObservationRow.workspace_id == context.workspace_id,
                    PriceObservationRow.listing_id == listing_id,
                )
            )
        ).all()
    )
    by_url = {
        row.metadata_json.get("sourceUrl"): row
        for row in existing
        if row.metadata_json.get("researchVersion") == RESEARCH_VERSION
    }
    own_url = source_url(listing.url, listing.platform)
    accepted = 0
    seen: set[str] = set()
    now = datetime.now(UTC)
    for candidate in payload.candidates:
        url = source_url(candidate.url, candidate.platform)
        if not url or url == own_url or url in seen or candidate.currency != listing.currency:
            continue
        if model_identity(candidate.title) != identity:
            continue
        condition = condition_group(candidate.title + "\n" + candidate.description)
        if condition != condition_group(listing.title + "\n" + listing.description):
            continue
        seen.add(url)
        row = by_url.get(url)
        if row is None:
            row = PriceObservationRow(workspace_id=context.workspace_id, listing_id=listing.id)
            context.session.add(row)
        row.platform = candidate.platform
        row.observed_price = candidate.price
        row.shipping_cost = candidate.shipping
        row.currency = candidate.currency
        row.condition = "defekt" if condition == "damaged" else condition
        row.observation_kind = "active"
        row.observed_at = now
        row.source_quality = Decimal("0.7")
        row.metadata_json = {
            "researchVersion": RESEARCH_VERSION,
            "identity": identity,
            "sourceUrl": url,
            "sourceTitle": candidate.title,
            "priceKind": "advertised",
            "verifiedSale": False,
        }
        accepted += 1
    record_audit_event(
        context,
        "market.researched",
        "listing",
        listing_id,
        {"accepted": accepted, "examined": len(payload.candidates), "identity": identity},
    )
    await context.session.flush()
    await evaluate_listing_record(context.session, context.workspace_id, listing_id)
    await context.session.commit()
    return {"accepted": accepted, "examined": len(payload.candidates)}
