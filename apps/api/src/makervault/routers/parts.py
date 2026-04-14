"""Parts API router — CRUD + text search."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Text, cast, func, or_, select
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
    q: str | None = Query(default=None, description="Simple text search (name, code, description, aliases)"),
    category_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    part_kind: str | None = Query(default=None),
    tags: list[str] | None = Query(default=None, description="Filter by tags (PostgreSQL only)"),
    db: AsyncSession = Depends(get_db_session),
) -> PartListResponse:
    query = select(Part)
    count_query = select(func.count()).select_from(Part)

    filters = []
    if q:
        like = f"%{q}%"
        # Search the denormalised aliases column (TEXT on SQLite, TEXT[] on Postgres).
        # Casting to Text works on both: Postgres gives '{alias1,alias2}' string;
        # SQLite aliases column is already TEXT.
        filters.append(
            or_(
                Part.name.ilike(like),
                Part.part_code.ilike(like),
                Part.short_description.ilike(like),
                Part.manufacturer.ilike(like),
                Part.manufacturer_part_number.ilike(like),
                cast(Part.aliases, Text).ilike(like),
            )
        )
    if category_id is not None:
        filters.append(Part.category_id == category_id)
    if status is not None:
        filters.append(Part.status == status)
    if part_kind is not None:
        filters.append(Part.part_kind == part_kind)
    if tags:
        # PostgreSQL ARRAY containment — all supplied tags must appear in Part.tags
        from sqlalchemy.dialects.postgresql import ARRAY
        for tag in tags:
            filters.append(Part.tags.op("@>")(cast([tag], ARRAY(Text))))

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
    data = body.model_dump()
    # Strip PostgreSQL ARRAY fields on non-PostgreSQL backends (e.g. SQLite in tests).
    try:
        if db.sync_session.get_bind().dialect.name != "postgresql":
            data.pop("aliases", None)
            data.pop("tags", None)
    except Exception:
        pass
    part = Part(**data)
    db.add(part)
    await db.flush()
    await db.refresh(part)
    return PartResponse.model_validate(part)


@router.get(
    "/duplicates",
    summary="Suggest potential duplicate parts",
)
async def suggest_duplicates(
    db: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    """Return groups of parts that may be duplicates.

    Duplicate candidates are parts that share the same (case-insensitive)
    ``name``, or the same non-null ``manufacturer_part_number``.  Each
    returned group contains at least two parts.
    """
    result = await db.execute(select(Part).order_by(Part.name))
    all_parts = result.scalars().all()

    # Group by normalised name
    name_groups: dict[str, list[Part]] = {}
    for p in all_parts:
        key = p.name.strip().lower()
        name_groups.setdefault(key, []).append(p)

    # Group by manufacturer_part_number (where non-null)
    mpn_groups: dict[str, list[Part]] = {}
    for p in all_parts:
        if p.manufacturer_part_number:
            key = p.manufacturer_part_number.strip().lower()
            mpn_groups.setdefault(key, []).append(p)

    groups: list[dict] = []
    seen_ids: set[frozenset[str]] = set()

    for key, parts in {**name_groups, **mpn_groups}.items():
        if len(parts) < 2:
            continue
        ids = frozenset(str(p.id) for p in parts)
        if ids in seen_ids:
            continue
        seen_ids.add(ids)
        groups.append({
            "reason": "same_name" if key in name_groups else "same_mpn",
            "parts": [
                {
                    "id": str(p.id),
                    "part_code": p.part_code,
                    "name": p.name,
                    "manufacturer": p.manufacturer,
                    "manufacturer_part_number": p.manufacturer_part_number,
                    "status": p.status,
                }
                for p in parts
            ],
        })

    return groups


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
    # Check part_code uniqueness if it's being changed
    if "part_code" in updates and updates["part_code"] != part.part_code:
        existing = await db.execute(
            select(Part).where(Part.part_code == updates["part_code"])
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A part with code '{updates['part_code']}' already exists.",
            )
    # Strip PostgreSQL ARRAY fields on non-PostgreSQL backends (e.g. SQLite in tests).
    try:
        if db.sync_session.get_bind().dialect.name != "postgresql":
            updates.pop("aliases", None)
            updates.pop("tags", None)
    except Exception:
        pass
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
