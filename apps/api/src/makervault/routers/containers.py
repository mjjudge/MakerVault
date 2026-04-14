"""Containers API router."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from makervault.database import get_db_session
from makervault.models.container import Container
from makervault.models.location import Location
from makervault.schemas.container import (
    ContainerCreate,
    ContainerListResponse,
    ContainerResponse,
    ContainerUpdate,
)

router = APIRouter(prefix="/containers", tags=["containers"])


@router.get("", response_model=ContainerListResponse, summary="List containers")
async def list_containers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    location_id: uuid.UUID | None = Query(default=None),
    parent_container_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> ContainerListResponse:
    query = select(Container)
    count_query = select(func.count()).select_from(Container)
    if location_id is not None:
        query = query.where(Container.location_id == location_id)
        count_query = count_query.where(Container.location_id == location_id)
    if parent_container_id is not None:
        query = query.where(Container.parent_container_id == parent_container_id)
        count_query = count_query.where(Container.parent_container_id == parent_container_id)

    total = (await db.execute(count_query)).scalar_one()
    result = await db.execute(query.order_by(Container.name).offset(skip).limit(limit))
    items = result.scalars().all()
    return ContainerListResponse(
        items=[ContainerResponse.model_validate(c) for c in items], total=total
    )


@router.post(
    "",
    response_model=ContainerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a container",
)
async def create_container(
    body: ContainerCreate,
    db: AsyncSession = Depends(get_db_session),
) -> ContainerResponse:
    # Validate parent references
    if body.location_id is not None:
        if await db.get(Location, body.location_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location {body.location_id} not found.",
            )
    if body.parent_container_id is not None:
        if await db.get(Container, body.parent_container_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent container {body.parent_container_id} not found.",
            )

    container = Container(**body.model_dump())
    db.add(container)
    await db.flush()
    await db.refresh(container)
    return ContainerResponse.model_validate(container)


@router.get(
    "/{container_id}",
    response_model=ContainerResponse,
    summary="Get a container by ID",
)
async def get_container(
    container_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ContainerResponse:
    container = await db.get(Container, container_id)
    if container is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found.",
        )
    return ContainerResponse.model_validate(container)


@router.patch(
    "/{container_id}",
    response_model=ContainerResponse,
    summary="Update a container",
)
async def update_container(
    container_id: uuid.UUID,
    body: ContainerUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> ContainerResponse:
    container = await db.get(Container, container_id)
    if container is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found.",
        )
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(container, field, value)
    await db.flush()
    await db.refresh(container)
    return ContainerResponse.model_validate(container)


@router.delete(
    "/{container_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a container",
)
async def delete_container(
    container_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    container = await db.get(Container, container_id)
    if container is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} not found.",
        )
    await db.delete(container)
