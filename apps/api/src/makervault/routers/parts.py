"""Parts API router — CRUD + text search."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.models.part import Part
from makervault.schemas.part import (
    PartCreate,
    PartListResponse,
    PartResponse,
    PartUpdate,
)

router = APIRouter(prefix="/parts", tags=["parts"])


@router.get("", response_model=PartListResponse, summary="List / search parts")
async def list_parts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(default=None, description="Simple text search (name, code, description)"),
    category_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    part_kind: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> PartListResponse:
    query = select(Part)
    count_query = select(func.count()).select_from(Part)

    filters = []
    if q:
        like = f"%{q}%"
        filters.append(
            or_(
                Part.name.ilike(like),
                Part.part_code.ilike(like),
                Part.short_description.ilike(like),
                Part.manufacturer.ilike(like),
                Part.manufacturer_part_number.ilike(like),
            )
        )
    if category_id is not None:
        filters.append(Part.category_id == category_id)
    if status is not None:
        filters.append(Part.status == status)
    if part_kind is not None:
        filters.append(Part.part_kind == part_kind)

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Part.name).offset(skip).limit(limit))
    items = result.scalars().all()
    return PartListResponse(
        items=[PartResponse.model_validate(p) for p in items], total=total
    )


@router.post(
    "",
    response_model=PartResponse,
    status_code=201,
    summary="Create a part",
)
async def create_part(
    body: PartCreate,
    db: AsyncSession = Depends(get_db_session),
) -> PartResponse:
    # Check uniqueness of part_code
    existing = await db.execute(
        select(Part).where(Part.part_code == body.part_code)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A part with code '{body.part_code}' already exists.",
        )
    part = Part(**body.model_dump())
    db.add(part)
    await db.flush()
    await db.refresh(part)
    return PartResponse.model_validate(part)


@router.get(
    "/{part_id}",
    response_model=PartResponse,
    summary="Get a part by ID",
)
async def get_part(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> PartResponse:
    part = await db.get(Part, part_id)
    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {part_id} not found.",
        )
    return PartResponse.model_validate(part)


@router.patch(
    "/{part_id}",
    response_model=PartResponse,
    summary="Update a part",
)
async def update_part(
    part_id: uuid.UUID,
    body: PartUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> PartResponse:
    part = await db.get(Part, part_id)
    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {part_id} not found.",
        )
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(part, field, value)
    await db.flush()
    await db.refresh(part)
    return PartResponse.model_validate(part)


@router.delete(
    "/{part_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a part",
)
async def delete_part(
    part_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    part = await db.get(Part, part_id)
    if part is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part {part_id} not found.",
        )
    await db.delete(part)
