from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..context import Context
from ..db_models import SearchProfileRow
from ..schemas import SearchProfileCreate, SearchProfileResponse

router = APIRouter(prefix="/search-profiles", tags=["search-profiles"])


def _response(row: SearchProfileRow) -> SearchProfileResponse:
    return SearchProfileResponse(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        query=row.query,
        category_profile=row.category_profile,
        enabled_platforms=row.enabled_platforms,
        minimum_price=row.minimum_price,
        maximum_price=row.maximum_price,
        required_terms=row.required_terms,
        excluded_terms=row.excluded_terms,
        minimum_deal_score=row.minimum_deal_score,
        maximum_risk_score=row.maximum_risk_score,
        scan_interval_minutes=row.scan_interval_minutes,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[SearchProfileResponse])
async def list_profiles(context: Context) -> list[SearchProfileResponse]:
    result = await context.session.execute(
        select(SearchProfileRow)
        .where(SearchProfileRow.workspace_id == context.workspace_id)
        .order_by(SearchProfileRow.name)
    )
    return [_response(row) for row in result.scalars()]


@router.post("", response_model=SearchProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(payload: SearchProfileCreate, context: Context) -> SearchProfileResponse:
    row = SearchProfileRow(workspace_id=context.workspace_id, **payload.model_dump(by_alias=False))
    context.session.add(row)
    await context.session.commit()
    await context.session.refresh(row)
    return _response(row)


@router.put("/{profile_id}", response_model=SearchProfileResponse)
async def update_profile(profile_id: UUID, payload: SearchProfileCreate, context: Context) -> SearchProfileResponse:
    result = await context.session.execute(
        select(SearchProfileRow).where(
            SearchProfileRow.id == profile_id,
            SearchProfileRow.workspace_id == context.workspace_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="search profile not found")
    for field, value in payload.model_dump(by_alias=False).items():
        setattr(row, field, value)
    await context.session.commit()
    await context.session.refresh(row)
    return _response(row)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: UUID, context: Context) -> None:
    result = await context.session.execute(
        select(SearchProfileRow).where(
            SearchProfileRow.id == profile_id,
            SearchProfileRow.workspace_id == context.workspace_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="search profile not found")
    await context.session.delete(row)
    await context.session.commit()
