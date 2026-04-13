"""Locations API router."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.models.location import Location
from makervault.schemas.location import (
    LocationCreate,
    LocationListResponse,
    LocationResponse,
    LocationUpdate,
)

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=LocationListResponse, summary="List locations")
async def list_locations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
) -> LocationListResponse:
    total_result = await db.execute(select(func.count()).select_from(Location))
    total = total_result.scalar_one()

    result = await db.execute(
        select(Location).order_by(Location.name).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return LocationListResponse(
        items=[LocationResponse.model_validate(loc) for loc in items], total=total
    )


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a location",
)
async def create_location(
    body: LocationCreate,
    db: AsyncSession = Depends(get_db_session),
) -> LocationResponse:
    if body.parent_location_id is not None:
        parent = await db.get(Location, body.parent_location_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent location {body.parent_location_id} not found.",
            )
    location = Location(**body.model_dump())
    db.add(location)
    await db.flush()
    await db.refresh(location)
    return LocationResponse.model_validate(location)


@router.get(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Get a location by ID",
)
async def get_location(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> LocationResponse:
    location = await db.get(Location, location_id)
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found.",
        )
    return LocationResponse.model_validate(location)


@router.patch(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Update a location",
)
async def update_location(
    location_id: uuid.UUID,
    body: LocationUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> LocationResponse:
    location = await db.get(Location, location_id)
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found.",
        )
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(location, field, value)
    await db.flush()
    await db.refresh(location)
    return LocationResponse.model_validate(location)


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a location",
)
async def delete_location(
    location_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    location = await db.get(Location, location_id)
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {location_id} not found.",
        )
    await db.delete(location)
